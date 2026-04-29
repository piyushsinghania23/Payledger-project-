#!/bin/bash
# Setup script for Payto Payout Engine development

set -e

echo "🚀 Payto Payout Engine - Local Setup"
echo "===================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check prerequisites
echo "${BLUE}Checking prerequisites...${NC}"
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed"
    exit 1
fi
echo "✓ Python 3 found: $(python3 --version)"

if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed"
    exit 1
fi
echo "✓ Node.js found: $(node --version)"

if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed"
    exit 1
fi
echo "✓ npm found: $(npm --version)"

echo ""
echo "${BLUE}Setting up backend...${NC}"

# Create Python virtual environment
if [ ! -d "backend/venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv backend/venv
fi

# Activate virtual environment
source backend/venv/bin/activate

# Install Python dependencies
echo "Installing Python dependencies..."
cd backend
pip install --upgrade pip
pip install -r requirements.txt
cd ..

echo "✓ Backend dependencies installed"

echo ""
echo "${BLUE}Setting up frontend...${NC}"

# Install Node dependencies
echo "Installing Node dependencies..."
cd frontend
npm install
cd ..

echo "✓ Frontend dependencies installed"

echo ""
echo "${BLUE}Initializing database...${NC}"

# Create .env file if it doesn't exist
if [ ! -f "backend/.env" ]; then
    echo "Creating .env file..."
    cat > backend/.env << EOF
DEBUG=True
SECRET_KEY=django-insecure-dev-key-change-in-production
DATABASE_URL=postgresql://payto:payto_dev_pass@localhost:5432/payto
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
EOF
fi

# Run migrations
cd backend
python manage.py migrate
echo "✓ Database migrations complete"

# Seed merchants
echo "Seeding database with merchants..."
python manage.py seed_merchants
echo "✓ Database seeded"
cd ..

echo ""
echo "${GREEN}✓ Setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Start PostgreSQL and Redis:"
echo "   ${BLUE}docker run -d --name payto-postgres -e POSTGRES_PASSWORD=payto_dev_pass -p 5432:5432 postgres:15${NC}"
echo "   ${BLUE}docker run -d --name payto-redis -p 6379:6379 redis:7-alpine${NC}"
echo ""
echo "2. In separate terminals, run:"
echo "   Terminal 1 - Backend: ${BLUE}source backend/venv/bin/activate && cd backend && python manage.py runserver${NC}"
echo "   Terminal 2 - Celery: ${BLUE}source backend/venv/bin/activate && cd backend && celery -A payto worker -l info${NC}"
echo "   Terminal 3 - Frontend: ${BLUE}cd frontend && npm start${NC}"
echo ""
echo "Then visit:"
echo "  Frontend: http://localhost:3000"
echo "  API Docs: http://localhost:8000/api/docs/"
echo "  Admin: http://localhost:8000/admin/"
echo ""
echo "Or use Docker Compose:"
echo "  ${BLUE}docker-compose up${NC}"
echo ""
