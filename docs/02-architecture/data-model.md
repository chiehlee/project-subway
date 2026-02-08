# Data Model
# Subway Store Operations App

**Version**: 0.1.0  
**Last Updated**: 2026-01-25  
**Status**: Draft

---

## Overview

This document defines the data model for the Subway Store Operations App, including entity relationships, schema definitions, and data validation rules.

---

## Entity Relationship Diagram

```
┌─────────────┐        ┌──────────────┐
│  Categories │←───────│   Invoices   │
└─────────────┘   *:1  └──────────────┘
                             │
                             │ 1:*
                             ↓
                       ┌──────────────┐
                       │ Invoice Items│
                       │  (future)    │
                       └──────────────┘

┌──────────────┐  *:1  ┌─────────────────┐
│ Transactions │───────→│ Daily Summaries │
└──────────────┘        └─────────────────┘
                              │
                              │ 1:1
                              ↓
                        ┌──────────────┐
                        │ Weather Data │
                        └──────────────┘

┌──────────────┐
│    Users     │
│  (future)    │
└──────────────┘
       │ 1:*
       ↓
┌──────────────┐
│  Audit Log   │
└──────────────┘

┌──────────────┐
│   Settings   │
└──────────────┘
```

---

## Core Entities

### 1. Invoices

Stores scanned and verified invoice data.

**Table**: `invoices`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique identifier |
| invoice_number | VARCHAR(50) | NOT NULL, UNIQUE | Invoice number from QR code |
| invoice_date | DATE | NOT NULL, INDEX | Invoice date |
| random_code | VARCHAR(4) | NOT NULL | Random verification code |
| seller_id | VARCHAR(8) | NOT NULL | Seller's tax ID |
| seller_name | VARCHAR(200) | | Seller's business name |
| buyer_id | VARCHAR(8) | | Buyer's tax ID (optional) |
| total_amount | DECIMAL(10,2) | NOT NULL | Total amount including tax |
| sales_amount | DECIMAL(10,2) | NOT NULL | Sales amount before tax |
| tax_amount | DECIMAL(10,2) | NOT NULL | Tax amount |
| category_id | INTEGER | FOREIGN KEY(categories), INDEX | Expense category |
| qr_code_left | TEXT | | Left QR code raw data |
| qr_code_right | TEXT | | Right QR code raw data |
| mof_verified | BOOLEAN | DEFAULT FALSE | Whether verified with MOF API |
| mof_verified_at | TIMESTAMP | | Timestamp of MOF verification |
| image_path | VARCHAR(500) | | Path to scanned image file |
| notes | TEXT | | User notes |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update time |

**Indexes**:
- `idx_invoice_date` on `invoice_date`
- `idx_invoice_category` on `category_id`
- `idx_invoice_seller` on `seller_id`

**Validation Rules**:
- `invoice_number` must match Taiwan e-invoice format (2 letters + 8 digits)
- `random_code` must be exactly 4 characters
- `total_amount = sales_amount + tax_amount`
- `invoice_date` cannot be in the future
- `tax_amount >= 0`

---

### 2. Transactions

Stores all sales transactions from POS system.

**Table**: `transactions`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique identifier |
| transaction_id | VARCHAR(50) | NOT NULL, UNIQUE | POS transaction ID |
| transaction_date | DATE | NOT NULL, INDEX | Transaction date |
| transaction_time | TIME | NOT NULL | Transaction time |
| transaction_datetime | TIMESTAMP | NOT NULL, INDEX | Combined date and time |
| payment_method | VARCHAR(20) | NOT NULL | cash, credit, debit, mobile |
| gross_amount | DECIMAL(10,2) | NOT NULL | Total amount before tax |
| tax_amount | DECIMAL(10,2) | NOT NULL | Tax amount |
| net_amount | DECIMAL(10,2) | NOT NULL | Total amount including tax |
| discount_amount | DECIMAL(10,2) | DEFAULT 0 | Discount applied |
| is_refund | BOOLEAN | DEFAULT FALSE | Whether this is a refund |
| is_void | BOOLEAN | DEFAULT FALSE | Whether this is voided |
| refund_reason | VARCHAR(200) | | Reason for refund (if applicable) |
| items_count | INTEGER | | Number of items in transaction |
| notes | TEXT | | Additional notes |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Indexes**:
- `idx_transaction_date` on `transaction_date`
- `idx_transaction_datetime` on `transaction_datetime`
- `idx_payment_method` on `payment_method`

**Validation Rules**:
- `net_amount = gross_amount + tax_amount - discount_amount`
- `transaction_date` cannot be in the future
- `payment_method` must be one of allowed values
- If `is_refund = TRUE`, `net_amount` should be negative
- `discount_amount >= 0`

---

### 3. Daily Summaries

Aggregated daily metrics for quick dashboard display.

**Table**: `daily_summaries`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique identifier |
| summary_date | DATE | NOT NULL, UNIQUE, INDEX | Date of summary |
| total_sales | DECIMAL(10,2) | NOT NULL | Total sales for the day |
| total_tax | DECIMAL(10,2) | NOT NULL | Total tax collected |
| transaction_count | INTEGER | NOT NULL | Number of transactions |
| average_ticket | DECIMAL(10,2) | | Average transaction amount |
| cash_sales | DECIMAL(10,2) | DEFAULT 0 | Cash payments total |
| card_sales | DECIMAL(10,2) | DEFAULT 0 | Credit/debit card total |
| mobile_sales | DECIMAL(10,2) | DEFAULT 0 | Mobile payment total |
| refund_count | INTEGER | DEFAULT 0 | Number of refunds |
| refund_amount | DECIMAL(10,2) | DEFAULT 0 | Total refund amount |
| expected_cash | DECIMAL(10,2) | | Expected cash in drawer |
| actual_cash | DECIMAL(10,2) | | Actual cash count |
| cash_discrepancy | DECIMAL(10,2) | | Difference (actual - expected) |
| is_reconciled | BOOLEAN | DEFAULT FALSE | Whether day is reconciled |
| reconciled_at | TIMESTAMP | | Timestamp of reconciliation |
| reconciled_by | VARCHAR(100) | | User who reconciled |
| notes | TEXT | | Reconciliation notes |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update time |

**Indexes**:
- `idx_summary_date` on `summary_date`
- `idx_reconciled` on `is_reconciled`

**Validation Rules**:
- `summary_date` is unique
- `total_sales >= 0`
- `transaction_count >= 0`
- `average_ticket = total_sales / transaction_count` (if count > 0)
- `cash_discrepancy = actual_cash - expected_cash` (if both provided)

---

### 4. Weather Data

Historical weather data correlated with sales.

**Table**: `weather_data`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique identifier |
| observation_date | DATE | NOT NULL, INDEX | Date of observation |
| observation_time | TIME | | Time of observation |
| station_id | VARCHAR(20) | | CWA station ID |
| station_name | VARCHAR(100) | | Weather station name |
| temperature | DECIMAL(5,2) | | Temperature in Celsius |
| temperature_max | DECIMAL(5,2) | | Max temperature for the day |
| temperature_min | DECIMAL(5,2) | | Min temperature for the day |
| humidity | DECIMAL(5,2) | | Relative humidity (%) |
| rainfall | DECIMAL(6,2) | DEFAULT 0 | Rainfall in mm |
| wind_speed | DECIMAL(5,2) | | Wind speed in m/s |
| wind_direction | VARCHAR(3) | | Wind direction (N, NE, E, ...) |
| weather_condition | VARCHAR(50) | | sunny, cloudy, rainy, etc. |
| air_pressure | DECIMAL(7,2) | | Air pressure in hPa |
| raw_data | TEXT | | Raw XML/JSON from API |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |

**Indexes**:
- `idx_weather_date` on `observation_date`
- `idx_weather_station` on `station_id`

**Validation Rules**:
- `temperature` range: -50 to 60 (Celsius)
- `humidity` range: 0 to 100 (%)
- `rainfall >= 0`
- `wind_speed >= 0`

---

### 5. Categories

Expense and income categories for classification.

**Table**: `categories`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique identifier |
| name | VARCHAR(100) | NOT NULL, UNIQUE | Category name |
| type | VARCHAR(20) | NOT NULL | expense or income |
| parent_id | INTEGER | FOREIGN KEY(categories) | Parent category (for subcategories) |
| description | TEXT | | Category description |
| is_active | BOOLEAN | DEFAULT TRUE | Whether category is active |
| display_order | INTEGER | DEFAULT 0 | Display order in UI |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Record creation time |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update time |

**Indexes**:
- `idx_category_type` on `type`
- `idx_category_parent` on `parent_id`

**Default Categories** (Expenses):
1. Food & Ingredients
2. Beverages
3. Packaging & Supplies
4. Equipment & Maintenance
5. Utilities
6. Rent & Lease
7. Marketing & Advertising
8. Professional Services (accounting, legal, etc.)
9. Insurance
10. Other

**Validation Rules**:
- `type` must be "expense" or "income"
- `parent_id` must exist if provided
- No circular parent references
- Active categories cannot have inactive parents

---

### 6. Settings

Application configuration and preferences.

**Table**: `settings`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| key | VARCHAR(100) | PRIMARY KEY | Setting key |
| value | TEXT | NOT NULL | Setting value (JSON or string) |
| value_type | VARCHAR(20) | NOT NULL | string, number, boolean, json |
| description | TEXT | | Setting description |
| is_system | BOOLEAN | DEFAULT FALSE | Whether system-managed |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update time |
| updated_by | VARCHAR(100) | | User who updated |

**Initial Settings**:
```json
{
  "store.name": "Subway Store",
  "store.address": "",
  "store.tax_id": "",
  "store.phone": "",
  "business.hours_open": "08:00",
  "business.hours_close": "22:00",
  "business.timezone": "Asia/Taipei",
  "tax.rate": 0.05,
  "tax.included": true,
  "currency.code": "TWD",
  "currency.symbol": "NT$",
  "alerts.low_cash_threshold": 500,
  "alerts.high_refund_rate": 0.05,
  "alerts.reconciliation_discrepancy": 100,
  "api.mof_app_id": "",
  "api.mof_api_key": "",
  "api.cwa_api_key": "",
  "backup.auto_enabled": true,
  "backup.schedule": "daily",
  "backup.retention_days": 30
}
```

**Validation Rules**:
- System settings (`is_system = TRUE`) cannot be deleted
- `value_type` determines value format validation
- Sensitive keys (api.*) should be encrypted

---

### 7. Audit Log

Tracks all significant system actions for accountability.

**Table**: `audit_log`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique identifier |
| timestamp | TIMESTAMP | NOT NULL, INDEX | Action timestamp |
| user_id | INTEGER | FOREIGN KEY(users) | User who performed action |
| username | VARCHAR(100) | | Username (denormalized) |
| action | VARCHAR(50) | NOT NULL | create, update, delete, login, etc. |
| entity_type | VARCHAR(50) | NOT NULL | invoices, transactions, etc. |
| entity_id | INTEGER | | ID of affected entity |
| old_values | TEXT | | JSON of old values (for updates) |
| new_values | TEXT | | JSON of new values |
| ip_address | VARCHAR(45) | | IP address of user |
| user_agent | VARCHAR(500) | | Browser/client info |
| notes | TEXT | | Additional context |

**Indexes**:
- `idx_audit_timestamp` on `timestamp`
- `idx_audit_user` on `user_id`
- `idx_audit_entity` on `entity_type, entity_id`

**Validation Rules**:
- Audit log records are immutable (no updates or deletes)
- `action` must be from predefined list
- Sensitive data (passwords) should not be logged

---

## Data Validation Rules (Summary)

### Invoice Data Validation
```python
def validate_invoice(invoice):
    # Invoice number format: 2 letters + 8 digits
    assert re.match(r'^[A-Z]{2}\d{8}$', invoice.invoice_number)
    
    # Random code must be 4 characters
    assert len(invoice.random_code) == 4
    
    # Amounts must be consistent
    assert invoice.total_amount == invoice.sales_amount + invoice.tax_amount
    
    # Date must not be in future
    assert invoice.invoice_date <= date.today()
    
    # Tax must be non-negative
    assert invoice.tax_amount >= 0
```

### Transaction Data Validation
```python
def validate_transaction(txn):
    # Net amount calculation
    assert txn.net_amount == txn.gross_amount + txn.tax_amount - txn.discount_amount
    
    # Date must not be in future
    assert txn.transaction_date <= date.today()
    
    # Payment method must be valid
    assert txn.payment_method in ['cash', 'credit', 'debit', 'mobile']
    
    # Refund amounts should be negative
    if txn.is_refund:
        assert txn.net_amount < 0
    
    # Discount must be non-negative
    assert txn.discount_amount >= 0
```

---

## Data Migration Strategy

### Phase 1: MVP (SQLite)
- Use SQLite for simplicity
- Single file database: `data/subway.db`
- Manual backups via file copy

### Phase 2: Production (PostgreSQL)
- Migrate to PostgreSQL for reliability and performance
- Use SQLAlchemy migrations (Alembic)
- Automated backup via pg_dump

### Migration Process
1. Export data from SQLite to CSV
2. Create PostgreSQL schema
3. Import CSV data with validation
4. Verify data integrity
5. Update application configuration
6. Test thoroughly before cutover

---

## Appendix

### Sample Data

**Sample Invoice**:
```json
{
  "id": 1,
  "invoice_number": "AB12345678",
  "invoice_date": "2026-01-25",
  "random_code": "1234",
  "seller_id": "12345678",
  "seller_name": "ABC Food Supply Co.",
  "total_amount": 1050.00,
  "sales_amount": 1000.00,
  "tax_amount": 50.00,
  "category_id": 1,
  "mof_verified": true,
  "notes": "Monthly food supplies order"
}
```

**Sample Transaction**:
```json
{
  "id": 1,
  "transaction_id": "POS20260125001",
  "transaction_date": "2026-01-25",
  "transaction_time": "12:34:56",
  "payment_method": "credit",
  "gross_amount": 285.71,
  "tax_amount": 14.29,
  "net_amount": 300.00,
  "discount_amount": 0,
  "is_refund": false,
  "items_count": 3
}
```

---

## Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1.0 | 2026-01-25 | Initial | Initial data model document |
