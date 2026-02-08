# System Design Document
# Subway Store Operations App

**Version**: 0.1.0  
**Last Updated**: 2026-01-25  
**Status**: Draft

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Principles](#architecture-principles)
3. [High-Level Architecture](#high-level-architecture)
4. [Component Design](#component-design)
5. [Data Flow](#data-flow)
6. [Technology Stack](#technology-stack)
7. [Deployment Architecture](#deployment-architecture)
8. [Security Considerations](#security-considerations)
9. [Scalability & Performance](#scalability--performance)
10. [Open Issues](#open-issues)

---

## Overview

### Purpose
This document describes the technical architecture of the Subway Store Operations App, including system components, data flows, and key design decisions.

### Scope
- Application architecture for MVP and future phases
- Component responsibilities and interactions
- Data storage and flow patterns
- Security and deployment considerations

### Audience
- Developers implementing the system
- Technical reviewers
- Future maintainers

---

## Architecture Principles

### 1. Modularity
- Components should be loosely coupled and independently testable
- Each module has a single, well-defined responsibility
- Clear interfaces between components

### 2. Simplicity First
- Start with simple solutions, add complexity only when needed
- Avoid over-engineering for hypothetical future requirements
- Use proven patterns and technologies

### 3. Data-Centric Design
- Data quality and integrity are paramount
- Clear data validation at boundaries
- Comprehensive audit trail for critical operations

### 4. Progressive Enhancement
- Build a working MVP first
- Design for extensibility without implementing it upfront
- Add features incrementally based on user feedback

### 5. Local-First with Cloud Option
- System should work well in local/offline mode
- Cloud deployment should be straightforward but optional
- Data ownership remains with the store

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Web UI     │  │  Mobile UI   │  │    CLI       │      │
│  │  (Browser)   │  │ (Responsive) │  │  (Scripts)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↕ HTTP/REST
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Invoice    │  │ Transaction  │  │   Weather    │      │
│  │   Service    │  │   Service    │  │   Service    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Analytics   │  │   Report     │  │    Auth      │      │
│  │   Service    │  │   Service    │  │   Service    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                        Data Layer                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Database    │  │  File Store  │  │    Cache     │      │
│  │ (SQLite/PG)  │  │   (Local)    │  │   (Redis?)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                   External Services                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  MOF e-Invoice│ │  CWA Weather │  │     POS      │      │
│  │     API      │  │     API      │  │   (Export)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Design

### 1. Presentation Layer

#### Web UI (Primary Interface)
**Technology**: TBD (Options: Flask/Django/FastAPI + HTML/CSS/JS)

**Responsibilities**:
- User authentication and session management
- Invoice scanning interface (webcam integration)
- Transaction data import and visualization
- Dashboard and reporting views
- System settings and configuration

**Key Considerations**:
- Mobile-responsive design (Bootstrap/Tailwind CSS)
- Progressive Web App (PWA) capabilities for offline use
- Minimal JavaScript frameworks (avoid heavy SPAs for simplicity)

#### CLI (Batch Operations)
**Technology**: Python Click or argparse

**Responsibilities**:
- Batch data import operations
- Database maintenance tasks
- Backup and restore operations
- Development and testing utilities

**Use Cases**:
- Automated nightly imports
- Database migrations
- Troubleshooting and diagnostics

---

### 2. Application Layer

#### Invoice Service
**Responsibilities**:
- QR code scanning and parsing (using pyzbar/zxing-cpp)
- MOF API integration for verification
- Invoice data validation and storage
- Invoice categorization and tagging
- Invoice search and retrieval

**Key Classes**:
```python
class InvoiceScanner:
    def scan_from_webcam() -> Invoice
    def scan_from_image(image_path) -> Invoice
    def extract_qr_codes(image) -> List[str]

class InvoiceVerifier:
    def verify_with_mof(invoice: Invoice) -> VerificationResult
    def enrich_invoice_data(invoice: Invoice) -> Invoice

class InvoiceRepository:
    def save(invoice: Invoice) -> int
    def find_by_id(id: int) -> Invoice
    def search(criteria: SearchCriteria) -> List[Invoice]
```

#### Transaction Service
**Responsibilities**:
- Import transactions from CSV/Excel
- Transaction validation and deduplication
- Daily reconciliation calculations
- Transaction categorization
- Payment method tracking

**Key Classes**:
```python
class TransactionImporter:
    def import_from_csv(file_path) -> List[Transaction]
    def import_from_excel(file_path) -> List[Transaction]
    def validate_transactions(txns) -> ValidationResult

class TransactionRepository:
    def save_batch(transactions: List[Transaction])
    def get_by_date_range(start, end) -> List[Transaction]
    def get_daily_summary(date) -> DailySummary

class ReconciliationService:
    def reconcile_day(date, cash_count) -> ReconciliationResult
```

#### Weather Service
**Responsibilities**:
- Fetch weather data from CWA API
- Store historical weather data
- Correlate weather with transaction data
- Weather-based analytics

**Key Classes**:
```python
class WeatherDataFetcher:
    def fetch_current_weather() -> WeatherData
    def fetch_historical(date) -> WeatherData
    def fetch_forecast(days) -> List[WeatherData]

class WeatherRepository:
    def save(weather_data: WeatherData)
    def get_by_date(date) -> WeatherData
    def get_range(start_date, end_date) -> List[WeatherData]

class WeatherAnalyzer:
    def correlate_with_sales(weather, sales) -> CorrelationResult
```

#### Analytics Service
**Responsibilities**:
- Calculate KPIs and metrics
- Trend analysis and comparisons
- Data aggregation for reporting
- Predictive models (future enhancement)

**Key Classes**:
```python
class MetricsCalculator:
    def calculate_daily_metrics(date) -> DailyMetrics
    def calculate_period_metrics(start, end) -> PeriodMetrics
    def calculate_trends(metric, period) -> TrendData

class ComparativeAnalyzer:
    def compare_periods(period1, period2) -> ComparisonResult
    def identify_patterns(metric, data) -> List[Pattern]
```

#### Report Service
**Responsibilities**:
- Generate formatted reports (PDF, Excel)
- Report templates and customization
- Scheduled report generation
- Data export functionality

**Key Classes**:
```python
class ReportGenerator:
    def generate_daily_report(date) -> Report
    def generate_weekly_report(week) -> Report
    def generate_custom_report(config) -> Report

class ReportExporter:
    def export_to_pdf(report) -> bytes
    def export_to_excel(report) -> bytes
    def export_to_csv(data) -> str
```

---

### 3. Data Layer

#### Database Schema (High-Level)

**Tables**:

1. **invoices**
   - id, date, vendor, amount, tax, category, qr_code_1, qr_code_2, mof_verified, notes, created_at, updated_at

2. **transactions**
   - id, date, time, transaction_id, payment_method, amount, tax, refund, void, notes, created_at

3. **weather_data**
   - id, date, hour, temperature, rainfall, humidity, wind_speed, conditions, created_at

4. **daily_summaries**
   - id, date, total_sales, transaction_count, average_ticket, cash_sales, card_sales, reconciled, discrepancy, created_at

5. **categories**
   - id, name, type (expense/income), parent_id, created_at

6. **settings**
   - key, value, type, description, updated_at

7. **audit_log**
   - id, timestamp, user, action, entity_type, entity_id, details

**Relationships**:
- invoices → categories (many-to-one)
- transactions → daily_summaries (many-to-one via date)
- weather_data joins with daily_summaries on date

#### File Storage

**Structure**:
```
data/
├── invoices/              # Scanned invoice images
│   ├── 2026/
│   │   ├── 01/
│   │   │   ├── inv_20260125_001.png
│   │   │   └── inv_20260125_002.png
├── transactions/          # Imported CSV/Excel files
│   ├── 2026-01-25.csv
├── weather/               # Raw weather data (XML/JSON)
│   └── cwa/
├── reports/               # Generated reports
│   ├── daily/
│   └── weekly/
└── backups/               # Database backups
    ├── backup_20260125.db
```

---

## Data Flow

### Invoice Scanning Flow

```
User → Web UI → InvoiceScanner.scan_from_webcam()
                      ↓
              Extract QR Codes (pyzbar)
                      ↓
              Parse Invoice Data
                      ↓
              InvoiceVerifier.verify_with_mof()
                      ↓
              User Reviews/Edits Data
                      ↓
              InvoiceRepository.save()
                      ↓
              Store Image in File System
                      ↓
              Update Database
```

### Transaction Import Flow

```
User Uploads CSV → TransactionImporter.import_from_csv()
                            ↓
                   Validate Format
                            ↓
                   Detect Duplicates
                            ↓
                   User Confirms Import
                            ↓
                   TransactionRepository.save_batch()
                            ↓
                   Calculate Daily Summary
                            ↓
                   Update Dashboard
```

### Weather Data Sync Flow

```
Scheduled Task → WeatherDataFetcher.fetch_current_weather()
                        ↓
                 CWA API Call
                        ↓
                 Parse XML/JSON Response
                        ↓
                 WeatherRepository.save()
                        ↓
                 Log Success/Failure
```

---

## Technology Stack

### Core Technologies
- **Language**: Python 3.13+
- **Package Management**: Poetry
- **Web Framework**: TBD (Flask/FastAPI recommended)
- **Database**: SQLite (MVP) → PostgreSQL (production)
- **ORM**: SQLAlchemy
- **Testing**: pytest
- **Linting**: ruff

### Key Libraries
- **Data Processing**: pandas, numpy
- **Visualization**: matplotlib, plotly (for interactive charts)
- **QR Code Scanning**: pyzbar, zxing-cpp, opencv-python
- **HTTP Requests**: requests, httpx
- **Date/Time**: python-dateutil, pytz
- **Reporting**: reportlab (PDF), openpyxl (Excel)

### Frontend (If Web UI)
- **CSS Framework**: Bootstrap 5 or Tailwind CSS
- **JavaScript**: Vanilla JS or Alpine.js (lightweight)
- **Charts**: Chart.js or Plotly.js

### DevOps
- **Containerization**: Docker
- **CI/CD**: GitHub Actions (optional)
- **Monitoring**: Logging to file (MVP) → Sentry (production)

---

## Deployment Architecture

### Development Environment
```
Local Machine
├── Python 3.13 (via pyenv)
├── Poetry virtual environment
├── SQLite database (data/dev.db)
├── File storage (data/)
└── Web server (Flask dev server)
```

### Production Environment (Option 1: Local Server)
```
Dedicated Machine/NAS
├── Docker Container
│   ├── Python app
│   ├── PostgreSQL
│   └── Nginx (reverse proxy)
├── External backup (NAS/external drive)
└── SSL Certificate (Let's Encrypt)
```

### Production Environment (Option 2: Cloud)
```
Cloud Provider (AWS/GCP/Azure)
├── Compute (EC2/Compute Engine/VM)
├── Database (RDS/Cloud SQL/Azure DB)
├── Object Storage (S3/GCS/Blob)
├── Backup (automated snapshots)
└── CDN (CloudFront/Cloud CDN)
```

---

## Security Considerations

### Authentication & Authorization
- **MVP**: Single-user mode with simple password authentication
- **Future**: Multi-user with role-based access control (RBAC)
- Session management with secure cookies
- Password hashing with bcrypt/argon2

### Data Protection
- Database encryption at rest (production)
- HTTPS/TLS for all network communication
- API keys stored in environment variables or secure key vault
- Sensitive data (passwords, API keys) never logged

### Input Validation
- Validate all user inputs at API boundaries
- Sanitize file uploads (CSV, images)
- Prevent SQL injection (use parameterized queries)
- Rate limiting on API endpoints

### Audit Trail
- Log all data modifications (who, what, when)
- Immutable audit log
- Regular security updates for dependencies

---

## Scalability & Performance

### Current Constraints (MVP)
- Single store, single user
- ~100 invoices/month
- ~500 transactions/day
- 2 years historical data (~365K records)

### Performance Targets
- Dashboard load: <3 seconds
- Invoice scan: <5 seconds per invoice
- Report generation: <10 seconds
- Data import: 1000 records in <30 seconds

### Optimization Strategies
- Database indexing on frequently queried fields (date, category)
- Caching for dashboard metrics (refresh every 5 minutes)
- Lazy loading for large reports
- Pagination for list views
- Background jobs for heavy processing (report generation, data sync)

### Future Scalability
- Horizontal scaling with load balancer
- Database read replicas
- Object storage for images/files
- CDN for static assets
- Message queue for async processing (Celery/Redis)

---

## Open Issues

### Decisions Needed

1. **Web Framework Choice**
   - Options: Flask (simple), Django (batteries included), FastAPI (modern, async)
   - Recommendation: Flask for MVP (easy to learn, sufficient features)

2. **Frontend Approach**
   - Options: Server-side rendering (Jinja templates), SPA (React/Vue), Hybrid
   - Recommendation: Server-side rendering with progressive enhancement

3. **Authentication Strategy**
   - MVP: Simple password protection sufficient?
   - Future: Need proper user management from start?

4. **Deployment Target**
   - Local server (Raspberry Pi, NAS) or cloud hosting?
   - Impact on database choice and backup strategy

5. **Image Storage**
   - Local file system or object storage (S3)?
   - Compression strategy for scanned invoices?

### Technical Risks

1. **QR Code Scanning Reliability**
   - Risk: Poor lighting or damaged invoices reduce scan success rate
   - Mitigation: Provide manual entry fallback, image enhancement

2. **API Dependencies**
   - Risk: MOF or CWA API changes/downtime
   - Mitigation: Cache results, graceful degradation, manual override

3. **Data Migration**
   - Risk: Moving from SQLite to PostgreSQL may be complex
   - Mitigation: Use SQLAlchemy for database abstraction, test migration early

4. **Performance with Large Datasets**
   - Risk: Dashboard slows down as data grows
   - Mitigation: Implement caching, pagination, data archiving strategy

---

## Next Steps

1. [ ] Finalize web framework choice
2. [ ] Create database schema and migrations
3. [ ] Set up development environment (Docker compose)
4. [ ] Implement core models and repositories
5. [ ] Build invoice scanning prototype
6. [ ] Design and implement UI mockups

---

## Appendix

### Diagrams
- See separate file: `system-diagrams.md`

### Alternative Architectures Considered
- Microservices: Too complex for single-store MVP
- Serverless: Interesting but adds deployment complexity
- Desktop app (Electron/PyQt): Less flexible than web app

### References
- Flask Documentation: https://flask.palletsprojects.com/
- FastAPI Documentation: https://fastapi.tiangolo.com/
- SQLAlchemy Documentation: https://www.sqlalchemy.org/
- Python Best Practices: https://docs.python-guide.org/

---

## Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1.0 | 2026-01-25 | Initial | Initial system design document |
