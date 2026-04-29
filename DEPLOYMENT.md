# Deployment Guide

This guide covers deploying the Playto Payout Engine to various platforms.

## Prerequisites

- Git account (GitHub, GitLab, Bitbucket)
- Platform account (Railway, Render, Fly.io, or Heroku)
- Docker installed locally (optional, for testing deployment)

## Quick Deploy to Railway (Recommended)

Railway is the **easiest and fastest option** for this project.

### Step 1: Create GitHub Repository

```bash
cd payto-payout
git init
git add .
git commit -m "Initial commit: Playto Payout Engine"
git branch -M main
git remote add origin https://github.com/yourusername/payto-payout.git
git push -u origin main
```

### Step 2: Deploy to Railway

1. Go to [Railway.app](https://railway.app)
2. Click **"New Project"**
3. Select **"Deploy from GitHub"**
4. Authorize Railway to access your GitHub account
5. Select your `payto-payout` repository
6. Click **"Deploy"**

Railway will:
- Auto-detect your `Dockerfile`
- Build and deploy the backend service
- Create a PostgreSQL database automatically
- Create a Redis cache automatically
- Assign a public URL

### Step 3: Run Migrations

Once deployed:
1. Click your project in Railway
2. Click the **"backend"** service
3. Go to the **"Deploy"** tab
4. Click **"View Logs"**
5. In the logs, you should see:
   ```
   Running migrations...
   Seeding merchants...
   ```

If migrations haven't run, manually trigger them:
1. Go to **Settings** → **Environment**
2. Add or modify the `START_COMMAND`:
   ```
   bash -c "python manage.py migrate && python manage.py seed_merchants && gunicorn payto.wsgi --bind 0.0.0.0:8000"
   ```
3. Redeploy

### Step 4: Set Environment Variables

In Railway dashboard:
1. Click your project
2. Go to **Settings** → **Environment**
3. Add these variables:

```
DEBUG=False
SECRET_KEY=<generate-a-random-string>
DATABASE_URL=<auto-filled-by-railway>
REDIS_URL=<auto-filled-by-railway>
CELERY_BROKER_URL=<redis-url>
CELERY_RESULT_BACKEND=<redis-url>
```

### Step 5: Get Your Deployment URL

In Railway:
1. Click the **"backend"** service
2. Go to the **"Deployments"** tab
3. Your public URL will be shown at the top, e.g., `https://payto-payout-production.up.railway.app`
4. The frontend is accessible at `/` (served from the same domain)

### Step 6: Test Your Deployment

Open your browser and visit:
```
https://payto-payout-production.up.railway.app
```

You should see:
- Merchant dashboard
- Payout form
- Payout history table
- Live status updates

---

## Alternative: Deploy to Render

Render is another excellent free option with generous free tier.

### Steps

1. Go to [Render.com](https://render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Set these values:
   - **Name**: `payto-payout`
   - **Environment**: `Docker`
   - **Branch**: `main`
   - **Build Command**: Leave empty (uses Dockerfile)

5. Add PostgreSQL:
   - Click **"Create Database"**
   - Name: `payto-db`

6. Add Redis:
   - Click **"New +"** → **"Redis"**
   - Name: `payto-redis`

7. Set Environment Variables:
   ```
   DEBUG=False
   SECRET_KEY=<generate-random>
   CELERY_BROKER_URL=<redis-connection-string>
   CELERY_RESULT_BACKEND=<redis-connection-string>
   ```

8. Click **"Create Web Service"**

Render will deploy automatically. Your URL will be assigned and shown on the service page.

---

## Alternative: Deploy to Fly.io

Fly.io offers a generous free tier and global deployment.

### Steps

1. Install Fly CLI:
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. Sign up and log in:
   ```bash
   flyctl auth signup
   flyctl auth login
   ```

3. Launch your app:
   ```bash
   flyctl launch
   ```
   Choose:
   - App name: `payto-payout`
   - Region: Closest to you
   - Postgres: Yes
   - Redis: Yes

4. Deploy:
   ```bash
   flyctl deploy
   ```

5. Get your URL:
   ```bash
   flyctl status
   ```

Your app will be at `https://payto-payout.fly.dev`

---

## Local Testing Before Deployment

To test the full stack locally before deploying:

```bash
docker-compose up --build
```

Then visit:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/api/v1
- **Admin**: http://localhost:8000/admin (username: admin, password: admin)
- **API Docs**: http://localhost:8000/api/docs

---

## Post-Deployment Checklist

After deploying, verify:

- [ ] Frontend loads at root URL
- [ ] Merchant list shows seeded merchants
- [ ] Can request a payout
- [ ] Payout status updates live (check every 5 seconds)
- [ ] Admin panel is accessible
- [ ] Celery worker is running (check logs for "ready to accept tasks")
- [ ] Background tasks are processing (check payout status changes)

---

## Environment Variables Reference

| Variable | Example | Purpose |
|----------|---------|---------|
| `DEBUG` | `False` | Disable debug mode in production |
| `SECRET_KEY` | `django-insecure-xyz` | Django secret key (generate new one) |
| `DATABASE_URL` | `postgresql://user:pass@host:5432/db` | PostgreSQL connection |
| `REDIS_URL` | `redis://host:6379/0` | Redis cache & Celery broker |
| `CELERY_BROKER_URL` | Same as `REDIS_URL` | Celery message broker |
| `CELERY_RESULT_BACKEND` | Same as `REDIS_URL` | Celery result storage |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1,yourdomain.com` | Allowed hosts (comma-separated) |

---

## Troubleshooting

### "ModuleNotFoundError" on Deploy

**Cause**: Python dependencies not installed
**Fix**: Make sure `requirements.txt` is in the `backend/` directory

### "No such database table"

**Cause**: Migrations haven't run
**Fix**: In deploy logs, ensure you see "Running migrations..." If not, manually trigger migrations in your platform's dashboard

### Celery Worker Not Running

**Cause**: Redis URL not configured
**Fix**: Verify `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` environment variables in your platform

### Frontend Shows Blank Page

**Cause**: API URL not set correctly
**Fix**: In your platform, verify `REACT_APP_API_URL` is set to your backend's full URL

---

## Generate a Strong SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Use this output as your `SECRET_KEY` in production.
   CELERY_RESULT_BACKEND=<redis-url>
   ```

6. **Run Migrations**
   - Go to Postgres service → "Data" tab
   - Open web terminal
   - Run database migrations:
   ```bash
   python backend/manage.py migrate
   python backend/manage.py seed_merchants
   ```

7. **Your URL**
   - Backend: `https://payto-backend-production.up.railway.app`
   - Swagger Docs: `https://payto-backend-production.up.railway.app/api/docs/`

## Option 2: Render

### Steps

1. **Create Repository** (same as Railway)

2. **Deploy on Render**
   - Go to https://render.com
   - Click "New +" → "Web Service"
   - Connect GitHub repository
   - Select backend directory
   - Set build command: `pip install -r requirements.txt`
   - Set start command: `gunicorn payto.wsgi --bind 0.0.0.0:$PORT`

3. **Add PostgreSQL**
   - Click "New +" → "PostgreSQL"
   - Set database name, user, password
   - Link to your web service

4. **Add Redis**
   - Click "New +" → "Redis"
   - Link to your web service

5. **Environment Variables**
   ```
   DEBUG=False
   SECRET_KEY=<generate-strong-secret>
   DATABASE_URL=postgresql://...
   REDIS_URL=redis://...
   ```

6. **Deploy Worker**
   - Create new Web Service for Celery worker
   - Start command: `celery -A payto worker -l info`

## Option 3: Fly.io

### Steps

1. **Install Fly CLI**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Login**
   ```bash
   flyctl auth login
   ```

3. **Create App**
   ```bash
   flyctl apps create payto-payout
   ```

4. **Deploy**
   ```bash
   flyctl deploy
   ```

5. **Add Postgres**
   ```bash
   flyctl postgres create --name payto-db
   flyctl postgres attach payto-db
   ```

6. **Run Migrations**
   ```bash
   flyctl ssh console
   cd backend
   python manage.py migrate
   python manage.py seed_merchants
   ```

## Option 4: Docker Compose (Local/VPS)

### Local Development

```bash
docker-compose up -d
```

This starts:
- PostgreSQL on port 5432
- Redis on port 6379
- Django on port 8000
- Celery worker (background)
- React on port 3000

### VPS Deployment

1. **SSH into your VPS**
   ```bash
   ssh user@your-vps-ip
   ```

2. **Install Docker and Docker Compose**
   ```bash
   # Ubuntu/Debian
   curl -fsSL https://get.docker.com -o get-docker.sh | sh
   sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

3. **Clone Repository**
   ```bash
   git clone https://github.com/yourusername/payto-payout.git
   cd payto-payout
   ```

4. **Create .env File**
   ```bash
   cp .env.example .env
   # Edit .env with your values
   nano .env
   ```

5. **Start Services**
   ```bash
   docker-compose up -d
   ```

6. **Check Logs**
   ```bash
   docker-compose logs -f backend
   ```

## Option 5: Heroku (Deprecated, Use Railway Instead)

Heroku free tier was discontinued, but you can still use paid dynos:

1. **Install Heroku CLI**
2. **Login**: `heroku login`
3. **Create App**: `heroku create payto-payout`
4. **Add PostgreSQL**: `heroku addons:create heroku-postgresql:mini`
5. **Add Redis**: `heroku addons:create heroku-redis:mini`
6. **Deploy**: `git push heroku main`
7. **Migrate**: `heroku run python backend/manage.py migrate`

## Monitoring and Logging

### Check Service Status

```bash
# Railway
railway logs

# Render
tail -f logs from dashboard

# Fly.io
flyctl logs

# Docker Compose
docker-compose logs -f backend
docker-compose logs -f celery
```

### View Metrics

- **Railway**: Built-in dashboard
- **Render**: Metrics tab
- **Fly.io**: `flyctl status`
- **VPS**: Use Prometheus + Grafana

## Database Backups

### Railway/Render
- Automatic daily backups
- Manual backup via dashboard

### Self-Hosted
```bash
# Backup
docker-compose exec db pg_dump -U payto payto > backup.sql

# Restore
docker-compose exec -T db psql -U payto payto < backup.sql
```

## SSL/HTTPS

All major platforms (Railway, Render, Fly.io) provide free SSL certificates.

For self-hosted, use:
```bash
# Nginx + Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d yourdomain.com
```

## Scaling

### Horizontal Scaling
- Deploy multiple Celery workers
- Use load balancer (Nginx, HAProxy)
- Scale database with connection pooling

### Vertical Scaling
- Increase dynos/instances
- Upgrade database tier

## Performance Optimization

1. **Database Indexes**
   - Already configured in models
   - Monitor slow queries: `EXPLAIN ANALYZE`

2. **Caching**
   - Implement Redis caching for frequently accessed data
   - Cache merchant balance for 5-10 seconds

3. **Connection Pooling**
   - Use PgBouncer for PostgreSQL
   - Redis connection pool (built-in)

4. **Celery Settings**
   ```python
   CELERY_WORKER_PREFETCH_MULTIPLIER = 1
   CELERY_TASK_ACKS_LATE = True
   CELERYD_MAX_TASKS_PER_CHILD = 1000
   ```

## Troubleshooting

### 500 Error
```bash
docker-compose logs backend
```

### Migration Errors
```bash
docker-compose exec backend python manage.py migrate --fake-initial
```

### Celery Not Processing
```bash
docker-compose logs celery
docker-compose restart celery
```

### Database Connection
```bash
docker-compose exec backend python manage.py dbshell
```

## Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Generate strong `SECRET_KEY`
- [ ] Configure allowed hosts
- [ ] Set up CORS correctly
- [ ] Enable HTTPS
- [ ] Configure email backend
- [ ] Set up monitoring/alerts
- [ ] Configure backups
- [ ] Test disaster recovery
- [ ] Set up error tracking (Sentry)
- [ ] Configure logging
- [ ] Load test before launch
