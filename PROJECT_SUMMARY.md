# Project Summary: Playto Payout Engine

## Overview

A production-grade payout engine for the Playto payment platform that handles merchant balance management, payout requests, and bank settlement processing with strong concurrency, idempotency, and data integrity guarantees.

**Stack**: Django + DRF | React + Tailwind | PostgreSQL | Celery + Redis | Docker

---

## 📦 What's Been Built

### Backend (Django)

#### Core Models
- **Merchant**: User accounts with balance tracking
- **LedgerEntry**: Credits (payments) and debits (corrections) in paise
- **Payout**: Payout requests with state machine (pending → processing → completed/failed)
- **IdempotencyKey**: Request deduplication with 24-hour expiry

#### API Endpoints
- `GET /api/v1/merchants/` - List merchants
- `GET /api/v1/merchants/{id}/` - Get merchant details
- `GET /api/v1/merchants/{id}/balance/` - Get balance breakdown
- `GET /api/v1/merchants/{id}/ledger/` - Get transaction history
- `POST /api/v1/payouts/` - Create payout (with Idempotency-Key header)
- `GET /api/v1/payouts/{id}/` - Get payout status
- `GET /api/v1/payouts/` - List payouts

#### Background Jobs (Celery)
- `process_pending_payouts()` - Pick up pending requests (every 10s)
- `process_single_payout()` - Simulate bank settlement (70% success, 20% fail, 10% retry)
- `retry_processing_payouts()` - Retry stuck payouts with exponential backoff
- `cleanup_expired_idempotency_keys()` - Clean up old keys (every hour)

#### Key Features
✅ **Money Integrity**: All amounts in paise (BigIntegerField), no floats
✅ **Concurrency**: SELECT FOR UPDATE locking prevents race conditions
✅ **Idempotency**: UUID per merchant, 24h expiry, database constraints
✅ **State Machine**: Enforced transitions, no illegal states
✅ **Atomic Transactions**: Fund returns on failure are atomic
✅ **Seed Data**: 3 merchants pre-populated with transaction history
✅ **Admin Panel**: Full Django admin for monitoring

### Frontend (React)

#### Components
- **App.js**: Main app with merchant selector
- **MerchantDashboard.js**: Balance display (total, held, available)
- **PayoutForm.js**: Request payout form with validation
- **PayoutHistory.js**: Payout table with live status updates

#### Features
✅ Real-time balance updates
✅ Live payout status polling (every 5 seconds)
✅ Responsive Tailwind CSS design
✅ Error handling and user feedback
✅ Idempotency key generation

### Testing

#### Test Coverage
- **TestMerchantBalance**: Balance calculations with multiple entries
- **TestPayoutStateMachine**: State transition validation
- **TestFailureReturnsFunds**: Fund return on failure
- **TestConcurrentPayouts**: Race condition handling (critical!)
- **TestIdempotency**: Duplicate request handling
- **TestInsufficientBalance**: Balance validation

#### Critical Tests
1. **Concurrency Test**: Two 60 paise payouts on 100 paise balance
   - Expected: 1 success, 1 failure
   - Tests: SELECT FOR UPDATE locking
   
2. **Idempotency Test**: Same request twice with same key
   - Expected: Same response, no duplicate
   - Tests: UUID deduplication, 24h expiry

### Documentation

#### Files Created
- **README.md**: Overview, setup, features
- **QUICK_START.md**: Get running in 5 minutes
- **EXPLAINER.md**: 5 technical deep dives (money, locks, idempotency, state machine, AI audit)
- **API.md**: Complete API documentation with examples
- **DEPLOYMENT.md**: Deploy to Railway, Render, Fly.io, Docker, VPS
- **This file**: Project summary

### Infrastructure

#### Docker
- **docker-compose.yml**: Full stack (Django, Celery, React, PostgreSQL, Redis)
- **backend/Dockerfile**: Python 3.11 + gunicorn
- **frontend/Dockerfile**: Node 18 + React

#### Configuration
- **backend/requirements.txt**: All Python dependencies
- **frontend/package.json**: React dependencies with Tailwind
- **Makefile**: Development commands
- **setup.sh / setup.bat**: One-time setup scripts
- **Procfile**: Heroku/Railway deployment config
- **.github/workflows/ci.yml**: GitHub Actions CI/CD
- **pytest.ini**: Test configuration

#### Environment
- **.env.example**: Template environment variables
- **.gitignore**: Git ignore patterns

---

## 🔑 Key Implementation Details

### 1. The Ledger (Money Integrity)

```python
def get_balance_paise(self):
    result = LedgerEntry.objects.filter(merchant=self).aggregate(
        balance=Sum('amount_paise')
    )
    return result['balance'] or 0
```

**Why This Works**:
- Database-level aggregation (not Python arithmetic)
- No floating-point errors
- Atomic and consistent

### 2. The Lock (Concurrency)

```python
@transaction.atomic
def _create_payout_atomic(self, merchant, amount_paise, ...):
    merchant = Merchant.objects.select_for_update().get(id=merchant.id)
    # Check and create are now atomic
    available = merchant.available_balance_paise
    if available < amount_paise:
        raise ValueError("Insufficient balance")
    Payout.objects.create(...)
```

**Why This Works**:
- `SELECT FOR UPDATE` locks the merchant row
- Other transactions block until lock is released
- Only one can check+create at a time

### 3. Idempotency (Network Resilience)

```python
try:
    existing = IdempotencyKey.objects.get(
        merchant=merchant,
        key=idempotency_key,
        expires_at__gt=timezone.now()
    )
    return existing.payout  # Return same response
except IdempotencyKey.DoesNotExist:
    # Create new payout...
```

**Why This Works**:
- Scoped per merchant (same customer, different merchants OK)
- 24-hour expiry (prevents infinite storage)
- Database constraint prevents duplicates

### 4. State Machine (Business Rules)

```python
def can_transition_to(self, new_status):
    legal_transitions = {
        'pending': ['processing'],
        'processing': ['completed', 'failed'],
        'completed': [],  # Terminal
        'failed': [],     # Terminal
    }
    return new_status in legal_transitions.get(self.status, [])
```

**Why This Works**:
- Centralized validation
- Terminal states can't transition
- Backwards transitions impossible

### 5. Fund Return (Atomic)

```python
@transaction.atomic
def _fail_payout(payout, error_message):
    LedgerEntry.objects.create(...)  # Return funds
    payout.status = 'failed'
    payout.save()
    # Both succeed or both fail
```

**Why This Works**:
- Decorated with `@transaction.atomic`
- Database ensures atomicity
- No partial state

---

## 🚀 Quick Start

### Docker (Easiest)
```bash
docker-compose up
# Visit http://localhost:3000
```

### Local Setup
```bash
bash setup.sh        # macOS/Linux
# or
setup.bat            # Windows

source backend/venv/bin/activate
cd backend && python manage.py runserver  # Terminal 1
cd backend && celery -A payto worker      # Terminal 2
cd frontend && npm start                  # Terminal 3
```

### Run Tests
```bash
cd backend
pytest payto/payout/tests.py -v
pytest payto/payout/tests.py::TestConcurrentPayouts -v
```

---

## 📊 Architecture

```
Internet
   ↓
Nginx/Gunicorn (Port 8000)
   ↓
Django REST API
   ├─ MerchantViewSet
   └─ PayoutViewSet (idempotency, concurrency control)
   ↓
PostgreSQL (Ledger, Payouts, Merchants)
   ↓
Celery Worker
   ├─ process_pending_payouts (every 10s)
   ├─ retry_processing_payouts (every 30s)
   └─ cleanup_expired_idempotency_keys (every 1h)
   ↓
Redis (Task Queue)

React Frontend (Port 3000)
   ├─ Merchant Selector
   ├─ Dashboard (Balances)
   ├─ Payout Form
   └─ Payout History (Live Updates)
```

---

## 📈 Test Results

All tests pass with comprehensive coverage:

```
TestMerchantBalance ✓
  - test_balance_with_no_entries
  - test_balance_with_single_credit
  - test_balance_with_multiple_credits
  - test_held_balance_pending_payout
  - test_held_balance_processing_payout
  - test_held_balance_excludes_completed

TestPayoutStateMachine ✓
  - test_pending_to_processing_allowed
  - test_pending_to_completed_blocked
  - test_processing_to_completed_allowed
  - test_completed_to_anything_blocked
  - test_failed_to_anything_blocked

TestFailureReturnsFunds ✓
  - test_failed_payout_returns_funds

TestConcurrentPayouts ✓ (Critical)
  - test_two_concurrent_60k_paise_requests
  → Proves one succeeds, one fails

TestIdempotency ✓ (Critical)
  - test_duplicate_request_returns_same_response
  - test_different_key_creates_new_payout
  - test_idempotency_key_expires_after_24_hours

TestInsufficientBalance ✓
  - test_payout_exceeds_balance
  - test_payout_respects_held_balance
```

---

## 📁 File Structure

```
payto-payout/
├── README.md                          # Overview
├── QUICK_START.md                    # Get started in 5 minutes
├── EXPLAINER.md                      # Technical deep dives ⭐
├── API.md                            # API documentation
├── DEPLOYMENT.md                     # Deploy guide
├── Makefile                          # Development commands
├── setup.sh / setup.bat              # Setup scripts
├── docker-compose.yml                # Full stack
├── Procfile                          # Deployment config
├── .env.example                      # Template env vars
├── .gitignore                        # Git ignore
│
├── backend/
│   ├── payto/
│   │   ├── payout/
│   │   │   ├── models.py            # ⭐ Data models
│   │   │   ├── views.py             # ⭐ API endpoints
│   │   │   ├── tasks.py             # ⭐ Celery tasks
│   │   │   ├── serializers.py       # DRF serializers
│   │   │   ├── urls.py              # URL routes
│   │   │   ├── admin.py             # Admin panel
│   │   │   ├── tests.py             # ⭐ Test suite
│   │   │   ├── management/
│   │   │   │   └── commands/
│   │   │   │       └── seed_merchants.py
│   │   │   └── __init__.py
│   │   ├── settings.py               # Django settings
│   │   ├── celery.py                 # Celery config
│   │   ├── wsgi.py                   # WSGI app
│   │   ├── urls.py                   # Project URLs
│   │   └── __init__.py
│   ├── manage.py                     # Django CLI
│   ├── requirements.txt              # Dependencies
│   ├── Dockerfile                    # Container
│   ├── pytest.ini                    # Test config
│   └── railway.json                  # Railway deploy
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── MerchantDashboard.js
│   │   │   ├── PayoutForm.js
│   │   │   └── PayoutHistory.js
│   │   ├── App.js
│   │   ├── index.js
│   │   ├── App.css
│   │   └── index.css
│   ├── public/
│   │   └── index.html
│   ├── package.json
│   ├── Dockerfile
│   ├── tailwind.config.js
│   └── postcss.config.js
│
└── .github/
    └── workflows/
        └── ci.yml                    # GitHub Actions
```

---

## 🔐 Security Considerations

### Production Checklist
- [ ] Change `SECRET_KEY`
- [ ] Set `DEBUG=False`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Enable HTTPS/SSL
- [ ] Set up CORS properly
- [ ] Use environment variables for secrets
- [ ] Enable CSRF protection
- [ ] Add rate limiting
- [ ] Set up monitoring/alerts
- [ ] Configure backups
- [ ] Test disaster recovery

### Current Implementation
- ✓ CSRF protection via Django middleware
- ✓ CORS headers configured
- ✓ Secret key in environment
- ✓ Database constraints enforce business rules
- ✓ Atomic transactions prevent data corruption
- ✓ Rate limiting ready (add `djangorestframework-throttling`)

---

## 🎯 Next Steps for Production

1. **Deployment**
   - Choose platform (Railway recommended)
   - Follow [DEPLOYMENT.md](DEPLOYMENT.md)
   - Set up monitoring

2. **Testing**
   - Load test with 1000+ concurrent users
   - Test payout processing at scale
   - Verify database performance

3. **Features**
   - Add WebSocket for real-time updates
   - Implement webhook delivery for status changes
   - Add audit logging for compliance

4. **Monitoring**
   - Set up Sentry for error tracking
   - Add Prometheus metrics
   - Configure PagerDuty alerts

---

## ✅ What Makes This Production-Ready

1. **Money Integrity**
   - All amounts in paise (never floats)
   - Database-level aggregation
   - Invariant checking possible

2. **Concurrency**
   - SELECT FOR UPDATE prevents race conditions
   - Tested with concurrent requests
   - Only one transaction can update balance

3. **Idempotency**
   - UUID per merchant, 24h expiry
   - Database constraints
   - Replay same response on duplicate

4. **Reliability**
   - Exponential backoff on retries
   - Atomic transactions
   - Error handling and logging

5. **Scalability**
   - Celery workers are stateless
   - Database indexed for performance
   - Can run multiple workers

6. **Documentation**
   - EXPLAINER.md answers all technical questions
   - API.md documents all endpoints
   - Code is well-commented

---

## 📞 Support

For questions about specific implementation:
1. Read [EXPLAINER.md](EXPLAINER.md)
2. Check [API.md](API.md) for endpoints
3. Review [DEPLOYMENT.md](DEPLOYMENT.md) for deployment
4. Look at [backend/payto/payout/models.py](backend/payto/payout/models.py) for data model
5. Check [backend/payto/payout/views.py](backend/payto/payout/views.py) for business logic
6. Review [backend/payto/payout/tests.py](backend/payto/payout/tests.py) for test examples

---

**Built with care for payment systems that scale.** 🚀
