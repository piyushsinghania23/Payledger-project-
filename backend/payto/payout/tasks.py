"""
Celery tasks for payout processing.

Simulates bank settlement and handles payout lifecycle:
- Pick up pending payouts
- Move to processing
- Simulate bank settlement (70% success, 20% fail, 10% hang/retry)
- Return funds on failure
- Clean up expired idempotency keys
"""
import random
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import Payout, IdempotencyKey, LedgerEntry


@shared_task(bind=True, max_retries=3)
def process_single_payout(self, payout_id):
    """
    Process a single pending payout.
    
    Called by process_pending_payouts.
    Handles exponential backoff on transient failures.
    """
    try:
        payout = Payout.objects.get(id=payout_id)
    except Payout.DoesNotExist:
        return f"Payout {payout_id} not found"

    # Only process pending payouts
    if payout.status != 'pending':
        return f"Payout {payout_id} is not in pending state (status: {payout.status})"

    # Simulate bank settlement decision
    settlement_result = simulate_bank_settlement()
    
    try:
        if settlement_result == 'success':
            _complete_payout(payout)
            return f"Payout {payout_id} completed successfully"
        
        elif settlement_result == 'failed':
            _fail_payout(payout, "Bank settlement failed")
            return f"Payout {payout_id} failed"
        
        elif settlement_result == 'processing':
            # Move to processing, will be retried by retry_processing_payouts task
            _move_to_processing(payout)
            return f"Payout {payout_id} moved to processing"
    
    except Exception as e:
        return f"Error processing payout {payout_id}: {str(e)}"


@shared_task
def process_pending_payouts():
    """
    Background task to pick up pending payouts.
    Runs periodically (every 10 seconds by default).
    
    Picks up all pending payouts and starts processing them.
    """
    pending_payouts = Payout.objects.filter(status='pending').order_by('created_at')[:10]
    
    count = 0
    for payout in pending_payouts:
        process_single_payout.delay(str(payout.id))
        count += 1
    
    return f"Started processing {count} pending payouts"


@shared_task(bind=True, max_retries=2)
def retry_processing_payouts(self):
    """
    Retry payouts stuck in processing state.
    
    If a payout has been in processing for more than 30 seconds,
    retry up to max_attempts times with exponential backoff.
    After max_attempts, move to failed state and return funds.
    """
    thirty_seconds_ago = timezone.now() - timedelta(seconds=30)
    
    # Find payouts stuck in processing for too long
    stuck_payouts = Payout.objects.filter(
        status='processing',
        last_attempt_at__lt=thirty_seconds_ago
    ).order_by('created_at')[:10]

    for payout in stuck_payouts:
        if payout.attempt_count >= payout.max_attempts:
            # Max attempts reached, fail the payout
            _fail_payout(payout, "Max retry attempts exceeded")
        else:
            # Retry processing
            payout.attempt_count += 1
            payout.last_attempt_at = timezone.now()
            payout.save()
            
            # Simulate another settlement attempt
            settlement_result = simulate_bank_settlement()
            
            if settlement_result == 'success':
                _complete_payout(payout)
            elif settlement_result == 'failed':
                _fail_payout(payout, "Bank settlement failed on retry")
            # If still processing, will be retried again next cycle

    return f"Retried {stuck_payouts.count()} stuck payouts"


@shared_task
def cleanup_expired_idempotency_keys():
    """
    Remove expired idempotency keys (older than 24 hours).
    Runs periodically (every hour by default).
    """
    expired_cutoff = timezone.now() - timedelta(hours=24)
    deleted_count, _ = IdempotencyKey.objects.filter(
        expires_at__lt=expired_cutoff
    ).delete()
    
    return f"Deleted {deleted_count} expired idempotency keys"


# Helper functions

def simulate_bank_settlement():
    """
    Simulate bank settlement response.
    
    70% success
    20% failure
    10% processing (will retry later)
    """
    rand = random.random()
    
    if rand < 0.70:
        return 'success'
    elif rand < 0.90:
        return 'failed'
    else:
        return 'processing'


@transaction.atomic
def _move_to_processing(payout):
    """Move payout from pending to processing state."""
    if not payout.can_transition_to('processing'):
        raise ValueError(f"Cannot transition {payout.id} to processing")
    
    payout.status = 'processing'
    payout.attempt_count = 1
    payout.last_attempt_at = timezone.now()
    payout.updated_at = timezone.now()
    payout.save()


@transaction.atomic
def _complete_payout(payout):
    """Move payout from processing to completed state."""
    if not payout.can_transition_to('completed'):
        raise ValueError(f"Cannot transition {payout.id} to completed")
    
    payout.status = 'completed'
    payout.completed_at = timezone.now()
    payout.updated_at = timezone.now()
    payout.error_message = ''
    payout.save()


@transaction.atomic
def _fail_payout(payout, error_message):
    """
    Move payout from processing to failed state.
    Return held funds to merchant balance.
    
    This is atomic: status change and fund return happen together or not at all.
    """
    if not payout.can_transition_to('failed'):
        raise ValueError(f"Cannot transition {payout.id} to failed")
    
    # Return funds to merchant
    LedgerEntry.objects.create(
        merchant=payout.merchant,
        amount_paise=payout.amount_paise,
        entry_type='credit',
        description=f'Payout {payout.id} failed: {error_message}'
    )
    
    # Update payout status
    payout.status = 'failed'
    payout.completed_at = timezone.now()
    payout.updated_at = timezone.now()
    payout.error_message = error_message
    payout.save()
