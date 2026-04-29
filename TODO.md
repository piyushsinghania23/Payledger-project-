# PayLedger Debug TODO

## Approved Debug Plan Steps

### 1. Run Backend Tests [COMPLETE - see terminal]
### 2. Local Setup [COMPLETE - venv, .env, migrations, seeds]
### 3. Docker [SKIPPED - not installed]

### 4. Run Backend + Celery
- Terminal1: `cd backend && python manage.py runserver`
- Terminal2: `cd backend && celery -A payto worker -l info`

### 5. Run Frontend
- Terminal3: `cd frontend && npm install && npm start`

### 6. Test Flow
- Visit localhost:3000
- Create payout, verify processing via Celery (70% success)

### 7. Fix Configs (if errors)
- Secure SECRET_KEY
- ALLOWED_HOSTS=['localhost','127.0.0.1']

### 8. Completion
- All services running
- Payout flow works

