# Playto Payout Engine - Technical Explainer

This document explains the critical engineering decisions in the Payout Engine implementation, focusing on the patterns that prevent money-losing bugs.

## 1. The Ledger: Balance Calculation

### Balance Query

```python
# From Merchant.get_balance_paise() in models.py
result = LedgerEntry.objects.filter(merchant=self).aggregate(
    balance=Sum('amount_paise')
)
return result['balance'] or 0
```

### Why This Works

**Database-level aggregation, not Python arithmetic.** 

The balance is calculated entirely at the database layer using SQL `SUM()`. This is critical because:

1. **Atomic consistency**: The database computes the sum in a single SQL statement, not fetching rows and adding them in Python (which could be interrupted).
2. **No floating point**: We use `BigIntegerField` for all amounts (stored as paise, integers). This prevents IEEE 754 rounding errors that plague decimal systems.
3. **Ledger entry model**: Every credit (customer payment) is stored as a positive `amount_paise`. Failed payouts return funds as positive credits, never negative adjustments.

### Data Model Philosophy

```python
class LedgerEntry(models.Model):
    amount_paise = models.BigIntegerField()  # Always positive
    entry_type = models.CharField(max_length=10, choices=[('credit', ...), ('debit', ...)])
```

We do NOT store signed amounts (positive/negative). All amounts are positive integers. The `entry_type` field semantically indicates whether it's a credit or debit. This makes auditing trivial and prevents subtle arithmetic bugs.

**Invariant the system maintains**: 
```
Merchant.balance_paise == SUM(all_ledger_entries.amount_paise WHERE entry_type='credit')
```

This invariant is checked in tests (`TestMerchantBalance`) and must hold after every payout operation.

---

## 2. The Lock: Preventing Concurrent Overdraw

### The Race Condition (Without Locking)

Scenario: Merchant has 100 paise. Two simultaneous requests for 60 paise each.

```
Request A: Check balance (100 paise) → OK to debit 60
Request B: Check balance (100 paise) → OK to debit 60  (BOTH see 100!)
Request A: Create payout for 60, hold funds
Request B: Create payout for 60, hold funds
Result: 120 paise held but only 100 available. MONEY IS LOST.
```

### The Fix: SELECT FOR UPDATE

```python
# From PayoutViewSet._create_payout_atomic() in views.py
@transaction.atomic
def _create_payout_atomic(self, merchant, amount_paise, bank_account_id, idempotency_key):
    # This is the critical line:
    merchant = Merchant.objects.select_for_update().get(id=merchant.id)
    
    # Check available balance (after held amounts)
    available = merchant.available_balance_paise
    if available < amount_paise:
        raise ValueError(f"Insufficient balance...")
    
    # Create payout in pending state
    payout = Payout.objects.create(
        merchant=merchant,
        amount_paise=amount_paise,
        bank_account_id=bank_account_id,
        status='pending',
        idempotency_key=idempotency_key
    )
    return payout
```

### How It Works

**`select_for_update()` uses PostgreSQL's `SELECT ... FOR UPDATE` row-level lock.**

When Request A executes `Merchant.objects.select_for_update().get(id=merchant.id)`, PostgreSQL locks the merchant row. Request B waits. Only after Request A commits/rolls back does Request B's lock acquire:

```
Request A: SELECT ... FROM merchants FOR UPDATE WHERE id=... → LOCK ACQUIRED
Request A: Check balance (100) → OK
Request A: Create payout for 60
Request B: SELECT ... FROM merchants FOR UPDATE WHERE id=... → BLOCKS until A commits
Request A: COMMIT
Request B: SELECT ... FROM merchants FOR UPDATE → LOCK ACQUIRED
Request B: Check balance (40 available) → REJECT (insufficient funds)
Request B: ROLLBACK
Result: Exactly one payout created. Money is safe.
```

### Database Primitive: PostgreSQL Row-Level Locking

`SELECT FOR UPDATE` is a standard SQL feature supported by PostgreSQL. It implements pessimistic locking at the database level:
- Locks are held for the duration of the transaction
- Other transactions block until the lock is released
- Deadlock detection is automatic (PostgreSQL raises an exception)

This is infinitely safer than Python-level locks (threading.Lock) because database locks work across process boundaries and survive application crashes.

### Verification

The test `TestConcurrentPayouts.test_two_concurrent_60k_paise_requests()` verifies this with:
- 100,000 paise merchant balance
- Two simultaneous requests for 60,000 paise each
- Expectation: Exactly 1 succeeds (201), 1 fails (400)
- Assertion: Only 1 payout record exists

---

## 3. The Idempotency: Key Tracking and Replay

### The Idempotency Model

```python
class IdempotencyKey(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    key = models.CharField(max_length=36)  # UUID string
    payout = models.ForeignKey(Payout, on_delete=models.CASCADE)
    response_data = models.JSONField()  # The response to replay
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['merchant', 'key'],
                condition=models.Q(expires_at__gt=timezone.now()),
                name='unique_active_idempotency_key'
            ),
        ]
```

### How It Works

**Request 1: First Time**
```
POST /api/v1/payouts/
Headers: Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
Body: {merchant_id: ..., amount_paise: 50000, ...}

1. Check: Is there an active IdempotencyKey with this merchant + key?
   → No, does not exist (DoesNotExist exception)
   
2. Create payout (with SELECT FOR UPDATE lock on merchant)
   → Payout(id=xyz, merchant=merchant, amount=50000, status='pending')
   
3. Store the idempotency key
   → IdempotencyKey(merchant=merchant, key=550e8400..., payout=xyz, 
                     response_data={...payout serialized...}, 
                     expires_at=now() + 24h)
   
4. Return: 201 Created + payout data
```

**Request 2: Duplicate (same Idempotency-Key, within 24h)**
```
POST /api/v1/payouts/
Headers: Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
Body: {merchant_id: ..., amount_paise: 50000, ...}

1. Check: Is there an active IdempotencyKey with this merchant + key?
   → Yes! found (idempotency_key.expires_at > now())
   
2. Retrieve the original payout
   → payout = idempotency_key.payout
   
3. Return: 200 OK + SAME payout data (no new payout created)
```

### Race: First Request Still in Flight

Critical scenario: Network hangs on first response. Client retries before first commits.

The unique constraint with the `expires_at` condition is the final guard against duplicates.

### Expiration

```python
@shared_task
def cleanup_expired_idempotency_keys():
    """Remove expired idempotency keys (older than 24 hours)."""
    expired_cutoff = timezone.now() - timedelta(hours=24)
    deleted_count, _ = IdempotencyKey.objects.filter(
        expires_at__lt=expired_cutoff
    ).delete()
    return f"Deleted {deleted_count} expired idempotency keys"
```

Runs hourly (via Celery Beat). After 24 hours, the same key can be reused for a different payout if the client wants to.

### Test Verification

`TestIdempotency.test_duplicate_request_returns_same_response()` verifies:
- First request creates payout, returns 201
- Second request with same key returns 200 (not 201)
- Same payout ID in both responses
- Only 1 payout in database

---

## 4. The State Machine: Blocking Invalid Transitions

### The State Diagram (Legal Transitions Only)

```
pending ──→ processing ──→ completed (terminal)
                      ├──→ failed (terminal, returns funds)
```

**Illegal transitions (must be rejected):**
- `completed` → anything (terminal state)
- `failed` → anything (terminal state)
- `pending` → `completed` (must go through processing)
- `pending` → `failed` (must go through processing)

### The Code

```python
# From Payout model in models.py
def can_transition_to(self, new_status):
    """Enforce state machine rules."""
    legal_transitions = {
        'pending': ['processing'],
        'processing': ['completed', 'failed'],
        'completed': [],  # Terminal state
        'failed': [],     # Terminal state
    }
    return new_status in legal_transitions.get(self.status, [])

@transaction.atomic
def transition_to(self, new_status, error_message=''):
    """Safely transition to a new status."""
    if not self.can_transition_to(new_status):
        raise ValidationError(
            f"Cannot transition from {self.status} to {new_status}"
        )
    
    # If transitioning to failed, return funds atomically
    if new_status == 'failed':
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=self.amount_paise,
            entry_type='credit',
            description=f'Payout {self.id} failed, funds returned'
        )
    
    self.status = new_status
    self.updated_at = timezone.now()
    if new_status in ['completed', 'failed']:
        self.completed_at = timezone.now()
    
    self.save()
```

### Blocking `failed` → `completed`

**Answer: In the `can_transition_to()` method.**

```python
legal_transitions = {
    'pending': ['processing'],
    'processing': ['completed', 'failed'],
    'completed': [],  # ← Empty list = terminal
    'failed': [],     # ← Empty list = terminal
}
```

When `payout.status == 'failed'`, the list `legal_transitions.get('failed', [])` returns `[]` (empty). So `can_transition_to('completed')` checks if `'completed' in []` → `False`.

Any code that tries `payout.transition_to('completed')` while status is 'failed' will raise `ValidationError`.

### Atomic Fund Return

Critical: When a payout fails, funds must be returned **atomically with the state change**. This happens in the same `@transaction.atomic` block:

```python
if new_status == 'failed':
    # Create ledger entry inside @transaction.atomic
    LedgerEntry.objects.create(...)

self.status = new_status  # Update status inside same transaction
self.save()
```

If the save fails, the ledger entry is also rolled back. No partial states.

---

## 5. The AI Audit: Catching AI's Mistakes

### Mistake: Python-Level Balance Aggregation Instead of Database Query

**What AI Generated:**
```python
# WRONG - AI wrote this initially
def get_balance_paise(self):
    entries = LedgerEntry.objects.filter(merchant=self)
    balance = sum(entry.amount_paise for entry in entries)  # Python loop!
    return balance
```

**Why This Is Wrong:**
1. **N+1 query performance**: Fetches all rows into Python, then loops
2. **Not atomic for large datasets**: Fetching and summing takes time, vulnerable to concurrent inserts
3. **Memory exhaustion**: For a high-volume merchant with 1M entries, this fails

**What I Replaced It With:**
```python
# CORRECT - Database aggregation
result = LedgerEntry.objects.filter(merchant=self).aggregate(
    balance=Sum('amount_paise')
)
return result['balance'] or 0
```

**Why This Is Right:**
- Single SQL query: `SELECT SUM(amount_paise) FROM ledger_entries WHERE merchant_id = X`
- Atomic: Database guarantees consistency
- Scalable: Works for 1 entry or 1 million entries

---

## Summary: The Three Pillars

1. **Ledger Integrity**: Database-level aggregation, integer arithmetic (paise), immutable ledger entries
2. **Concurrency Safety**: SELECT FOR UPDATE row-level locking, atomic transactions
3. **Idempotency**: Unique constraints, 24-hour expiry, atomic transaction blocks
@transaction.atomic
def _create_payout_atomic(self, merchant, amount_paise, bank_account_id, idempotency_key):
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
    payout = Payout.objects.create(
        merchant=merchant,
        amount_paise=amount_paise,
        bank_account_id=bank_account_id,
        status='pending',
        idempotency_key=idempotency_key
    )

    return payout
```

### Generated SQL
```sql
BEGIN TRANSACTION;
  SELECT * FROM "merchants" WHERE "id" = %s FOR UPDATE;  -- Lock acquired here
  -- Calculate available balance (includes check on held payouts)
  SELECT ... available_balance ...
  -- If check passes, insert payout
  INSERT INTO "payouts" (...) VALUES (...);
COMMIT;  -- Lock released here
```

### Database Primitive: SELECT FOR UPDATE

`SELECT FOR UPDATE` is a PostgreSQL (and MySQL, Oracle) locking mechanism that:
1. Acquires an exclusive lock on the merchant row
2. Other transactions attempting to read/write that row **block** until the lock is released
3. Ensures only one transaction can check and update the balance atomically

### Race Condition Prevented

**Without the lock** (WRONG):
```
Request A: Check balance (100 paise) → OK, can debit 60
Request B: Check balance (100 paise) → OK, can debit 60
Request A: Create payout #1 for 60 paise, held amount = 60
Request B: Create payout #2 for 60 paise, held amount = 120 (WRONG!)
```
Result: 120 paise is held but only 100 exists!

**With SELECT FOR UPDATE (CORRECT)**:
```
Request A: Lock merchant row
Request A: Check balance (100 paise) → OK, create payout for 60
Request A: Release lock
Request B: Lock merchant row (had to wait)
Request B: Check available_balance (now 40) → REJECT, insufficient funds
Request B: Release lock
```
Result: Only one payout created. Balance is safe.

## 3. The Idempotency

### Implementation

```python
# From payto/payout/views.py - PayoutViewSet.create()
def create(self, request, *args, **kwargs):
    merchant_id = request.data.get('merchant_id')
    merchant = get_object_or_404(Merchant, id=merchant_id)
    
    # Get idempotency key from headers
    idempotency_key = request.headers.get('Idempotency-Key')
    
    # Check for existing idempotency key (active within 24h)
    try:
        existing_key = IdempotencyKey.objects.get(
            merchant=merchant,
            key=idempotency_key,
            expires_at__gt=timezone.now()
        )
        # Return same response as original
        payout = existing_key.payout
        serializer = PayoutDetailSerializer(payout)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except IdempotencyKey.DoesNotExist:
        pass
    
    # ... process new request ...
    
    # Store idempotency key with response
    response_data = PayoutDetailSerializer(payout).data
    IdempotencyKey.objects.create(
        merchant=merchant,
        key=idempotency_key,
        payout=payout,
        response_data=response_data,
        expires_at=timezone.now() + timedelta(hours=24)
    )
    
    return Response(response_data, status=status.HTTP_201_CREATED)
```

### Database Schema

```python
class IdempotencyKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    key = models.CharField(max_length=36)  # UUID string
    payout = models.ForeignKey(Payout, on_delete=models.CASCADE)
    response_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['merchant', 'key'],
                condition=models.Q(expires_at__gt=timezone.now()),
                name='unique_active_idempotency_key'
            ),
        ]
```

### How It Knows It's Seen a Key Before

1. **Lookup on second request**: Query `IdempotencyKey` table for the merchant + key combination
2. **Check expiry**: Constraint ensures only active (not expired) keys are unique
3. **Return stored response**: If found, return the payout ID that was created for this key

### In-Flight Request Scenario

**If first request is in flight when second arrives:**

```
Request 1: POST /payouts with key="abc-123"
  - No existing IdempotencyKey found
  - Starts transaction (slow network, server processing)
  
Request 2: POST /payouts with key="abc-123" (user clicked retry)
  - Queries for IdempotencyKey with key="abc-123"
  - Not found yet (Request 1 hasn't committed)
  - Tries to acquire merchant lock
  - BLOCKS waiting for Request 1's transaction to complete
  
Request 1: Completes, inserts IdempotencyKey
  - Commits transaction, lock released
  
Request 2: Acquires lock, recomputes available balance
  - If balance changed, payout might fail
  - If balance still sufficient, creates second payout
```

**Mitigation**: The unique constraint on `(merchant, key)` **with expiry** prevents duplicates even if both requests race. If Request 2 tries to create a new `IdempotencyKey` for the same merchant+key combo, the database constraint throws a unique violation.

## 4. The State Machine

### Legal Transitions

```python
# From payto/payout/models.py - Payout.can_transition_to()
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
```

### Preventing Illegal Transitions

**Failed → Completed (example illegal transition)**:

```python
# In PayoutViewSet or tasks, attempting to complete a failed payout
payout.status = 'failed'
payout.save()

# Later, someone tries:
payout.transition_to('completed')  # Raises ValidationError!
# ValidationError: Cannot transition from failed to completed
```

The check happens in `transition_to()`:

```python
@transaction.atomic
def transition_to(self, new_status, error_message=''):
    if not self.can_transition_to(new_status):
        raise ValidationError(
            f"Cannot transition from {self.status} to {new_status}"
        )
    # ... proceed with transition ...
```

### Atomic Fund Return on Failure

```python
@transaction.atomic
def _fail_payout(payout, error_message):
    """
    Move payout from processing to failed state.
    Return held funds to merchant balance.
    
    This is atomic: status change and fund return happen together or not at all.
    """
    if not payout.can_transition_to('failed'):
        raise ValueError(f"Cannot transition {payout.id} to failed")
    
    # Return funds to merchant (creates new credit entry)
    LedgerEntry.objects.create(
        merchant=payout.merchant,
        amount_paise=payout.amount_paise,
        entry_type='credit',
        description=f'Payout {payout.id} failed: {error_message}'
    )
    
    # Update payout status
    payout.status = 'failed'
    payout.completed_at = timezone.now()
    payout.error_message = error_message
    payout.save()
    # @transaction.atomic ensures both happen together
```

The `@transaction.atomic` decorator ensures:
- Both the ledger entry insert and payout status update happen in the same database transaction
- If either fails, the entire transaction rolls back
- No partial state: either both operations complete or neither does

## 5. The AI Audit

### Issue: Wrong Idempotency Handling

**What AI Suggested (WRONG)**:
```python
def create_payout(request):
    idempotency_key = request.headers.get('Idempotency-Key')
    
    # Check if key exists
    if IdempotencyKey.objects.filter(key=idempotency_key).exists():
        # Return same response
        payout = IdempotencyKey.objects.get(key=idempotency_key).payout
        return Response(PayoutSerializer(payout).data)
    
    # Create new payout
    payout = Payout.objects.create(...)
    IdempotencyKey.objects.create(key=idempotency_key, payout=payout)
    return Response(PayoutSerializer(payout).data, status=201)
```

**Why It's Wrong**:
1. **No merchant scoping**: Keys should be unique per merchant, not globally
2. **No expiry**: Keys are stored forever, causing false positives
3. **Race condition**: Between check and create, another request could insert the same key
4. **No atomic transaction**: Check and insert are separate, allowing duplicates

**Test that Catches It**:
```python
def test_concurrent_same_idempotency_key():
    """Two concurrent requests with same global key would both succeed (WRONG)"""
    key = "abc-123"
    
    # Request 1 checks, finds no key, starts creating payout
    # Request 2 checks, finds no key, also starts creating payout
    # Both insert IdempotencyKey entries - DUPLICATE PAYOUTS CREATED!
```

**What We Implemented (CORRECT)**:
```python
@transaction.atomic
def create_payout_with_idempotency(merchant, amount, key):
    # 1. Scoped per merchant
    try:
        existing = IdempotencyKey.objects.get(
            merchant=merchant,           # ← Merchant scoping
            key=key,
            expires_at__gt=timezone.now()  # ← Expiry check
        )
        return existing.payout  # Replay response
    except IdempotencyKey.DoesNotExist:
        pass
    
    # 2. Create in atomic transaction with constraint
    payout = Payout.objects.create(merchant=merchant, amount=amount)
    
    # Database constraint prevents duplicate (merchant, key) pairs
    IdempotencyKey.objects.create(
        merchant=merchant,
        key=key,
        payout=payout,
        expires_at=timezone.now() + timedelta(hours=24)
    )
    
    return payout
```

**Key Improvements**:
1. **Merchant scoping**: Same merchant can retry with same key, different merchants can use same key
2. **24-hour expiry**: Keys don't accumulate forever, reducing false duplicates
3. **Database constraint**: `UNIQUE(merchant_id, key) WHERE expires_at > NOW()` prevents duplicates
4. **Atomic transaction**: Both operations succeed together or fail together
5. **Test coverage**: Concurrent requests tested explicitly

### How We Caught It

The concurrency test (`test_two_concurrent_60k_paise_requests`) would fail with the AI code:
- Both requests would pass idempotency check (global key doesn't exist yet)
- Both would create payouts (no constraint violation)
- Result: 120 paise held on 100 paise balance (WRONG)

With our implementation:
- Both requests lock the merchant row
- Only one passes the balance check
- Second gets 400 error (insufficient balance)
- Only one payout created (CORRECT)

---

## Summary of Key Patterns

| Pattern | Implementation | Enforces |
|---------|---|---|
| **Money Integrity** | Database-level aggregation, BigIntegerField | No float arithmetic, atomic sums |
| **Concurrency** | SELECT FOR UPDATE locking | Only one transaction checks+updates at a time |
| **Idempotency** | UUID key per merchant, 24h expiry, DB constraint | No duplicates on retry |
| **State Machine** | Method validation + database constraints | Illegal transitions blocked |
| **Fund Returns** | @transaction.atomic on ledger insert + status update | Atomicity on failure |

## Testing Strategy

1. **Unit tests** - Individual model methods work correctly
2. **Concurrency tests** - TransactionTestCase with ThreadPoolExecutor proves race condition fix
3. **Idempotency tests** - Duplicate requests return same response, no duplicates created
4. **Integration tests** - Full flow from request to completion

Run all tests:
```bash
cd backend
pytest tests.py -v
```

Run concurrency tests only:
```bash
pytest tests.py::TestConcurrentPayouts -v
```

Run idempotency tests only:
```bash
pytest tests.py::TestIdempotency -v
```
