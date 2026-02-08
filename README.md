# Project Subway

A comprehensive operational management application for Subway store operations, including invoice management, transaction tracking, analytics, and reporting.

**Current Status**: Planning & Specification Phase  
**Version**: 0.1.0 (Pre-MVP)  
**Last Updated**: 2026-01-25

---

## 📚 Documentation

**[View Beautiful Documentation →](http://127.0.0.1:8000)** (when running locally)

This project uses **MkDocs Material** for documentation. 

### Quick Commands

```bash
# View all available commands
make help

# Install documentation dependencies
make docs-install

# Serve docs locally with live reload
make docs-serve
# Then open: http://127.0.0.1:8000

# Build static site
make docs-build

# Deploy to GitHub Pages  
make docs-deploy
```

### Documentation Structure

```
docs/                      # All documentation lives here
├── index.md              # Documentation homepage
├── 01-product/           # Product specs, user stories, roadmap
└── 02-architecture/      # System design, data models
```

---

## Quick Links

### Project Guidelines
- **[📋 Development Guidelines](PROJECT_GUIDELINES.md)** - Base guidelines for AI-assisted development

### Product Documentation
- **[📊 Overview](docs/01-product/overview.md)** - Executive summary and target users
- **[✨ Features](docs/01-product/features.md)** - Core features and requirements
- **[📝 Requirements](docs/01-product/requirements.md)** - Technical and non-functional requirements
- **[🗺️ Planning](docs/01-product/planning.md)** - Success metrics and timeline

### Technical Documentation
- **[🏗️ System Design](docs/02-architecture/system-design.md)** - Technical architecture
- **[💾 Data Model](docs/02-architecture/data-model.md)** - Database schema and entities

---

## Project Overview

### What is Project Subway?

An application to streamline daily operations for a Subway store, including:
- 🧾 **Invoice Management**: Scan and digitize Taiwan e-invoices
- 💰 **Transaction Tracking**: Import and reconcile daily sales
- 📊 **Analytics Dashboard**: Visualize performance metrics
- 🌦️ **Weather Integration**: Correlate weather with sales patterns
- 📈 **Reporting**: Generate daily, weekly, and monthly reports

### Why?

Currently, store operations involve tedious manual processes for data entry, reconciliation, and reporting. This app will:
- Save 5-10 hours per week on administrative tasks
- Reduce errors in financial records
- Enable data-driven decision making
- Provide real-time visibility into store performance

---

## Development Setup

### Prerequisites

Python requirement: 3.13.x (pyproject pins to >=3.13,<3.14)

### Installation

1. Install Python 3.13 (e.g., with pyenv: `pyenv install 3.13.6`)
2. Point Poetry at that interpreter: `poetry env use $(pyenv which python)`
3. Install dependencies: `poetry install`

### Development Workflow

```bash
# Add new dependencies
poetry add <package>

# Run tests
poetry run pytest

# Format code
poetry run black project_subway tests

# Lint code
poetry run ruff check project_subway tests

# Type check
poetry run mypy project_subway
```

---

## Project Structure

```
project-subway/
├── data/                   # Data files (CSV, images, etc.)
│   ├── invoices/          # Scanned invoice images
│   ├── transactions/      # Transaction CSV files
│   └── weather/           # Weather data
├── docs/                   # 📚 Documentation (START HERE!)
│   ├── 01-product/        # Product specs, user stories, roadmap
│   └── 02-architecture/   # System design, data models
├── project_subway/        # Main application code
├── scripts/               # Utility scripts
├── tests/                 # Test files
├── utilities/             # Helper utilities
├── pyproject.toml         # Poetry dependencies
└── README.md              # This file
```

---

## Current Phase: Documentation & Specification

**⚠️ We are currently in the planning phase. No application code should be written yet!**

### Completed
- ✅ Documentation framework created
- ✅ Product Requirements Document (PRD)
- ✅ User Stories documented
- ✅ System Architecture designed
- ✅ Data Model defined
- ✅ Coding Standards established
- ✅ Development Roadmap created

### Next Steps
1. Review and finalize all specification documents
2. Make key technical decisions (web framework, deployment, etc.)
3. Set up development environment (Docker, CI/CD)
4. Create database schema and migrations
5. Begin MVP development (Sprint 1: Invoice Management)

---

## Documentation First Approach

This project follows a **documentation-first** methodology:

1. 📝 **Specify** - Write detailed specifications before coding
2. 🏗️ **Design** - Document architecture and data models
3. 💻 **Implement** - Write code based on specifications
4. ✅ **Test** - Verify against documented requirements
5. 📚 **Update** - Keep documentation current as system evolves

**Benefits**:
- Clear requirements before development starts
- Better architectural decisions
- Easier onboarding for new contributors
- Living documentation that stays relevant

---

## Usage

### Current Status

The application is not yet developed. Currently, there are some utility scripts for specific tasks:

### Scan Taiwan e-invoice paper (2 QR codes)

Prereqs (macOS):
- Install zbar: `brew install zbar` (required by `pyzbar`)
- Install Python deps: `poetry add opencv-python pyzbar`

Webcam mode (batch scan; press `s` to save each invoice):
- `poetry run python scripts/scan_invoice_qr.py --output data/invoices/invoices.tsv`

Optional: try MOF enrichment (best-effort; requires credentials):
- Set env vars: `MOF_EINVOICE_APP_ID` and `MOF_EINVOICE_API_KEY`
- Run with `--mof`

---

---

## License

TBD

---

## Contact & Support

For questions or issues:
- Create an issue in the repository
- Refer to documentation in `docs/` directory

---

## Acknowledgments

Built with:
- Python 3.13+
- Poetry for dependency management
- OpenCV & pyzbar for QR code scanning
- pandas for data processing
- And many other great open-source libraries

### Scan Taiwan e-invoice paper (2 QR codes)

Prereqs (macOS):
- Install zbar: `brew install zbar` (required by `pyzbar`)
- Install Python deps: `poetry add opencv-python pyzbar`

Webcam mode (batch scan; press `s` to save each invoice):
- `poetry run python scripts/scan_invoice_qr.py --output data/invoices/invoices.tsv`

Optional: try MOF enrichment (best-effort; requires credentials):
- Set env vars: `MOF_EINVOICE_APP_ID` and `MOF_EINVOICE_API_KEY`
- Run with `--mof`

## Poetry environments
- List envs: `poetry env list` (names look like `project-subway-<hash>-py3.13`).
- Current 3.13 env: `/Users/chieh/Library/Caches/pypoetry/virtualenvs/project-subway-1s6GqF-t-py3.13` (auto-used by `poetry run ...`).
- Test env created with Python 3.12: `poetry env use python3.12`. It exists but doesn’t satisfy the >=3.13,<3.14 constraint; switch back with `poetry env use python3.13`.
- Inspect the active env: `poetry env info`.