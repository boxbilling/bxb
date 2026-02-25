# bxb

<p align="center">
  <strong>Open Source Metering & Usage-Based Billing</strong>
</p>

<p align="center">
  The modern, developer-friendly alternative to Chargebee, Recurly, and Stripe Billing.
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#documentation">Documentation</a> •
  <a href="#contributing">Contributing</a>
</p>

---

## What is bxb?

**bxb** is an open-source billing platform designed for modern SaaS businesses. Whether you need usage-based pricing, subscription billing, or a hybrid of both, bxb provides the infrastructure to build sophisticated billing systems without the complexity.

Inspired by [Lago](https://github.com/getlago/lago), built with Python/FastAPI for reliability and developer productivity.

### Why bxb?

- **🐍 Python/FastAPI**: Modern async Python stack, easy to extend
- **📦 Simple Deployment**: Docker-first, minimal dependencies
- **🔧 Developer First**: OpenAPI spec, auto-generated clients, great DX
- **💰 Any Pricing Model**: Usage-based, subscription, hybrid, volume, graduated
- **🔒 Self-Hosted**: Your data stays on your infrastructure
- **📊 Real-Time Metering**: Instant usage tracking and billing
- **✅ Tested**: Smoke tests included, full suite available separately

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy |
| Frontend | React, TypeScript, Vite, Radix UI |
| Database | PostgreSQL |
| Queue | arq (Redis) |
| Payments | Stripe |

## Features

### Core Billing
- **Usage Metering**: Track and aggregate customer usage in real-time
- **Flexible Plans**: Create plans with any combination of subscription fees and usage charges
- **Multiple Charge Models**: Standard, graduated, volume, package, and percentage pricing
- **Automated Invoicing**: Generate professional invoices automatically

### Pricing Models
- **Subscription-Based**: Fixed recurring fees on any interval
- **Usage-Based**: Pay-as-you-go based on actual consumption
- **Hybrid**: Combine subscriptions with usage charges
- **Tiered/Graduated**: Progressive pricing as usage increases
- **Volume**: Retroactive volume discounts

### Integrations
- **Payment Providers**: Stripe (more coming)
- **Webhooks**: Real-time notifications for billing events
- **REST API**: Comprehensive API for all operations
- **OpenAPI**: Auto-generated TypeScript client

## Quick Start

### Prerequisites

- Python 3.12+ (via [uv](https://docs.astral.sh/uv/))
- Node.js 20+ (via pnpm)
- PostgreSQL 16+
- Redis (for background jobs)

### Using Docker

```bash
# Clone the repository
git clone https://github.com/boxbilling/bxb.git
cd bxb

# Start all services
docker-compose up -d

# API: http://localhost:8000
# Frontend: http://localhost:3000
```

### From Source

```bash
# Clone the repository
git clone https://github.com/boxbilling/bxb.git
cd bxb

# Install dependencies
make install

# Set up environment
cp backend/.env.example backend/.env
# Edit backend/.env with your database URL

# Run database migrations
make migrate

# Start the backend
make dev

# In another terminal, start the frontend
make frontend-dev
```

## Development

### Running Tests

```bash
# Run smoke tests
make test

# Run smoke tests with coverage report
make test-cov

# Run linting
make lint

# Format code
make format
```

### Project Structure

```
bxb/
├── backend/
│   ├── app/
│   │   ├── alembic/        # Database migrations
│   │   ├── core/           # Config, database, deps
│   │   ├── models/         # SQLAlchemy models
│   │   ├── repositories/   # Data access layer
│   │   ├── routers/        # API endpoints
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   └── main.py         # FastAPI app
│   ├── tests/              # Test suite
│   └── pyproject.toml      # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   └── lib/            # Utilities, API client
│   └── package.json        # Node dependencies
├── docker-compose.yml
└── Makefile
```

## API Design

API follows Lago's patterns. Core resources:

- `POST /v1/customers` - Create customer
- `POST /v1/billable_metrics` - Define metered features
- `POST /v1/plans` - Create pricing plans
- `POST /v1/subscriptions` - Subscribe customer to plan
- `POST /v1/events` - Send usage events
- `GET /v1/invoices` - List invoices

See [OpenAPI spec](./backend/openapi.json) for full API documentation.

## Comparison with Alternatives

| Feature | bxb | Lago | Stripe Billing | Chargebee |
|---------|-----|------|----------------|-----------|
| Open Source | ✅ | ✅ | ❌ | ❌ |
| Self-Hosted | ✅ | ✅ | ❌ | ❌ |
| Usage-Based Billing | ✅ | ✅ | ✅ | ✅ |
| Python/FastAPI | ✅ | ❌ (Ruby) | N/A | N/A |
| Smoke Tests Included | ✅ | ✅ | N/A | N/A |
| No Revenue Share | ✅ | ✅ | ❌ | ❌ |

## Contributing

We love contributions! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

### Before Pushing

```bash
make test
make lint
```

## License

bxb is open source under the [AGPL-3.0 License](./LICENSE).

## Acknowledgments

bxb is inspired by [Lago](https://github.com/getlago/lago), an excellent open-source billing platform. We're building on their API design while using a Python stack.

---

<p align="center">
  Built with ❤️ for the developer community
</p>
