# bxb-portal

Python SDK for the [bxb](https://github.com/boxbilling/bxb) customer portal API.

This package contains only the portal endpoints, intended for customer-facing applications that need self-service access to billing data.

## Installation

```bash
pip install bxb-portal
```

## Usage

```python
import bxb_portal

config = bxb_portal.Configuration(host="https://your-bxb-instance.com")
client = bxb_portal.ApiClient(config)
```

## Authentication

The portal API uses JWT tokens passed as a query parameter. See the main bxb documentation for details on generating portal tokens.

## Documentation

- [GitHub Repository](https://github.com/boxbilling/bxb)
- [API Reference](https://github.com/boxbilling/bxb/blob/main/backend/openapi.json)

## License

AGPL-3.0
