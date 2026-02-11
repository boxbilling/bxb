---
type: spec
title: "Multi-Tenancy Specification"
created: 2026-02-11
tags:
  - spec
  - multi-tenancy
  - organization
  - billing-entity
  - P1
related:
  - "[[00-overview]]"
  - "[[06-tax-system]]"
  - "[[07-webhooks]]"
  - "[[11-dunning-and-payments]]"
---

# Multi-Tenancy Specification

## Overview

Multi-tenancy introduces the Organization as the top-level tenant and BillingEntity as a sub-tenant. Currently, bxb operates as a single-tenant system. Lago's architecture scopes all resources (customers, subscriptions, invoices, etc.) under an organization, with optional billing entities for companies that invoice from multiple legal entities.

## Lago Reference

Sources: `app/models/organization.rb`, `app/models/billing_entity.rb` in the Lago codebase. Organization includes PaperTrailTraceable, OrganizationTimezone, Currencies, AuthenticationMethods, HasFeatureFlags. BillingEntity supports its own document numbering, tax defaults, and branding.

## Entities

### Table: `organizations`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique organization identifier |
| `name` | String(255) | NOT NULL | Organization name |
| `default_currency` | String(3) | NOT NULL, default "USD" | Default currency |
| `timezone` | String(50) | NOT NULL, default "UTC" | Default timezone |
| `email` | String(255) | nullable | Billing contact email |
| `legal_name` | String(255) | nullable | Legal entity name |
| `legal_number` | String(255) | nullable | Tax/registration number |
| `address_line1` | String(255) | nullable | Address |
| `address_line2` | String(255) | nullable | Address line 2 |
| `city` | String(255) | nullable | City |
| `state` | String(255) | nullable | State/province |
| `zipcode` | String(20) | nullable | ZIP/postal code |
| `country` | String(2) | nullable | ISO 3166-1 alpha-2 country code |
| `hmac_key` | String(255) | nullable | HMAC key for webhook signing |
| `document_number_prefix` | String(50) | nullable | Prefix for invoice/credit-note numbers |
| `document_numbering` | String(30) | NOT NULL, default "per_customer" | per_customer or per_organization |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

### Table: `billing_entities`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique billing entity identifier |
| `organization_id` | UUID | FK -> organizations, NOT NULL, indexed | Parent organization |
| `name` | String(255) | NOT NULL | Entity name |
| `code` | String(255) | NOT NULL | Lookup code |
| `legal_name` | String(255) | nullable | Legal entity name |
| `legal_number` | String(255) | nullable | Tax/registration number |
| `email` | String(255) | nullable | Billing contact email |
| `default_currency` | String(3) | NOT NULL, default "USD" | Entity-level default currency |
| `timezone` | String(50) | nullable | Entity-level timezone |
| `address_line1` | String(255) | nullable | Address |
| `city` | String(255) | nullable | City |
| `state` | String(255) | nullable | State/province |
| `zipcode` | String(20) | nullable | ZIP/postal code |
| `country` | String(2) | nullable | Country |
| `document_number_prefix` | String(50) | nullable | Entity-specific document prefix |
| `document_numbering` | String(30) | NOT NULL, default "per_customer" | Numbering strategy |
| `is_default` | Boolean | NOT NULL, default false | Whether this is the default entity |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

**Unique Constraint:** `(organization_id, code)`

## API Key Scoping

### Table: `api_keys`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Key identifier |
| `organization_id` | UUID | FK -> organizations, NOT NULL, indexed | Owning organization |
| `value` | String(255) | NOT NULL, unique, indexed | API key value |
| `name` | String(255) | nullable | Key name/description |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `expires_at` | DateTime | nullable | Expiration date |

All API requests are scoped to the organization identified by the API key. Resources are isolated between organizations.

## Sequential ID Generation

Invoice and credit note numbers must be sequential and unique within their scope:

### Per-Organization Numbering
- Format: `{prefix}-YYYYMMDD-{sequential_id}`
- Sequential ID increments per organization
- Advisory lock on organization ID prevents race conditions

### Per-Customer Numbering
- Format: `{prefix}-{customer_sequential_id}-YYYYMMDD-{sequential_id}`
- Sequential ID increments per customer within an organization

### Per-Billing-Entity Numbering
- Same as per-organization but scoped to the billing entity
- Each billing entity has its own sequential counter

## Resource Scoping

When multi-tenancy is enabled, all resources gain an `organization_id` foreign key:
- Customers
- Plans
- Billable Metrics
- Subscriptions
- Invoices
- Events
- Taxes
- Coupons
- Add-Ons
- Webhooks
- etc.

Additionally, resources that can be billing-entity-specific gain a `billing_entity_id`:
- Invoices
- Credit Notes
- Customers (default billing entity)

## Migration Strategy

For existing bxb deployments:
1. Create a default organization
2. Create a default billing entity under it
3. Migrate all existing resources to reference the default organization
4. Add `organization_id` column to all resource tables
5. Add API key authentication

## API Endpoints

### Organizations
- `GET /v1/organization` — Get current organization
- `PUT /v1/organization` — Update organization settings

### Billing Entities
- `POST /v1/billing_entities` — Create billing entity
- `GET /v1/billing_entities` — List billing entities
- `GET /v1/billing_entities/{id}` — Get billing entity
- `PUT /v1/billing_entities/{id}` — Update billing entity
- `DELETE /v1/billing_entities/{id}` — Delete billing entity
