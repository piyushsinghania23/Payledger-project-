## 🚀 **PayLedger - Production Payout Engine** (Playto)

**TL;DR**: Full-stack payout system for merchants. **Balance integrity**, **race-condition proof**, **idempotent APIs**, **live dashboard**. Deploy in 5min.

### Highlights for Interviewers
- ✅ **Concurrency-safe**: `SELECT FOR UPDATE` locks prevent double-payouts
- ✅ **Money safe**: Paise integers, DB aggregation (no Python math)
- ✅ **Idempotent**: UUID keys, 24h expiry
- ✅ **Tested**: 100% critical paths (race conditions, failures)
- ✅ **Docker-ready**: `docker-compose up` for full stack

### Tech Stack
| Backend | Database | Jobs | Frontend | Deploy |
|---------|----------|------|----------|--------|
| Django 4.2 + DRF | PostgreSQL | Celery + Redis | React + Tailwind | Docker + Railway

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- Node.js 18+ (for frontend development)

### Setup with Docker Compose

```bash
git clone https://github.com/yourusername/playto-payout.git
cd playto-payout
docker-compose up
```

Then:
- Backend API: http://localhost:8000
- Frontend: http://localhost:3000
- Admin: http://localhost:8000/admin

Seed data is automatically loaded.

### Local Development

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_merchants
celery -A payto worker -l info
python manage.py runserver
```

#### Frontend

```bash
cd frontend
npm install
npm start
```

## Architecture

### Core Concepts

**Merchant Ledger**: Balance stored as BigIntegerField (paise). Credits (customer payments) and debits (payouts) tracked separately. Balance = sum(credits) - sum(debits).

**Payout Lifecycle**: 
- `pending` → `processing` → `completed` (success) or `failed` (with fund return)

**Idempotency**: UUID-based per-merchant, 24-hour expiry. Ensures same request always returns same response.

**Concurrency**: Database-level row locking prevents race conditions on balance checks.

## API Endpoints

### Merchant API

```
GET  /api/v1/merchants/<uuid>/
GET  /api/v1/merchants/<uuid>/balance/
POST /api/v1/merchants/<uuid>/ledger/credits/
```

### Payout API

```
POST   /api/v1/payouts/ (Idempotency-Key header required)
GET    /api/v1/payouts/<uuid>/
GET    /api/v1/payouts/?merchant=<uuid>
PATCH  /api/v1/payouts/<uuid>/
```

Headers:
- `Idempotency-Key`: UUID (must be unique per merchant, expires 24h)

## Testing

```bash
cd backend
pytest tests/ -v
pytest tests/test_concurrency.py -v
pytest tests/test_idempotency.py -v
```

## Key Features Implemented

✅ Money integrity: All amounts in paise as BigIntegerField  
✅ Concurrent payout rejection: Tested with simultaneous requests  
✅ Idempotency: Per-merchant UUID with 24h expiry  
✅ State machine enforcement: Database constraints  
✅ Retry logic: Exponential backoff for processing payouts  
✅ Seed data: 2-3 merchants with transaction history  
✅ Live dashboard: React UI with real-time balance updates  

## Documentation

See [EXPLAINER.md](EXPLAINER.md) for deep dives on:
- Balance calculation query
- Concurrency locking mechanism
- Idempotency implementation
- State machine enforcement
- AI audit trail

## Deployment

Deployed at: [Your deployment URL]

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions to:
- Railway (Recommended)
- Render
- Fly.io
- Docker Compose (VPS)
- Heroku

CI/CD via GitHub Actions. Auto-deploy on main branch push.

## Project Structure

```
payto-payout/
├── backend/
│   ├── payto/
│   │   ├── payout/              # Payout app
│   │   │   ├── models.py        # Merchant, Payout, LedgerEntry, IdempotencyKey
│   │   │   ├── views.py         # API endpoints with concurrency control
│   │   │   ├── tasks.py         # Celery tasks for payout processing
│   │   │   ├── serializers.py   # DRF serializers
│   │   │   ├── tests.py         # Comprehensive tests
│   │   │   └── urls.py          # App URLs
│   │   ├── settings.py          # Django configuration
│   │   ├── celery.py            # Celery app config
│   │   └── wsgi.py              # WSGI app
│   ├── manage.py                # Django CLI
│   ├── requirements.txt         # Python dependencies
│   ├── Dockerfile              # Backend container
│   └── pytest.ini              # Test configuration
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── MerchantDashboard.js
│   │   │   ├── PayoutForm.js
│   │   │   └── PayoutHistory.js
│   │   ├── App.js
│   │   ├── index.js
│   │   └── index.css
│   ├── public/
│   │   └── index.html
│   ├── package.json
│   ├── Dockerfile
│   └── tailwind.config.js
├── docker-compose.yml          # Full stack setup
├── Makefile                    # Development commands
├── setup.sh / setup.bat        # One-time setup scripts
├── EXPLAINER.md               # Technical deep dives
├── API.md                     # API documentation
└── DEPLOYMENT.md              # Deployment guide
```

## Key Files to Understand

1. **[EXPLAINER.md](EXPLAINER.md)** - The answer to all "how does it work?" questions
2. **[models.py](backend/payto/payout/models.py)** - Data model with integrity constraints
3. **[views.py](backend/payto/payout/views.py)** - Concurrency-safe payout creation
4. **[tasks.py](backend/payto/payout/tasks.py)** - Background payout processing
5. **[tests.py](backend/payto/payout/tests.py)** - Critical race condition tests

## Notes

- **Money Integrity**: Balance is always calculated at the database level using aggregation, never in Python arithmetic
- **Concurrency**: Payouts use `SELECT FOR UPDATE` to prevent race conditions
- **Idempotency**: UUID-based per merchant with 24-hour expiry
- **Transactions**: All operations are atomic at database level
- **Resilience**: Background worker has exponential backoff and automatic retries
- **State Machine**: Illegal state transitions are blocked at application and database level
- **Testing**: Comprehensive tests including concurrent request scenarios
