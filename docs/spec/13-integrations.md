---
type: spec
title: "Integrations Specification"
created: 2026-02-11
tags:
  - spec
  - integrations
  - netsuite
  - xero
  - salesforce
  - P3
related:
  - "[[00-overview]]"
  - "[[06-tax-system]]"
  - "[[10-multi-tenancy]]"
---

# Integrations Specification

## Overview

The integration system provides a pluggable adapter architecture for connecting bxb to external services: accounting systems (NetSuite, Xero), CRM platforms (HubSpot, Salesforce), tax providers (Anrok, Avalara), and SSO providers (Okta). Each integration follows a base provider pattern with standardized mapping and customer synchronization.

## Lago Reference

Sources: `app/models/integration.rb` (and subtypes), `app/models/integration_mapping.rb` (and subtypes), `app/models/integration_customer.rb` in the Lago codebase. IntegrationMappable concern adds mapping relationships to AddOn and BillableMetric.

## Architecture

### Base Provider Pattern

```
IntegrationBase (abstract)
├── Integrations::NetsuiteIntegration
├── Integrations::XeroIntegration
├── Integrations::HubspotIntegration
├── Integrations::SalesforceIntegration
├── Integrations::AnrokIntegration
├── Integrations::AvalaraIntegration
└── Integrations::OktaIntegration
```

Each integration subclass implements:
- Connection configuration (API keys, OAuth tokens)
- Data synchronization methods
- Webhook handling for real-time updates

## Entities

### Table: `integrations`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique integration identifier |
| `organization_id` | UUID | FK -> organizations, NOT NULL, indexed | Owning organization |
| `type` | String(50) | NOT NULL | Integration subtype discriminator |
| `code` | String(255) | NOT NULL | Lookup code |
| `name` | String(255) | NOT NULL | Display name |
| `settings` | JSON | NOT NULL, default {} | Provider-specific configuration |
| `secrets` | JSON | NOT NULL, default {} | Encrypted credentials |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

**Unique Constraint:** `(organization_id, code)`

### Table: `integration_mappings`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique mapping identifier |
| `integration_id` | UUID | FK -> integrations, NOT NULL, indexed | Parent integration |
| `mappable_type` | String(50) | NOT NULL | Polymorphic type (AddOn, BillableMetric, etc.) |
| `mappable_id` | UUID | NOT NULL | Polymorphic ID |
| `external_id` | String(255) | nullable | ID in external system |
| `external_account_code` | String(255) | nullable | Account code in external system |
| `external_name` | String(255) | nullable | Name in external system |
| `settings` | JSON | NOT NULL, default {} | Mapping-specific settings |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

### Table: `integration_collection_mappings`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique mapping identifier |
| `integration_id` | UUID | FK -> integrations, NOT NULL, indexed | Parent integration |
| `mapping_type` | String(50) | NOT NULL | Type of collection (invoice, payment, etc.) |
| `external_id` | String(255) | nullable | External collection ID |
| `external_account_code` | String(255) | nullable | External account code |
| `external_name` | String(255) | nullable | External collection name |
| `settings` | JSON | NOT NULL, default {} | Collection-specific settings |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

### Table: `integration_customers`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique identifier |
| `customer_id` | UUID | FK -> customers, NOT NULL, indexed | bxb customer |
| `integration_id` | UUID | FK -> integrations, NOT NULL, indexed | Integration |
| `type` | String(50) | NOT NULL | Customer subtype discriminator |
| `external_customer_id` | String(255) | nullable | Customer ID in external system |
| `settings` | JSON | NOT NULL, default {} | Provider-specific customer settings |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

## Planned Providers

### Accounting

**NetSuite**
- Sync invoices, credit notes, payments
- Map bxb entities to NetSuite items/accounts
- Real-time or batch synchronization

**Xero**
- Sync invoices, credit notes, payments
- Map bxb entities to Xero accounts
- OAuth2 authentication

### CRM

**HubSpot**
- Sync customer data bidirectionally
- Associate subscriptions and invoices with HubSpot deals
- Webhook-driven updates

**Salesforce**
- Sync customer and subscription data
- Map to Salesforce accounts and opportunities
- OAuth2 authentication

### Tax

**Anrok**
- Real-time tax calculation during invoice generation
- Replaces built-in tax calculation (see [[06-tax-system]])
- Supports US sales tax, EU VAT, and international taxes

**Avalara**
- Real-time tax rate lookup and calculation
- Tax document generation and filing
- Address validation

### SSO

**Okta**
- SAML/OIDC authentication for dashboard access
- User provisioning and deprovisioning
- Role mapping

## API Endpoints

### Integrations
- `POST /v1/integrations` — Create integration
- `GET /v1/integrations` — List integrations
- `GET /v1/integrations/{id}` — Get integration
- `PUT /v1/integrations/{id}` — Update integration
- `DELETE /v1/integrations/{id}` — Delete integration

### Integration Mappings
- `POST /v1/integration_mappings` — Create mapping
- `GET /v1/integration_mappings` — List mappings (filter by integration_id)
- `PUT /v1/integration_mappings/{id}` — Update mapping
- `DELETE /v1/integration_mappings/{id}` — Delete mapping
