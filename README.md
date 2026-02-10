# Template

Opinionated web project template for building projects with AI.

## Backend Tech Stack

- **Framework**: FastAPI
- **Python**: 3.12+
- **Package Manager**: uv
- **Database**: PostgreSQL (SQLAlchemy + psycopg2)
- **Validation**: Pydantic
- **DB Migrations**: alembic
- **Task Queue**: arq
- **HTTP Client**: httpx

## Rules before each commit

1. Test must pass: run `make test` and fix any errors.
2. Run `make lint` to check code style.
3. Run `make openapi` to generate new OpenAPI schema.