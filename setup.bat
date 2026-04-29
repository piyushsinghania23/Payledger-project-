@echo off
REM Setup script for Payto Payout Engine development (Windows)

echo.
echo 🚀 Payto Payout Engine - Local Setup (Windows)
echo ===============================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed or not in PATH
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo ✓ Python found: %PYTHON_VERSION%

REM Check Node
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Node.js is not installed or not in PATH
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
echo ✓ Node.js found: %NODE_VERSION%

REM Check npm
npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ npm is not installed or not in PATH
    exit /b 1
)
for /f "tokens=*" %%i in ('npm --version') do set NPM_VERSION=%%i
echo ✓ npm found: %NPM_VERSION%

echo.
echo Setting up backend...

REM Create Python virtual environment
if not exist "backend\venv" (
    echo Creating Python virtual environment...
    python -m venv backend\venv
)

REM Activate virtual environment
call backend\venv\Scripts\activate.bat

REM Install Python dependencies
echo Installing Python dependencies...
cd backend
pip install --upgrade pip
pip install -r requirements.txt
cd ..

echo ✓ Backend dependencies installed

echo.
echo Setting up frontend...

REM Install Node dependencies
echo Installing Node dependencies...
cd frontend
call npm install
cd ..

echo ✓ Frontend dependencies installed

echo.
echo Initializing database...

REM Create .env file if it doesn't exist
if not exist "backend\.env" (
    echo Creating .env file...
    (
        echo DEBUG=True
        echo SECRET_KEY=django-insecure-dev-key-change-in-production
        echo DATABASE_URL=postgresql://payto:payto_dev_pass@localhost:5432/payto
        echo REDIS_URL=redis://localhost:6379/0
        echo CELERY_BROKER_URL=redis://localhost:6379/0
        echo CELERY_RESULT_BACKEND=redis://localhost:6379/0
    ) > backend\.env
)

REM Run migrations
cd backend
python manage.py migrate
echo ✓ Database migrations complete

REM Seed merchants
echo Seeding database with merchants...
python manage.py seed_merchants
echo ✓ Database seeded
cd ..

echo.
echo ✓ Setup complete!
echo.
echo Next steps:
echo 1. Start PostgreSQL and Redis using Docker:
echo    docker run -d --name payto-postgres -e POSTGRES_PASSWORD=payto_dev_pass -p 5432:5432 postgres:15
echo    docker run -d --name payto-redis -p 6379:6379 redis:7-alpine
echo.
echo 2. In separate terminals, run:
echo    Terminal 1 - Backend: backend\venv\Scripts\activate ^&^& cd backend ^&^& python manage.py runserver
echo    Terminal 2 - Celery: backend\venv\Scripts\activate ^&^& cd backend ^&^& celery -A payto worker -l info
echo    Terminal 3 - Frontend: cd frontend ^&^& npm start
echo.
echo Then visit:
echo   Frontend: http://localhost:3000
echo   API Docs: http://localhost:8000/api/docs/
echo   Admin: http://localhost:8000/admin/
echo.
echo Or use Docker Compose:
echo   docker-compose up
echo.
