# BLACK CORAL

An AI-powered government contracting workflow system that streamlines and accelerates the U.S. government contracting process.

## Overview

BLACK CORAL replaces the traditional sequential evaluation-capture-pricing-proposal process with a dynamic, concurrent agent-driven system. It integrates AI assistants to automate research, analysis, compliance monitoring, and proposal generation for government contracting opportunities.

## Key Features

- **Real-time Opportunity Discovery**: Integrated searches across sam.gov, USASpending.gov, and GAO APIs
- **AI-Powered Analysis**: Automated SOW/PWS summarization using Claude Code and Gemini
- **Role-Based Workflow**: Six distinct user roles with specialized permissions and dashboards
- **Document Processing**: Support for PDF, Word, ZIP, HTML, XLS, and image formats with OCR
- **Compliance Monitoring**: Continuous FAR and agency compliance checking with real-time alerts
- **Proposal Assembly**: Automated document compilation and submission coordination

## Technology Stack

### Backend
- **Python 3.10+** with **Django 5.2**
- **PostgreSQL** for data storage
- **Redis** for caching and task queuing
- **Celery** for background task processing

### Frontend
- **HTMX** for dynamic page updates
- **Alpine.js** for interactive components
- **Django Templates** with custom CSS

### AI Integration
- **Anthropic Claude Code** for advanced analysis
- **Google Gemini** for content generation
- **Custom AI abstraction layer** for service management

### External APIs
- sam.gov API for opportunity data
- USASpending.gov API for spending information
- GAO API for reports and oversight data

## User Roles

1. **Admin**: User management and system configuration
2. **Researcher**: Opportunity discovery and initial analysis
3. **Reviewer**: Content review and approval workflows
4. **Compliance Monitor**: Regulatory compliance oversight
5. **QA**: Quality assurance and content validation
6. **Submission Agent**: Final assembly and proposal submission

## Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL 14+
- Redis 7+
- Node.js (for development tools)

### Installation

1. **Clone and setup environment**:
   ```bash
   git clone https://github.com/sjpenn/BlackCoral.git
   cd BlackCoral
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials and API keys
   ```

4. **Setup database**:
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

5. **Load initial data** (optional):
   ```bash
   python manage.py loaddata fixtures/naics_codes.json
   python manage.py loaddata fixtures/agencies.json
   ```

6. **Run development server**:
   ```bash
   python manage.py runserver
   ```

7. **Start Celery workers** (in separate terminal):
   ```bash
   celery -A blackcoral worker -l info
   ```

### Docker Setup (Alternative)

```bash
docker-compose up -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

## Configuration

### Environment Variables

Key environment variables to configure in `.env`:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/blackcoral

# API Keys
SAM_GOV_API_KEY=your-sam-gov-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
GOOGLE_AI_API_KEY=your-google-ai-api-key

# Security
SECRET_KEY=your-secret-key
DEBUG=False
```

### External API Setup

1. **sam.gov API**: Register at [sam.gov](https://sam.gov/api) for API access
2. **USASpending.gov**: Public API, no registration required
3. **Anthropic Claude**: Sign up at [console.anthropic.com](https://console.anthropic.com)
4. **Google AI**: Enable Gemini API in Google Cloud Console

## Development

### Project Structure

```
BlackCoral/
├── apps/                    # Django applications
│   ├── core/               # Core models and utilities
│   ├── authentication/     # User management and RBAC
│   ├── opportunities/      # Opportunity management
│   ├── documents/          # Document processing
│   ├── ai_integration/     # AI service integrations
│   └── compliance/         # Compliance monitoring
├── templates/              # Django templates
├── static/                 # Static assets
├── docs/                   # Project documentation
├── .agent-os/             # Agent OS integration
└── blackcoral/            # Django project settings
```

### Running Tests

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test apps.core

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

### Code Quality

```bash
# Format code
black .

# Lint code
flake8 .

# Type checking (if using mypy)
mypy .
```

## Agent OS Integration

BLACK CORAL includes Agent OS integration for multi-agent workflow orchestration:

- **Research Agent**: Monitors APIs and processes opportunities
- **Analysis Agent**: Generates AI-powered summaries and analysis
- **Compliance Agent**: Monitors regulatory compliance
- **QA Agent**: Validates content quality
- **Submission Agent**: Coordinates proposal assembly

See `.agent-os/README.md` for detailed agent configuration.

## Test Coverage Analysis

Recent comprehensive test coverage analysis reveals:

- **12 Django apps** with 224 test files
- **7 apps require test coverage**: workflows, agents, compliance, collaboration, core, ai_features, api
- **731+ test methods** with proper mocking patterns
- **Excellent fixture setup** with comprehensive test utilities
- **Priority areas**: workflow orchestration, agent coordination, compliance validation

See our [Test Coverage Improvement Plan](docs/test_coverage_analysis.md) for detailed recommendations.

## Deployment

### Production Checklist

- [ ] Set `DEBUG=False` in production
- [ ] Configure proper database credentials
- [ ] Set up Redis for production
- [ ] Configure file storage (AWS S3, etc.)
- [ ] Set up monitoring and logging
- [ ] Configure backup procedures
- [ ] Set up SSL certificates
- [ ] Configure CDN for static assets

### Deployment Options

1. **AWS Elastic Beanstalk**: Simplified deployment with autoscaling
2. **Docker + Kubernetes**: Container orchestration for scalability
3. **Traditional VPS**: Manual deployment with nginx/gunicorn

## Documentation

- [Project Requirements](docs/project_requirements_document.md)
- [Tech Stack Details](docs/tech_stack_document.md)
- [Development Roadmap](DEVELOPMENT_ROADMAP.md)
- [Security Guidelines](docs/security_guideline_document.md)
- [API Documentation](docs/api_documentation.md) (Coming soon)

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes and add tests
4. Run code quality checks: `black .` and `flake8 .`
5. Commit changes: `git commit -m "Description"`
6. Push to branch: `git push origin feature-name`
7. Create a Pull Request

## Security

BLACK CORAL handles sensitive government contracting data. Please:

- Never commit API keys or secrets
- Follow security guidelines in `docs/security_guideline_document.md`
- Report security issues privately to the development team
- Use environment variables for all configuration
- Keep dependencies updated

## License

This project is developed for internal government use. See LICENSE file for details.

## Support

For technical support or questions:

- Check the [documentation](docs/)
- Review [troubleshooting guide](docs/troubleshooting.md) (Coming soon)
- Contact the development team

---

**BLACK CORAL** - Streamlining Government Contracting Through AI-Powered Workflows
