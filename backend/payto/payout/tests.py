"""
Tests for the payout engine.

Key test scenarios:
1. Concurrency: Two simultaneous payout requests on same merchant
2. Idempotency: Same payout request repeated returns same response
3. Balance integrity: Balance calculations are always correct
4. State machine: Invalid state transitions are rejected
"""
import uuid
import pytest
from django.test import TestCase, TransactionTestCase
from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import threading

from payto.payout.models import Merchant, Payout, LedgerEntry, IdempotencyKey
from payto.payout.tasks import _complete_payout, _fail_payout, _move_to_processing


@pytest.mark.django_db
class TestMerchantBalance(TestCase):
    """Test merchant balance calculations."""
    
    def setUp(self):
        self.merchant = Merchant.objects.create(
            name='Test Merchant',
            email='test@example.com'
        )
    
    def test_balance_with_no_entries(self):
        """New merchant has zero balance."""
        assert self.merchant.balance_paise == 0
    
    def test_balance_with_single_credit(self):
        """Balance increases with credit entry."""
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=100000,
            entry_type='credit',
            description='Test credit'
        )
        assert self.merchant.balance_paise == 100000
    
    def test_balance_with_multiple_credits(self):
        """Balance sums all credits."""
        for i in range(3):
            LedgerEntry.objects.create(
                merchant=self.merchant,
                amount_paise=100000,
                entry_type='credit',
                description=f'Credit {i}'
            )
        assert self.merchant.balance_paise == 300000
    
    def test_held_balance_pending_payout(self):
        """Held balance includes pending payouts."""
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=100000,
            entry_type='credit',
            description='Initial credit'
        )
        
        Payout.objects.create(
            merchant=self.merchant,
            amount_paise=50000,
            bank_account_id='account123',
            status='pending'
        )
        
        assert self.merchant.balance_paise == 100000
        assert self.merchant.held_balance_paise == 50000
        assert self.merchant.available_balance_paise == 50000
    
    def test_held_balance_processing_payout(self):
        """Held balance includes processing payouts."""
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=100000,
            entry_type='credit',
            description='Initial credit'
        )
        
        Payout.objects.create(
            merchant=self.merchant,
            amount_paise=50000,
            bank_account_id='account123',
            status='processing'
        )
        
        assert self.merchant.held_balance_paise == 50000
        assert self.merchant.available_balance_paise == 50000
    
    def test_held_balance_excludes_completed(self):
        """Held balance excludes completed payouts."""
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=100000,
            entry_type='credit',
            description='Initial credit'
        )
        
        Payout.objects.create(
            merchant=self.merchant,
            amount_paise=50000,
            bank_account_id='account123',
            status='completed'
        )
        
        assert self.merchant.held_balance_paise == 0
        assert self.merchant.available_balance_paise == 100000


@pytest.mark.django_db
class TestPayoutStateMachine(TestCase):
    """Test payout state machine enforcement."""
    
    def setUp(self):
        self.merchant = Merchant.objects.create(
            name='Test Merchant',
            email='test@example.com'
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=100000,
            entry_type='credit',
            description='Initial credit'
        )
        self.payout = Payout.objects.create(
            merchant=self.merchant,
            amount_paise=50000,
            bank_account_id='account123',
            status='pending'
        )
    
    def test_pending_to_processing_allowed(self):
        """Can transition from pending to processing."""
        assert self.payout.can_transition_to('processing')
    
    def test_pending_to_completed_blocked(self):
        """Cannot skip processing and go directly to completed."""
        assert not self.payout.can_transition_to('completed')
    
    def test_pending_to_failed_blocked(self):
        """Cannot skip processing and go directly to failed."""
        assert not self.payout.can_transition_to('failed')
    
    def test_processing_to_completed_allowed(self):
        """Can transition from processing to completed."""
        self.payout.status = 'processing'
        assert self.payout.can_transition_to('completed')
    
    def test_processing_to_failed_allowed(self):
        """Can transition from processing to failed."""
        self.payout.status = 'processing'
        assert self.payout.can_transition_to('failed')
    
    def test_completed_to_anything_blocked(self):
        """Cannot transition from completed state (terminal)."""
        self.payout.status = 'completed'
        assert not self.payout.can_transition_to('pending')
        assert not self.payout.can_transition_to('processing')
        assert not self.payout.can_transition_to('failed')
    
    def test_failed_to_anything_blocked(self):
        """Cannot transition from failed state (terminal)."""
        self.payout.status = 'failed'
        assert not self.payout.can_transition_to('pending')
        assert not self.payout.can_transition_to('processing')
        assert not self.payout.can_transition_to('completed')


@pytest.mark.django_db
class TestFailureReturnsFunds(TestCase):
    """Test that failed payouts return funds to merchant balance."""
    
    def setUp(self):
        self.merchant = Merchant.objects.create(
            name='Test Merchant',
            email='test@example.com'
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=100000,
            entry_type='credit',
            description='Initial credit'
        )
        self.payout = Payout.objects.create(
            merchant=self.merchant,
            amount_paise=50000,
            bank_account_id='account123',
            status='pending'
        )
    
    def test_failed_payout_returns_funds(self):
        """When payout fails, funds are returned to merchant balance."""
        # Move to processing first
        _move_to_processing(self.payout)
        
        initial_balance = self.merchant.balance_paise
        
        # Fail the payout
        _fail_payout(self.payout, "Test failure")
        
        # Check that funds were returned
        self.payout.refresh_from_db()
        assert self.payout.status == 'failed'
        
        # Balance should be back to initial amount
        assert self.merchant.balance_paise == initial_balance + 50000


class TestConcurrentPayouts(TransactionTestCase):
    """
    Test concurrency handling for payout requests.
    
    This test verifies the critical race condition scenario:
    If a merchant has 100 paise and requests two 60 paise payouts simultaneously,
    exactly one should succeed and one should fail.
    
    Without SELECT FOR UPDATE locking, both would succeed (WRONG).
    With locking, only one succeeds (CORRECT).
    """
    
    def setUp(self):
        self.merchant = Merchant.objects.create(
            name='Test Merchant',
            email='test@example.com'
        )
        # Give merchant exactly 100 paise
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=100000,
            entry_type='credit',
            description='Initial credit'
        )
        
        self.client = APIClient()
        self.request_results = []
        self.lock = threading.Lock()
    
    def test_two_concurrent_60k_paise_requests(self):
        """
        Two simultaneous 60k paise requests on 100k paise balance.
        Expected: Exactly one succeeds, one fails.
        """
        def make_payout_request(request_num):
            idempotency_key = str(uuid.uuid4())
            
            response = self.client.post(
                '/api/v1/payouts/',
                {
                    'merchant_id': str(self.merchant.id),
                    'amount_paise': 60000,
                    'bank_account_id': f'account{request_num}'
                },
                HTTP_IDEMPOTENCY_KEY=idempotency_key
            )
            
            with self.lock:
                self.request_results.append({
                    'num': request_num,
                    'status': response.status_code,
                    'key': idempotency_key
                })
        
        # Execute two requests concurrently
        with ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(make_payout_request, 1)
            executor.submit(make_payout_request, 2)
        
        # One request should succeed (201), one should fail (400)
        successes = [r for r in self.request_results if r['status'] == 201]
        failures = [r for r in self.request_results if r['status'] == 400]
        
        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
        assert len(failures) == 1, f"Expected 1 failure, got {len(failures)}"
        
        # Verify only one payout was created
        payouts = Payout.objects.filter(merchant=self.merchant)
        assert payouts.count() == 1
        assert payouts.first().amount_paise == 60000


class TestIdempotency(TransactionTestCase):
    """
    Test idempotency key handling.
    
    Scenario: Client makes same request twice (network retry, browser refresh).
    Expected: Same response returned both times, no duplicate payout created.
    """
    
    def setUp(self):
        self.merchant = Merchant.objects.create(
            name='Test Merchant',
            email='test@example.com'
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=100000,
            entry_type='credit',
            description='Initial credit'
        )
        
        self.client = APIClient()
        self.idempotency_key = str(uuid.uuid4())
    
    def test_duplicate_request_returns_same_response(self):
        """Same idempotency key returns same response without creating duplicate."""
        
        # First request
        response1 = self.client.post(
            '/api/v1/payouts/',
            {
                'merchant_id': str(self.merchant.id),
                'amount_paise': 50000,
                'bank_account_id': 'account123'
            },
            HTTP_IDEMPOTENCY_KEY=self.idempotency_key
        )
        assert response1.status_code == 201
        payout_id_1 = response1.json()['id']
        
        # Second request with same key
        response2 = self.client.post(
            '/api/v1/payouts/',
            {
                'merchant_id': str(self.merchant.id),
                'amount_paise': 50000,
                'bank_account_id': 'account123'
            },
            HTTP_IDEMPOTENCY_KEY=self.idempotency_key
        )
        assert response2.status_code == 200  # 200 OK for replay
        payout_id_2 = response2.json()['id']
        
        # Should be same payout
        assert payout_id_1 == payout_id_2
        
        # Only one payout created
        assert Payout.objects.filter(merchant=self.merchant).count() == 1
    
    def test_different_key_creates_new_payout(self):
        """Different idempotency keys create separate payouts."""
        
        key1 = str(uuid.uuid4())
        key2 = str(uuid.uuid4())
        
        response1 = self.client.post(
            '/api/v1/payouts/',
            {
                'merchant_id': str(self.merchant.id),
                'amount_paise': 30000,
                'bank_account_id': 'account1'
            },
            HTTP_IDEMPOTENCY_KEY=key1
        )
        assert response1.status_code == 201
        
        response2 = self.client.post(
            '/api/v1/payouts/',
            {
                'merchant_id': str(self.merchant.id),
                'amount_paise': 30000,
                'bank_account_id': 'account2'
            },
            HTTP_IDEMPOTENCY_KEY=key2
        )
        assert response2.status_code == 201
        
        # Two separate payouts created
        assert Payout.objects.filter(merchant=self.merchant).count() == 2
    
    def test_idempotency_key_expires_after_24_hours(self):
        """After 24 hours, key expires and creates new payout."""
        
        # Make first request
        response1 = self.client.post(
            '/api/v1/payouts/',
            {
                'merchant_id': str(self.merchant.id),
                'amount_paise': 30000,
                'bank_account_id': 'account1'
            },
            HTTP_IDEMPOTENCY_KEY=self.idempotency_key
        )
        assert response1.status_code == 201
        
        # Manually expire the key
        IdempotencyKey.objects.filter(
            merchant=self.merchant,
            key=self.idempotency_key
        ).update(expires_at=timezone.now() - timedelta(seconds=1))
        
        # Reuse same key - should create new payout since old one expired
        response2 = self.client.post(
            '/api/v1/payouts/',
            {
                'merchant_id': str(self.merchant.id),
                'amount_paise': 30000,
                'bank_account_id': 'account2'
            },
            HTTP_IDEMPOTENCY_KEY=self.idempotency_key
        )
        assert response2.status_code == 201
        
        # Two payouts created
        assert Payout.objects.filter(merchant=self.merchant).count() == 2


@pytest.mark.django_db
class TestInsufficientBalance(TestCase):
    """Test that payouts are rejected when balance is insufficient."""
    
    def setUp(self):
        self.merchant = Merchant.objects.create(
            name='Test Merchant',
            email='test@example.com'
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=50000,  # Only 50k paise
            entry_type='credit',
            description='Initial credit'
        )
        
        self.client = APIClient()
    
    def test_payout_exceeds_balance(self):
        """Payout request exceeding balance is rejected."""
        response = self.client.post(
            '/api/v1/payouts/',
            {
                'merchant_id': str(self.merchant.id),
                'amount_paise': 60000,  # More than available
                'bank_account_id': 'account123'
            },
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())
        )
        assert response.status_code == 400
        assert 'Insufficient balance' in response.json()['error']
    
    def test_payout_respects_held_balance(self):
        """Payout considers held amounts in pending payouts."""
        # Create first payout (pending)
        payout1 = Payout.objects.create(
            merchant=self.merchant,
            amount_paise=40000,
            bank_account_id='account1',
            status='pending'
        )
        
        # Available balance is 50k - 40k = 10k
        # Try to create payout for 20k - should fail
        response = self.client.post(
            '/api/v1/payouts/',
            {
                'merchant_id': str(self.merchant.id),
                'amount_paise': 20000,
                'bank_account_id': 'account2'
            },
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())
        )
        assert response.status_code == 400
