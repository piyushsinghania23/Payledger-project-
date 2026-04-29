# Quick Start Guide

Get the Playto Payout Engine running in 5 minutes.

## Option 1: Docker Compose (Easiest)

### Prerequisites
- Docker and Docker Compose installed

### Run
```bash
docker-compose up
```

That's it! 🎉

**Wait for startup** (watch for "seed_merchants" output), then visit:
- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/api/docs/
- **Admin Panel**: http://localhost:8000/admin/

**Default admin login** (if needed):
- Username: `admin`
- Password: (created automatically, check logs)

---

## Option 2: Local Development Setup

### Prerequisites
- Python 3.11+
- Node 18+
- PostgreSQL
- Redis

### Setup

**One-time setup**:
```bash
# Windows
setup.bat

# macOS/Linux
bash setup.sh
```

**Start services** (3 terminals):

Terminal 1 - Backend:
```bash
source backend/venv/bin/activate  # Windows: backend\venv\Scripts\activate
cd backend
python manage.py runserver
```

Terminal 2 - Celery:
```bash
source backend/venv/bin/activate  # Windows: backend\venv\Scripts\activate
cd backend
celery -A payto worker -l info
```

Terminal 3 - Frontend:
```bash
cd frontend
npm start
```

Visit http://localhost:3000

---

## Running Tests

```bash
# All tests
cd backend
pytest payto/payout/tests.py -v

# Concurrency test only
pytest payto/payout/tests.py::TestConcurrentPayouts -v

# Idempotency test only
pytest payto/payout/tests.py::TestIdempotency -v
```

---

## First Steps

1. **Open dashboard**: http://localhost:3000
2. **Select a merchant** from the dropdown
3. **View balance**: Shows total, held, and available amounts
4. **Request payout**: 
   - Enter amount (in rupees)
   - Enter bank account ID
   - Click "Request Payout"
5. **Watch status**: Status updates every 5 seconds
   - Pending → Processing → Completed/Failed

---

## Key Features to Try

### 1. View Merchant Balance
```bash
curl http://localhost:8000/api/v1/merchants/
```

### 2. Create a Payout
```bash
curl -X POST http://localhost:8000/api/v1/payouts/ \
  -H "Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000" \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_id": "<merchant-uuid>",
    "amount_paise": 50000,
    "bank_account_id": "ACCOUNT123"
  }'
```

### 3. Idempotency (Run Same Request Twice)
```bash
# First request
curl -X POST http://localhost:8000/api/v1/payouts/ ... \
  -H "Idempotency-Key: abc-123"

# Second request (same key)
curl -X POST http://localhost:8000/api/v1/payouts/ ... \
  -H "Idempotency-Key: abc-123"
# Returns 200 with same response as first (no duplicate created!)
```

### 4. Insufficient Balance (Try This)
Create a payout request for more than the available balance:
- You'll get a 400 error: "Insufficient balance"
- No payout created
- Balance protected

### 5. Watch Payout Processing
- Create a payout → Status: `pending`
- Wait 10 seconds → Status: `processing`
- Wait 10 more seconds → Status: `completed` or `failed`
  - 70% succeed
  - 20% fail (funds returned)
  - 10% hang and retry

---

## Admin Panel

Visit http://localhost:8000/admin/ to:
- View all merchants and their balances
- See ledger entries (credits and debits)
- Track all payouts and their status
- Monitor idempotency keys

Create a superuser:
```bash
cd backend
python manage.py createsuperuser
```

---

## Stopping Services

**Docker Compose**:
```bash
docker-compose down
```

**Local Development**:
- Ctrl+C in each terminal
- Kill any lingering processes (celery, django)

---

## Troubleshooting

### Ports Already in Use
```bash
# Change ports in docker-compose.yml or Makefile
```

### Database Connection Error
```bash
# Ensure PostgreSQL and Redis are running
docker ps  # Check if containers are up
docker-compose logs db  # Check database logs
```

### Python Module Not Found
```bash
# Reinstall dependencies
pip install -r backend/requirements.txt
```

### Celery Tasks Not Processing
```bash
# Check celery logs
docker-compose logs celery

# Restart celery worker
docker-compose restart celery
```

---

## Next Steps

1. Read [EXPLAINER.md](EXPLAINER.md) for technical details
2. Check [API.md](API.md) for all API endpoints
3. Explore [DEPLOYMENT.md](DEPLOYMENT.md) to deploy live
4. Review [backend/payto/payout/tests.py](backend/payto/payout/tests.py) for testing patterns
5. Check [backend/payto/payout/models.py](backend/payto/payout/models.py) for data model

---

## Support

- **Frontend issues**: Check browser console (F12)
- **Backend errors**: Check `docker-compose logs backend`
- **Database issues**: Check `docker-compose logs db`
- **Celery problems**: Check `docker-compose logs celery`

For detailed documentation, see the files mentioned above! 🚀
