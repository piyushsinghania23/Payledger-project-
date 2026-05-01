"""
REST API views for the payout engine.

Key patterns:
- Idempotency: Check for existing key, return same response
- Concurrency: Use SELECT FOR UPDATE for atomic balance checks
- Validation: Ensure state machine constraints
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import transaction
from django.db import IntegrityError
from django.db.utils import OperationalError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from datetime import timedelta
import json
import time

from .models import Merchant, Payout, LedgerEntry, IdempotencyKey
from .serializers import (
    MerchantSerializer, PayoutSerializer, PayoutCreateSerializer,
    PayoutDetailSerializer, LedgerEntrySerializer
)


class MerchantViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for merchants.
    GET /api/v1/merchants/<id>/
    GET /api/v1/merchants/<id>/balance/
    GET /api/v1/merchants/<id>/ledger/
    """
    queryset = Merchant.objects.all()
    serializer_class = MerchantSerializer
    permission_classes = []

    @action(detail=True, methods=['get'])
    def balance(self, request, pk=None):
        """
        Get merchant's current balance.
        Returns: total, held, available (all in paise)
        """
        merchant = self.get_object()
        return Response({
            'total_paise': merchant.balance_paise,
            'held_paise': merchant.held_balance_paise,
            'available_paise': merchant.available_balance_paise,
        })

    @action(detail=True, methods=['get'])
    def ledger(self, request, pk=None):
        """Get merchant's ledger entries (credits and debits)."""
        merchant = self.get_object()
        entries = merchant.ledger_entries.all()
        
        page = self.paginate_queryset(entries)
        if page is not None:
            serializer = LedgerEntrySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = LedgerEntrySerializer(entries, many=True)
        return Response(serializer.data)


class PayoutViewSet(viewsets.ModelViewSet):
    """
    API endpoints for payouts.
    POST   /api/v1/payouts/           (create with idempotency)
    GET    /api/v1/payouts/<id>/      (get payout)
    GET    /api/v1/payouts/           (list payouts)
    PATCH  /api/v1/payouts/<id>/      (update status - admin only)
    """
    queryset = Payout.objects.all()
    serializer_class = PayoutSerializer
    permission_classes = []

    def get_serializer_class(self):
        if self.action == 'create':
            return PayoutCreateSerializer
        if self.action == 'retrieve':
            return PayoutDetailSerializer
        return PayoutSerializer

    def create(self, request, *args, **kwargs):
        """
        Create a payout request with idempotency support.
        
        Required headers:
        - Idempotency-Key: UUID (unique per merchant, 24h TTL)
        
        Request body:
        {
            "merchant_id": "uuid",
            "amount_paise": 1000000,  # 1000 rupees
            "bank_account_id": "account123"
        }
        
        Returns:
        - On success: 201 Created with payout details
        - On duplicate: 200 OK with same response as original
        - On insufficient balance: 400 Bad Request
        - On invalid transition: 400 Bad Request
        """
        merchant_id = request.data.get('merchant_id')
        if not merchant_id:
            return Response(
                {'error': 'merchant_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        merchant = get_object_or_404(Merchant, id=merchant_id)
        now = timezone.now()
        
        # Get idempotency key from headers
        idempotency_key = request.headers.get('Idempotency-Key')
        if not idempotency_key:
            return Response(
                {'error': 'Idempotency-Key header is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        for attempt in range(3):
            try:
                # Cleanup expired keys for this merchant/key pair before lookup/create.
                IdempotencyKey.objects.filter(
                    merchant=merchant,
                    key=idempotency_key,
                    expires_at__lte=now
                ).delete()

                # Check for existing idempotency key (active within 24h)
                existing_key = IdempotencyKey.objects.filter(
                    merchant=merchant,
                    key=idempotency_key,
                    expires_at__gt=now
                ).first()
                if existing_key:
                    return Response(existing_key.response_data, status=status.HTTP_200_OK)
                break
            except OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt == 2:
                    raise
                time.sleep(0.05)

        # Validate request data
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount_paise = serializer.validated_data['amount_paise']
        bank_account_id = serializer.validated_data['bank_account_id']

        # Create payout with concurrency control
        try:
            payout = self._create_payout_atomic(
                merchant, amount_paise, bank_account_id, idempotency_key
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Store idempotency key
        response_data = PayoutDetailSerializer(payout).data
        try:
            IdempotencyKey.objects.create(
                merchant=merchant,
                key=idempotency_key,
                payout=payout,
                response_data=self._to_json_safe(response_data),
                expires_at=now + timedelta(hours=24)
            )
        except IntegrityError:
            existing_key = IdempotencyKey.objects.filter(
                merchant=merchant,
                key=idempotency_key,
                expires_at__gt=now
            ).first()
            if existing_key:
                return Response(existing_key.response_data, status=status.HTTP_200_OK)
            raise

        return Response(response_data, status=status.HTTP_201_CREATED)

    def _create_payout_atomic(self, merchant, amount_paise, bank_account_id, idempotency_key):
        """
        Atomically create a payout with balance check.
        
        Uses SELECT FOR UPDATE to lock merchant row while checking balance.
        This prevents race conditions on balance checks.
        
        Race condition scenario (without lock):
        1. Request A: Check balance (100 paise) → OK to debit 60
        2. Request B: Check balance (100 paise) → OK to debit 60
        3. Request A: Create payout for 60, hold funds
        4. Request B: Create payout for 60, hold funds
        Result: 120 paise held but only 100 available! WRONG
        
        With SELECT FOR UPDATE:
        1. Request A: Lock merchant row, check balance (100) → OK, create payout
        2. Request B: Wait for lock, check balance (40 available) → REJECT
        Result: Only one payout created. CORRECT
        """
        retries = 3
        for attempt in range(retries):
            try:
                with transaction.atomic():
                    # Lock merchant row for update - blocks other transactions
                    merchant = Merchant.objects.select_for_update().get(id=merchant.id)

                    # Check available balance (after held amounts)
                    available = merchant.available_balance_paise
                    if available < amount_paise:
                        raise ValueError(
                            f"Insufficient balance. Available: {available} paise, "
                            f"Requested: {amount_paise} paise"
                        )

                    # Create payout in pending state
                    return Payout.objects.create(
                        merchant=merchant,
                        amount_paise=amount_paise,
                        bank_account_id=bank_account_id,
                        status='pending',
                        idempotency_key=None
                    )
            except OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt == retries - 1:
                    raise
                time.sleep(0.05)

    def _to_json_safe(self, payload):
        """Convert serializer output into JSON-safe primitives."""
        return json.loads(json.dumps(payload, cls=DjangoJSONEncoder))

    def get_queryset(self):
        """Filter payouts by merchant if merchant_id query param provided."""
        queryset = Payout.objects.all()
        merchant_id = self.request.query_params.get('merchant')
        if merchant_id:
            queryset = queryset.filter(merchant_id=merchant_id)
        return queryset.order_by('-created_at')

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Get current payout status."""
        payout = self.get_object()
        return Response({
            'id': payout.id,
            'status': payout.status,
            'amount_paise': payout.amount_paise,
            'created_at': payout.created_at,
            'completed_at': payout.completed_at,
            'error_message': payout.error_message,
        })
