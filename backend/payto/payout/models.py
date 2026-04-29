"""
Database models for the payout engine.

Core models:
- Merchant: Has a balance
- LedgerEntry: Credit or debit to merchant balance
- Payout: Request to send funds to bank account
- IdempotencyKey: Prevent duplicate payout requests
"""
import uuid
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta


class Merchant(models.Model):
    """
    A merchant who can receive payments and request payouts.
    Balance is always calculated from ledger entries.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    country_code = models.CharField(max_length=2, default='IN')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'merchants'
        indexes = [
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f"{self.name} ({self.email})"

    @property
    def balance_paise(self):
        """
        Get merchant's current balance in paise.
        Calculated as sum(credits) - sum(debits).
        Uses database aggregation, not Python arithmetic.
        """
        return self.get_balance_paise()

    def get_balance_paise(self):
        """
        Calculate balance at database level.
        Credits are positive, debits are negative.
        """
        from django.db.models import Sum, Value, Case, When
        
        result = LedgerEntry.objects.filter(merchant=self).aggregate(
            balance=Sum('amount_paise')
        )
        return result['balance'] or 0

    @property
    def held_balance_paise(self):
        """Get total amount held in pending/processing payouts."""
        from django.db.models import Sum
        
        result = Payout.objects.filter(
            merchant=self,
            status__in=['pending', 'processing']
        ).aggregate(held=Sum('amount_paise'))
        return result['held'] or 0

    @property
    def available_balance_paise(self):
        """Get balance available for withdrawal after held amounts."""
        return self.balance_paise - self.held_balance_paise


class LedgerEntry(models.Model):
    """
    A credit or debit entry to a merchant's ledger.
    Amount is in paise (smallest unit).
    Positive = credit (customer payment)
    Negative = debit (manual correction)
    """
    ENTRY_TYPE_CHOICES = [
        ('credit', 'Customer Payment'),
        ('debit', 'Correction'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name='ledger_entries')
    amount_paise = models.BigIntegerField()  # Always positive, sign indicates type
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPE_CHOICES)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    external_id = models.CharField(max_length=255, null=True, blank=True, unique=True)

    class Meta:
        db_table = 'ledger_entries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['merchant', '-created_at']),
            models.Index(fields=['external_id']),
        ]

    def __str__(self):
        return f"{self.merchant.name}: {self.amount_paise} paise ({self.entry_type})"


class PayoutStatus(models.TextChoices):
    """Legal payout state transitions"""
    PENDING = 'pending', 'Pending'
    PROCESSING = 'processing', 'Processing'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'


class Payout(models.Model):
    """
    A payout request from merchant to their bank account.
    
    State machine:
    - pending → processing → completed (success)
    - pending → processing → failed (then funds returned)
    
    Illegal transitions are blocked at database/application level.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name='payouts')
    amount_paise = models.BigIntegerField()  # Never floats or decimals
    bank_account_id = models.CharField(max_length=255)  # Bank account identifier
    status = models.CharField(
        max_length=20,
        choices=PayoutStatus.choices,
        default=PayoutStatus.PENDING,
        db_index=True
    )
    
    # Track attempts for retry logic
    attempt_count = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)
    
    # Last attempt info
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    
    # Idempotency tracking
    idempotency_key = models.CharField(max_length=36, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'payouts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['merchant', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['merchant', 'status']),
        ]
        # Prevent duplicate payouts for same merchant + idempotency key
        constraints = [
            models.UniqueConstraint(
                fields=['merchant', 'idempotency_key'],
                condition=models.Q(idempotency_key__isnull=False),
                name='unique_payout_idempotency_per_merchant'
            ),
        ]

    def __str__(self):
        return f"Payout {self.id}: {self.amount_paise} paise ({self.status})"

    def can_transition_to(self, new_status):
        """
        Enforce state machine rules.
        Legal: pending → processing → completed/failed
        Illegal: backwards, completed → anything, etc.
        """
        legal_transitions = {
            'pending': ['processing'],
            'processing': ['completed', 'failed'],
            'completed': [],  # Terminal state
            'failed': [],     # Terminal state
        }
        return new_status in legal_transitions.get(self.status, [])

    @transaction.atomic
    def transition_to(self, new_status, error_message=''):
        """
        Safely transition to a new status.
        If failing, return held funds to merchant balance.
        """
        if not self.can_transition_to(new_status):
            raise ValidationError(
                f"Cannot transition from {self.status} to {new_status}"
            )

        # If transitioning to failed, return funds
        if new_status == 'failed':
            LedgerEntry.objects.create(
                merchant=self.merchant,
                amount_paise=self.amount_paise,
                entry_type='credit',
                description=f'Payout {self.id} failed, funds returned'
            )

        # Update status
        self.status = new_status
        self.error_message = error_message
        self.updated_at = timezone.now()
        
        if new_status in ['completed', 'failed']:
            self.completed_at = timezone.now()
        
        self.save()


class IdempotencyKey(models.Model):
    """
    Track idempotency keys to prevent duplicate operations.
    Keys are scoped per merchant and expire after 24 hours.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    key = models.CharField(max_length=36)  # UUID string
    payout = models.ForeignKey(Payout, on_delete=models.CASCADE, related_name='idempotency_records')
    
    # Track response for replay
    response_data = models.JSONField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'idempotency_keys'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['merchant', 'key']),
            models.Index(fields=['expires_at']),
        ]
        # Enforce per-merchant uniqueness
        constraints = [
            models.UniqueConstraint(
                fields=['merchant', 'key'],
                condition=models.Q(expires_at__gt=timezone.now()),
                name='unique_active_idempotency_key'
            ),
        ]

    def __str__(self):
        return f"IdempotencyKey {self.key[:8]}... for {self.merchant.name}"

    @staticmethod
    def create_for_merchant(merchant, key):
        """Create an idempotency key that expires in 24 hours."""
        expires_at = timezone.now() + timedelta(hours=24)
        return IdempotencyKey(
            merchant=merchant,
            key=key,
            expires_at=expires_at
        )

    def is_expired(self):
        """Check if this key has expired."""
        return timezone.now() > self.expires_at
