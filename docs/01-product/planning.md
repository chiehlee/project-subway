# Project Planning

This document outlines success metrics, timeline, and open questions for the project.

---

## Success Metrics

### Phase 1 (MVP - 3 months)
- Successfully process 100+ invoices
- Track 30+ days of transaction data
- Generate basic daily/weekly reports
- 1-2 active users using the system daily

### Phase 2 (6 months)
- Weather data integrated for 90+ days
- Advanced analytics dashboard operational
- 5+ users actively using the system
- Time savings: 5+ hours per week vs manual processes

### Phase 3 (12 months)
- Predictive analytics functional
- Mobile app available
- Multi-store support (if applicable)
- Time savings: 10+ hours per week
- Decision making improved (measured by operator feedback)

---

## Out of Scope (for MVP)

The following features are explicitly excluded from the initial release:

1. Multi-store/franchise management
2. Employee scheduling and time tracking
3. Customer loyalty program integration
4. Online ordering integration
5. Advanced ML/AI predictions
6. Real-time POS integration (will use batch import instead)
7. Third-party accounting software integration
8. Marketing campaign management
9. Customer feedback system

---

## Timeline and Milestones

### Phase 0: Planning & Design (2 weeks)
- [ ] Complete PRD
- [ ] Finalize system architecture
- [ ] Design data models
- [ ] Create wireframes/mockups

### Phase 1: MVP Development (6-8 weeks)
- [ ] Invoice scanning module
- [ ] Transaction tracking module
- [ ] Basic data storage and retrieval
- [ ] Simple reporting interface

### Phase 2: Enhancement (4-6 weeks)
- [ ] Weather data integration
- [ ] Analytics dashboard
- [ ] Data export functionality
- [ ] Mobile responsiveness

### Phase 3: Polish & Deploy (2-4 weeks)
- [ ] User acceptance testing
- [ ] Bug fixes and performance optimization
- [ ] Documentation completion
- [ ] Production deployment

---

## Open Questions

1. **Hosting Strategy**: Should we deploy locally on a dedicated machine or use cloud hosting?
2. **Database Choice**: SQLite sufficient for MVP or should we start with PostgreSQL?
3. **Mobile Strategy**: Web-responsive sufficient or need native mobile app?
4. **Authentication**: Single user or multi-user from the start?
5. **Backup Strategy**: Where should backups be stored? What's the retention policy?
6. **API Rate Limits**: What are the rate limits for MOF and CWA APIs?
7. **POS System**: What specific POS system is being used? Can we get API access or only exports?

---

## Appendix

### Glossary
- **MOF**: Ministry of Finance (Taiwan)
- **CWA**: Central Weather Administration (Taiwan)
- **POS**: Point of Sale
- **e-Invoice**: Electronic invoice with QR codes (Taiwan-specific format)
- **P&L**: Profit and Loss statement

### References
- [Taiwan e-Invoice API Documentation](https://www.einvoice.nat.gov.tw/)
- [CWA Open Data Platform](https://opendata.cwa.gov.tw/)
- Existing project scripts in `/scripts` and `/utilities` directories

### Change Log
| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1.0 | 2026-01-25 | Initial | Initial PRD creation |
| 0.2.0 | 2026-02-08 | AI | Split PRD into subpages, improved Executive Summary |
