- **Clone the github repository**
- **Populate the env file with correct values**

# Install dependencies and sync the virtual environment

uv sync

# Run database migrations

uv run alembic upgrade head

# Start the Celery worker (in a new terminal tab)

uv run celery -A src.tasks.celery_app worker --pool=solo --loglevel=info

# Start the FastAPI backend from project root

uv run uvicorn src.main:app

# Frontend Setup

cd FRONTEND/

npm install

npm run dev
