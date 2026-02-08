# Core Features

This document outlines the core features of the Subway Store Operations App.

---

## 1. Invoice Management
**Priority**: P0 (Must Have)

### Description
Automate the scanning, parsing, and storage of Taiwan e-invoices (with 2 QR codes).

### Requirements
- Scan invoices using webcam or mobile camera
- Parse QR codes to extract invoice data
- Validate against Ministry of Finance (MOF) API
- Store invoice data with proper categorization
- Support batch scanning workflow
- Handle invoice corrections and cancellations

### Success Criteria
- 95%+ accuracy in QR code scanning
- <5 seconds per invoice processing time
- Automatic categorization of 80%+ of invoices

### Future Enhancements
- OCR for invoice details beyond QR codes
- Automatic vendor recognition
- Invoice approval workflow

---

## 2. Transaction Tracking
**Priority**: P0 (Must Have)

### Description
Track and reconcile daily transactions from POS system and other payment sources.

### Requirements
- Import transaction data from CSV/Excel files
- Categorize transactions by type (sales, refunds, etc.)
- Daily reconciliation against bank statements
- Multiple payment method support
- Generate daily sales reports

### Success Criteria
- All transactions logged with proper categorization
- Daily reconciliation discrepancies <1%
- Report generation in <10 seconds

### Future Enhancements
- Real-time POS integration
- Automatic anomaly detection
- Predictive sales forecasting

---

## 3. Weather Data Integration
**Priority**: P1 (Should Have)

### Description
Correlate weather conditions with store performance to identify patterns.

### Requirements
- Fetch weather data from CWA (Central Weather Administration)
- Store historical weather data
- Correlate with transaction data
- Visualize weather impact on sales
- Generate weather-adjusted forecasts

### Success Criteria
- Daily weather data capture with >99% uptime
- Historical data available for analysis
- Clear visualization of weather-sales correlation

### Future Enhancements
- Predictive inventory adjustment based on weather forecast
- Automated staffing recommendations
- Multi-location weather comparison

---

## 4. Analytics Dashboard
**Priority**: P1 (Should Have)

### Description
Provide visual insights into store performance across multiple dimensions.

### Requirements
- Key metrics display (daily/weekly/monthly)
- Trend analysis and comparisons
- Customizable time ranges
- Export capabilities (PDF, Excel)
- Mobile-responsive design

### Metrics to Track
- Daily sales revenue
- Transaction count and average ticket
- Best/worst performing products
- Peak hours and traffic patterns
- Inventory turnover
- Expense tracking and P&L

### Success Criteria
- Dashboard loads in <3 seconds
- Support for 2+ years of historical data
- Responsive design works on mobile devices

---

## 5. Data Management
**Priority**: P0 (Must Have)

### Description
Centralized, reliable storage and management of all operational data.

### Requirements
- Secure data storage
- Data backup and recovery
- Data validation and integrity checks
- Import/export functionality
- Data retention policies

### Success Criteria
- Zero data loss
- Daily automated backups
- Data recovery possible within 24 hours
- Support for standard formats (CSV, JSON, Excel)
