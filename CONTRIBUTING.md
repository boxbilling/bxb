# Contributing to bxb

Thank you for your interest in contributing to bxb! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful. Be inclusive. Be helpful.

## Getting Started

### Prerequisites

- Python 3.12+ (we recommend [uv](https://docs.astral.sh/uv/) for package management)
- Node.js 20+ with pnpm
- PostgreSQL 16+
- Redis
- Docker & Docker Compose (optional, for containerized development)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/boxbilling/bxb.git
   cd bxb
   ```

2. **Install dependencies**
   ```bash
   make install
   ```

3. **Set up environment**
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env with your database URL
   ```

4. **Start PostgreSQL and Redis** (using Docker)
   ```bash
   docker-compose up -d postgres redis
   ```

5. **Run migrations**
   ```bash
   make migrate
   ```

6. **Start the development server**
   ```bash
   # Backend (in one terminal)
   make dev
   
   # Frontend (in another terminal)
   make frontend-dev
   ```

## Development Workflow

### Making Changes

1. Create a branch from `main`:
   ```bash
   git checkout -b feat/your-feature
   ```

2. Make your changes

3. **Run tests with coverage check**:
   ```bash
   make test-cov
   ```
   ⚠️ **100% coverage is required.** CI will fail if coverage drops below 100%.

4. **Run linting**:
   ```bash
   make lint
   ```

5. **Format code**:
   ```bash
   make format
   ```

6. Commit your changes:
   ```bash
   git commit -m "feat(scope): description"
   ```

7. Push and open a PR

### Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `test`: Adding/updating tests
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `chore`: Changes to build process, CI, etc.

Examples:
```
feat(customers): add customer CRUD API
fix(invoices): correct tax calculation
docs(readme): update installation instructions
test(events): add batch ingestion tests
```

## Testing Requirements

### 100% Code Coverage

**All code must be tested.** We enforce 100% test coverage via CI.

```bash
# Run tests with coverage
make test-cov

# Run just tests (faster, no coverage)
make test
```

### Writing Tests

Tests live in `backend/tests/`. Structure mirrors the app:

```
tests/
├── conftest.py           # Shared fixtures
├── test_api.py           # Health endpoints
├── test_customers.py     # Customer API
├── test_plans.py         # Plan API
└── test_services/
    └── test_billing.py   # Billing service
```

Example test:
```python
import pytest
from fastapi.testclient import TestClient

class TestCustomerAPI:
    def test_create_customer(self, client: TestClient):
        response = client.post("/v1/customers", json={
            "external_id": "cust_123",
            "name": "Acme Corp",
            "email": "billing@acme.com"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["external_id"] == "cust_123"
        assert data["name"] == "Acme Corp"
    
    def test_create_customer_duplicate(self, client: TestClient):
        # First creation
        client.post("/v1/customers", json={
            "external_id": "cust_dup",
            "name": "Test"
        })
        # Duplicate should fail
        response = client.post("/v1/customers", json={
            "external_id": "cust_dup",
            "name": "Test 2"
        })
        assert response.status_code == 409
```

### Test Fixtures

Common fixtures in `conftest.py`:
- `client`: TestClient instance
- `db`: Database session (auto-cleanup)
- `customer`: Sample customer
- `plan`: Sample plan

## Code Style

### Python

We use **ruff** for linting and formatting (replaces black, isort, flake8).

```bash
# Check linting
make lint

# Auto-format
make format
```

Key rules:
- Line length: 100 characters
- Type hints: Required (mypy strict mode)
- Docstrings: Required for public functions

### TypeScript (Frontend)

- Strict TypeScript
- Functional components with hooks
- API types auto-generated from OpenAPI

## Project Structure

### Backend (`backend/`)

```
app/
├── core/           # Config, database, dependencies
├── models/         # SQLAlchemy models
├── repositories/   # Data access layer
├── routers/        # API endpoints (FastAPI routers)
├── schemas/        # Pydantic request/response models
├── services/       # Business logic
└── main.py         # FastAPI application
```

### Frontend (`frontend/`)

```
src/
├── components/     # Reusable UI components
├── pages/          # Page components
├── lib/
│   ├── api.ts      # API client
│   └── schema.d.ts # Generated types
└── App.tsx
```

## API Design

We follow Lago's API patterns. Key principles:

1. **RESTful**: Standard HTTP methods and status codes
2. **Consistent**: Same patterns across all resources
3. **Idempotent**: POST with external_id/transaction_id for idempotency
4. **Documented**: OpenAPI spec auto-generated from code

### Response Format

Success:
```json
{
  "id": "uuid",
  "external_id": "cust_123",
  "name": "Acme Corp",
  ...
}
```

Error:
```json
{
  "detail": "Customer not found",
  "code": "not_found"
}
```

## Pull Request Process

1. **Ensure all tests pass** with 100% coverage
2. **Update documentation** if needed
3. **Add yourself** to CONTRIBUTORS if this is your first contribution
4. **Request review** from maintainers
5. **Address feedback**
6. **Squash and merge** (maintainers will do this)

## Questions?

- Open an issue for bugs or feature requests
- Start a discussion for questions

Thank you for contributing! 🎉
