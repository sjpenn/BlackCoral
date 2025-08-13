# BLACK CORAL MVP: Step-by-Step Implementation Plan

Below is a phased, sprint-based plan for delivering the BLACK CORAL MVP. Security and compliance best practices are woven into each phase to ensure we build a robust, resilient, and trustworthy system from day one.

---

## Phase 0: Project Initialization & Foundations

**Goals:** Establish repositories, development workflows, and core architectural decisions.

1. Repository & CI/CD Setup
   - Create Git repositories (backend, frontend, infra).
   - Enforce branch protection rules; require PR reviews, signed commits.
   - Configure CI pipelines (GitHub Actions/GitLab CI) to run linting, type checks, and security scans (SAST, dependency scanning).
   - Generate lockfiles (`Pipfile.lock`, `poetry.lock`).

2. Environment & Secrets Management
   - Define `.env.example` with placeholders for DATABASE_URL, API keys (sam.gov, USASpending.gov, GAO, etc.), AI credentials.
   - Integrate a secrets manager (e.g., AWS Secrets Manager or Vault) for production.
   - Enforce secure defaults: HTTPS for all environments; debug off in non-dev.

3. Architecture & Design Docs
   - Draft high-level system diagram: Django backend, HTMX/Alpine frontend, AI abstraction layer, external APIs, PostgreSQL.
   - Define role model (Admin, Researcher, Reviewer, Compliance Monitor, QA, Submission Agent).
   - Detail data flow: from external sources → ingestion → AI layer → storage → UI.

4. Security Baseline
   - Harden Django settings: `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `X_FRAME_OPTIONS`.
   - Install security headers middleware (django-csp, django-secure).
   - Configure CSP, X-Content-Type-Options, Referrer-Policy.

---

## Phase 1: Core Authentication & RBAC

**Goals:** Implement user management, roles, and permissions before any data functionality.

1. User Model & Password Policies
   - Extend `AbstractBaseUser` if needed; else use `User` with email as unique identifier.
   - Enforce strong passwords via `AUTH_PASSWORD_VALIDATORS` (min length, complexity).
   - Use Argon2 for password hashing (`django-argon2`).

2. Session & Token Security
   - Configure session timeouts (idle + absolute).
   - Protect against session fixation (`SESSION_SAVE_EVERY_REQUEST`).
   - Implement optional MFA stub (TOTP) for future expansion.

3. Role-Based Access Control
   - Create `Role` and `Permission` models or use `django-guardian`.
   - Define per-model and per-view permissions.
   - Decorate sensitive endpoints with `@permission_required`.

4. Automated Tests
   - Write unit tests covering signup/login flows.
   - Test role assignment and authorization failures.

---

## Phase 2: Data Modeling & Shared Knowledge Base

**Goals:** Define data structures for opportunities, NAICS codes, capabilities, and the knowledge base.

1. Database Schema
   - Models: `Opportunity`, `NAICSCode`, `Capability`, `Evaluation`, `KnowledgeEntry`, `DocumentAttachment`.
   - Relations: Many-to-Many for opportunities ↔ NAICS, opportunities ↔ capabilities.
   - Unique constraints, non-nullable fields, cascade rules.

2. NAICS Data Import
   - Build management command to load NAICS hierarchy from CSV/JSON.
   - Implement foreign key relationships to allow auto-inclusion of related codes.

3. Knowledge Base
   - Schema: `KnowledgeEntry { title, content, tags, created_by, timestamp }`.
   - Versioning or soft deletes for audit trail.

4. Security Controls
   - Enforce server-side validation on all fields (`Model.clean()`, DRF serializers).
   - Sanitize rich text (`bleach` for HTML inputs).

5. Tests & Migrations
   - Create migrations with review.
   - Write model tests for constraints and validation.

---

## Phase 3: External API Integration & Data Ingestion

**Goals:** Connect to sam.gov, USASpending.gov, GAO, and OSDBU endpoints; normalize responses.

1. API Key Management
   - Store keys in environment variables or secrets manager.
   - Rotate keys periodically; log access attempts.

2. Connector Layer (Django App: `connectors`)
   - Define an interface: `BaseConnector.fetch_opportunities(filters)`.
   - Implement connectors for each data source using `requests` with retries and timeouts.
   - Rate-limit calls to avoid DoS; cache responses (Redis) where appropriate.

3. Data Normalization
   - Map external fields to our `Opportunity` model.
   - Validate incoming JSON schema (`jsonschema` or Pydantic).

4. Edge Case Handling
   - Gracefully handle missing fields, malformed responses.
   - Fail securely: log errors without exposing stack traces.

5. Scheduled Tasks
   - Use Celery/Redis or Django-Q for periodic ingestion jobs.
   - Monitor job status and performance metrics.

---

## Phase 4: AI Abstraction & Processing Layer

**Goals:** Build a unified service to call Claude Code, Gemini, and Cursor for summarization and evaluation.

1. AI Service Interface
   - Define `AIClient` with methods: `summarize(text)`, `evaluate(requirement, past_performance)`, etc.
   - Load model-specific configs (endpoints, auth) from secure settings.

2. Implementations
   - `ClaudeClient`, `GeminiClient`—wrap official SDKs or REST APIs.
   - Fallback logic: if one service fails, route to another.

3. Rate Limiting & Retry
   - Enforce per-service rate limits.
   - Exponential backoff on failures.

4. AI Task Queue
   - Offload heavy requests to Celery workers.
   - Stream partial results via WebSockets or HTMX polling for progress feedback.

5. Security & Privacy
   - Mask PII before sending to AI.
   - Audit logs of AI inputs/outputs (redacted).
   - TLS for all AI API calls.

---

## Phase 5: Opportunity Evaluation & Document Handling

**Goals:** Enable extraction of SOW/PWS, full evaluation workflows, and secure file uploads.

1. Document Uploads
   - Accept PDF, DOCX, HTML, XLS, TXT, images, ZIP.
   - Validate MIME type & magic bytes.
   - Scan uploads for malware (ClamAV).
   - Store files outside web root; serve via signed URLs.

2. Text Extraction
   - Use Apache Tika or specialized parsers for each format.
   - Sanitize outputs; remove scripts from HTML.

3. Evaluation Workflow
   - UI flows for matching requirements → capabilities → past performance.
   - Use HTMX to dynamically add/remove evaluation rows.
   - Save drafts; auto-save using debounced AJAX.

4. Compliance & QA Flags
   - Implement rule engine to flag missing FAR elements.
   - Display real-time alerts in UI; color-coded severity.

5. Tests
   - Unit tests for file validation, parsing logic.
   - Integration tests for evaluation endpoints.

---

## Phase 6: Frontend & User Experience

**Goals:** Build interactive UI using Django templates, HTMX, and Alpine.js.

1. Base Templates & Layout
   - Implement secure template context (
     - Autoescape on,
     - No inline JavaScript injection).
   - Include global HTMX configuration and Alpine setup.

2. HTMX Interactions
   - Filter panel: lazy-load agency, NAICS selectors.
   - Inline editing for evaluations, knowledge entries.
   - Real-time compliance pop-ups via SSE or HTMX polling.

3. Alpine.js Components
   - Modal dialogs (upload, AI prompts).
   - Dynamic form validations.
   - State management for review checklists.

4. Accessibility & Styling
   - Follow WCAG 2.1 AA guidelines.
   - Use a design system or Tailwind CSS for consistency.

5. Security Considerations
   - Output encode all user data.
   - Use Anti-CSRF tokens on all POST forms.

---

## Phase 7: Quality Assurance & Security Testing

**Goals:** Validate functionality, performance, and security before internal release.

1. Automated Testing
   - Expand unit, integration, and end-to-end tests (Selenium/Playwright).
   - Incorporate security tests: SQLi, XSS, CSRF validation.

2. Performance Benchmarks
   - Load test key endpoints (ingestion, AI calls, dashboards) using Locust.
   - Optimize DB indexes, query plans.

3. Vulnerability Scanning
   - Run SCA tools (Dependabot, Snyk).
   - Address high/critical findings immediately.

4. Penetration Testing Stub
   - Prepare an internal pentest checklist.
   - Schedule third-party assessment if budget allows.

---

## Phase 8: Deployment & Handover

**Goals:** Deliver an internal prototype; hand off to users for feedback.

1. Infrastructure Provisioning
   - Use Terraform/CloudFormation for reproducible infra.
   - Harden servers: disable unused ports, enforce SSH key auth.

2. Continuous Deployment
   - Define staging and prod environments with separate secrets.
   - Automate DB migrations.

3. Monitoring & Alerting
   - Integrate Prometheus/Grafana or equivalent.
   - Set alerts for error rates, latency spikes, CPU/memory.

4. Documentation & Training
   - Publish developer docs: architecture, coding standards, onboarding guide.
   - Create user manual for Admins and Researchers.

5. Internal Launch
   - Conduct stakeholder demos.
   - Collect feedback; triage feature requests and bugs.

---

**Next Steps:**
- Assign teams to each phase and define sprint durations (e.g., 2-week sprints).
- Set up a backlog in Jira/Trello to track tasks and dependencies.
- Kick off Phase 0 immediately to establish the secure foundation and begin sprint 1.

Let me know if you’d like to adjust priorities, add more detail to any phase, or discuss resource allocation.