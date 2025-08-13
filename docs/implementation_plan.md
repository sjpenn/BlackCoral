# Implementation plan

## Phase 1: Environment Setup

1. **Prevalidation**: Check if current directory contains `manage.py` or `.git` to avoid reinitializing an existing project. If found, abort setup. (Derived from general prevalidation best practice)
2. Install Python 3.11.4 if not present (**Tech Stack: Backend**).
   - Validation: Run `python --version` and confirm `Python 3.11.4`.
3. Create and activate a virtual environment in project root:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # macOS/Linux
   .\.venv\Scripts\activate  # Windows
   ```
   (Tech Stack: Backend)
4. Install Django 5.2 and psycopg2-binary exactly:
   ```bash
   pip install Django==5.2 psycopg2-binary==2.9.10
   ```
   (Tech Stack: Backend)
5. Install Docker Engine if absent to host PostgreSQL 15.3 container (**Tech Stack: Database**).
   - Validation: Run `docker --version` and check `Docker version 20.x`.
6. Pull and run PostgreSQL 15.3 container:
   ```bash
   docker run --name black_coral_db -e POSTGRES_USER=blackcoral -e POSTGRES_PASSWORD=securepass -e POSTGRES_DB=black_coral -p 5432:5432 -d postgres:15.3
   ```
   (Tech Stack: Database)
   - Validation: Run `docker ps` and verify `black_coral_db` is running.
7. Create a `cursor_metrics.md` file in the root and refer to `cursor_project_rules.mdc` before populating it (**Tools: Cursor**).
8. Commit initial environment files:
   ```bash
   git init
   echo ".venv/" >> .gitignore
   git add .gitignore cursor_metrics.md
   git commit -m "chore: initial environment setup"
   ```
   (General best practice)

## Phase 2: Frontend Development

9. Create Django project and application:
   ```bash
   django-admin startproject black_coral .
   python manage.py startapp opportunities
   ```
   (Project Overview: Application Name + Tech Stack: Backend)
10. Create `templates/base.html` and add HTMX and Alpine.js via CDN:
    ```html
    <!-- templates/base.html -->
    <!DOCTYPE html>
    <html>
      <head>
        <script src="https://unpkg.com/htmx.org@1.9.5"></script>
        <script src="https://unpkg.com/alpinejs@3.12.0" defer></script>
      </head>
      <body>
        {% block content %}{% endblock %}
      </body>
    </html>
    ```
    (Project Overview: User Interface)
11. Create `templates/opportunities/filter.html` with a form for NAICS codes (multi-select up to 25), Title, Agency, Capability set, and wrap results in `<div id="results" hx-get>`. (Key Features: Opportunity Retrieval)
12. Define a Django Form in `opportunities/forms.py`:
    ```python
    from django import forms
    class OpportunityFilterForm(forms.Form):
        naics_codes = forms.MultipleChoiceField(...)  # limit=25
        title = forms.CharField(required=False)
        agency = forms.CharField(required=False)
        capability_set = forms.CharField(required=False)
    ```
    (Key Features: Opportunity Retrieval)
13. Add URL route in `black_coral/urls.py`:
    ```python
    from opportunities.views import OpportunityFilterView
    urlpatterns = [
      path("opportunities/", OpportunityFilterView.as_view(), name="opportunity-filter"),
    ]
    ```
    (Tech Stack: Backend)
14. Implement `OpportunityFilterView` in `opportunities/views.py` to render form and process AJAX requests returning partial HTML. (Key Features: Opportunity Retrieval)
15. Add Alpine.js interactivity in `filter.html` for filtering controls using `x-data`, `x-on:change`. (Project Overview: User Interface)
16. **Validation**: Run Django development server and navigate to `/opportunities/`, verify that the filter form loads, and that typing triggers HTMX requests.
    ```bash
    python manage.py runserver
    ```
17. Commit all frontend templates and forms:
    ```bash
    git add templates/* opportunities/forms.py opportunities/views.py black_coral/urls.py
    git commit -m "feat: implement opportunity filter UI with HTMX and Alpine.js"
    ```

## Phase 3: Backend Development

18. Configure PostgreSQL connection in `black_coral/settings.py`:
    ```python
    DATABASES = {
      'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'black_coral',
        'USER': 'blackcoral',
        'PASSWORD': 'securepass',
        'HOST': 'localhost',
        'PORT': '5432',
      }
    }
    ```
    (Tech Stack: Backend)
19. Define data models in `opportunities/models.py`:
    ```python
    class NAICSCode(models.Model):
        code = models.CharField(max_length=6, unique=True)
        related_codes = models.ManyToManyField('self', blank=True)
    class Opportunity(models.Model):
        title = models.CharField(max_length=255)
        agency = models.CharField(max_length=255)
        capability_set = models.TextField()
        naics_codes = models.ManyToManyField(NAICSCode)
    ```
    (Key Features: Shared Knowledge Base)
20. Create and run migrations:
    ```bash
    python manage.py makemigrations
    python manage.py migrate
    ```
    - Validation: Confirm tables exist by connecting with `psql -h localhost -U blackcoral -d black_coral`
21. Configure file uploads in `settings.py`:
    ```python
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'
    ```
    (Key Features: Detailed Evaluation)
22. Create management command to import NAICS codes into `opportunities/management/commands/import_naics.py`. (Data Sources: Plan to import NAICS code data)
23. **Validation**: Run `python manage.py import_naics` and verify NAICSCode count in Django shell:
    ```bash
    python manage.py shell
    >>> from opportunities.models import NAICSCode; NAICSCode.objects.count()
    ```
24. Install `requests` library:
    ```bash
    pip install requests==2.31.0
    ```
    (Tech Stack: Backend)
25. Implement external API clients in `opportunities/services/samgov.py`, `usaspending.py`, and `gao.py` with methods `fetch_opportunities()`, `get_spending()`, etc. (Key Features: Integration with sam.gov, USASpending.gov, GAO)
26. **Validation**: In Django shell, import and call each service with sample parameters and ensure no exceptions are thrown.
27. Create stubs for AI agents in `opportunities/agents/claude_code_agent.py`, `gemini_agent.py`, and `cursor_agent.py` with base class `AgentBase` defining `generate_content()` (Key Features: AI-Driven Content Generation)
28. Install any required AI SDKs (`openai`, `google-cloud-aiplatform`) as needed. (Tech Stack: AI)
29. **Validation**: Write and run a simple script under `/scripts/test_agents.py` that instantiates each agent and prints stub output.

## Phase 4: Integration

30. In `OpportunityFilterView`, connect form results to `Opportunity.objects.filter(...)` and external API calls to enrich data. (App Flow: Step "Opportunity Retrieval and Filtering")
31. In `templates/opportunities/filter.html`, render compliance and quality flags next to each result using agent outputs. (Key Features: Compliance Monitor Agent + Quality Assurance Agent)
32. Configure Django’s built-in authentication and permissions in `settings.py` and create user roles via `manage.py createsuperuser` and the admin interface. (Project Overview: User Roles and Permissions)
33. **Validation**: Log in as Admin, Researcher, Reviewer, etc., and confirm RBAC controls page access by visiting restricted URLs.
34. Commit integration changes:
    ```bash
    git add opportunities services templates
    git commit -m "feat: integrate backend filtering, compliance, and RBAC"
    ```

## Phase 5: Deployment

35. Create `Dockerfile` in project root for Django app:
    ```dockerfile
    FROM python:3.11.4-slim
    WORKDIR /app
    COPY requirements.txt ./
    RUN pip install -r requirements.txt
    COPY . .
    CMD ["gunicorn", "black_coral.wsgi:application", "--bind", "0.0.0.0:8000"]
    ```
    (General deployment best practice)
36. Create `docker-compose.yml` to orchestrate Django and PostgreSQL 15.3:
    ```yaml
    version: '3.8'
    services:
      db:
        image: postgres:15.3
        environment:
          POSTGRES_USER: blackcoral
          POSTGRES_PASSWORD: securepass
          POSTGRES_DB: black_coral
      web:
        build: .
        ports:
          - '8000:8000'
        depends_on:
          - db
    ```
    (General deployment best practice)
37. **Validation**: Run `docker-compose up --build -d` and verify both services are healthy in `docker ps`.
38. Add GitHub Actions CI at `.github/workflows/ci.yml` to run `pip install`, `flake8`, `pytest` on pull requests. (CI/CD best practice)
39. **Validation**: Push a test commit and verify CI passes on GitHub.
40. Document deployment instructions in `DEPLOYMENT.md` with steps to deploy to chosen cloud (e.g., AWS Elastic Beanstalk in `us-east-1`). (General deployment best practice)

---

*Total Steps: 40*