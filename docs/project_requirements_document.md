# BLACK CORAL – Project Requirements Document (PRD)

## 1. Project Overview

BLACK CORAL is an internal MVP web application designed to streamline and accelerate the U.S. government contracting workflow. It replaces a strictly sequential evaluation-capture-pricing-proposal process with a dynamic, concurrent agent-driven system. Users can define filters (like NAICS codes, agencies, capability sets), retrieve matching solicitations from sources such as sam.gov and USASpending.gov, and immediately begin analysis. The app extracts Statements of Work (SOW/PWS), parses attached documents (PDF, Word, ZIP, HTML, XLS, images), and stores everything in a shared Django-based knowledge base for real-time updates.

Built in Django 5.2 with HTMX and Alpine.js (no React), BLACK CORAL integrates AI assistants (via Claude Code and Gemini) to generate summaries, draft proposal sections, continuously check compliance (FAR, agency rules) and quality (grammar, style), and match requirements to past-performance records or partner firms. Success is measured by reduced cycle time (parallel tasks), up-to-date shared data, inline compliance alerts, and a smooth route from opportunity discovery to final submission.

## 2. In-Scope vs. Out-of-Scope

**In-Scope (MVP)**

*   Role-based authentication & permissions (Admin, Researcher, Reviewer, Compliance Monitor, QA, Submission Agent)
*   Opportunity filtering (up to 25 NAICS with automatic expansion, title, agency, capability sets, edge-case keywords)
*   Real-time queries to sam.gov, USASpending.gov, GAO APIs
*   SOW/PWS extraction and full-text storage (PDF, Word, HTML, XLS, ZIP, images)
*   AI-generated summaries next to capabilities
*   Past performance rating and partner-matching interface
*   Shared knowledge base (custom Django models) with HTMX-driven views
*   AI-driven content drafting and refinement via Claude Code, Gemini, free Cursor integration
*   Continuous compliance & quality monitoring with inline flags and dashboard
*   Final document assembly and submission workflow

**Out-of-Scope (Phase 2+)**

*   Mobile app or native clients
*   Advanced UX theming, branding beyond basic styling
*   Direct live NAICS API integration (we’ll import codes locally)
*   Full FedRAMP certification or external security accreditation
*   Complex budget modeling or forecasting beyond agency annual goals
*   Multi-tenant support or external partner portals

## 3. User Flow

Upon visiting BLACK CORAL, users log in through Django’s authentication system. Based on their role, they land on a dashboard showing relevant widgets: Admins manage saved filters and user roles; Researchers see new or pending opportunities; Reviewers get tasks awaiting sign-off; Compliance and QA monitors view live issue trackers; Submission Agents see proposals queued for assembly. From the dashboard, users navigate to the Opportunity Filtering page, adjust criteria (NAICS, agency, keywords), and watch results update in real time without page reloads.

Clicking a solicitation opens the Detailed Evaluation view. The full SOW/PWS is shown side by side with AI-generated summaries for each requirement. Researchers rate go/no-go confidence, review past-performance match scores, and initiate partner searches. Attached documents and URLs are fetched, parsed, and indexed in the local database. As users refine strategy, AI writing agents draft proposal sections while compliance and QA agents continuously flag issues inline. Once content volumes, pricing tables, and compliance checks are complete, the Submission Agent runs a final scan, incorporates edits, and dispatches the proposal, with status and confirmation logged for audit.

## 4. Core Features

*   **Authentication & RBAC**: Admin, Researcher, Reviewer, Compliance Monitor, QA, Submission Agent roles with scoped permissions.
*   **Opportunity Retrieval & Filtering**: Up to 25 NAICS codes (auto-expand to related codes), title, agency, capability, edge cases; live sam.gov, USASpending.gov, GAO queries.
*   **SOW/PWS Extraction & Parsing**: Support for PDF, DOCX, HTML, XLS, ZIP, images; OCR and metadata tagging; local storage.
*   **Shared Knowledge Base**: Custom Django models holding requirements, summaries, solution details, pricing, compliance matrix, draft content.
*   **AI-Generated Summaries & Drafting**: Integration with Claude Code, Gemini, free Cursor; initial drafts by AI agents, refinement by junior writers.
*   **Past-Performance & Partner Matching**: Rate requirements, match to internal or partner firm profiles, annotate confidence.
*   **Continuous Compliance Monitoring**: Real-time FAR and agency compliance checks with inline flags and severity levels.
*   **Quality Assurance**: Grammar, style, consistency scanning; inline suggestions; dashboard of open issues.
*   **HTMX & Alpine.js Interface**: Partial page updates, modals, and inline editing for a fluid, desktop-like experience.
*   **Final Assembly & Submission**: Automated compile of volumes, pricing, compliance scan, metadata confirmation, and API-driven dispatch to agencies.

## 5. Tech Stack & Tools

*   Backend: Python 3, Django 5.2, Django Authentication & Permissions, PostgreSQL, local file storage
*   Frontend: HTMX (HTML over the Wire), Alpine.js (lightweight interactions), Tailwind CSS (optional)
*   AI & Coding Assistants: Claude Code (local terminal integration), Google Gemini (via API), free Cursor (IDE plugin for code suggestions)
*   External APIs: sam.gov API, USASpending.gov API, GAO API (public endpoints)
*   Development: VS Code or preferred IDE, Docker for local environment, Git/GitHub for version control
*   Document Parsing: Tika or PyMuPDF (PDF), python-docx, zipfile, OCR (Tesseract)

## 6. Non-Functional Requirements

*   **Performance**: Page interactions under 300 ms; HTMX partial reloads under 200 ms; AI calls asynchronous with spinners.
*   **Security**: TLS 1.2+ for all traffic; encryption at rest for sensitive data; strict role-based access controls; audit logs for submissions.
*   **Scalability**: Modular Django apps; database migrations via Django’s migration framework; horizontal scaling of web workers.
*   **Reliability**: Automated daily backups; retry logic for external API calls; health checks on services.
*   **Usability**: Responsive UI for typical desktop resolutions; inline help tooltips; real-time feedback on actions.

## 7. Constraints & Assumptions

*   Access to sam.gov, USASpending.gov, GAO APIs will be provisioned (API keys available).
*   NAICS master list will be imported and maintained in-house; no real-time external NAICS updates in MVP.
*   Claude Code and Gemini quotas and availability are sufficient for development testing.
*   Application runs on Linux servers with Python 3.10+.
*   Users are on modern browsers (Chrome, Firefox, Edge) with JavaScript enabled.
*   MVP focuses on internal prototyping; production-grade security accreditations happen later.

## 8. Known Issues & Potential Pitfalls

*   **API Rate Limits**: Frequent sam.gov or USASpending.gov calls may hit thresholds. Mitigation: cache results, implement exponential backoff.
*   **Document Parsing Errors**: Complex PDFs or scanned docs may fail OCR. Mitigation: fallback to manual upload or highlight unparsed sections for user review.
*   **Concurrency Conflicts**: Multiple agents writing to the same database records. Mitigation: optimistic locking and transaction isolation in Django.
*   **AI Model Variability**: Summaries or draft content may be inconsistent. Mitigation: enforce prompt templates, human-in-the-loop edits.
*   **HTMX Complexity**: Partial updates could lead to stale states in nested components. Mitigation: clear component IDs and event hooks; rigorous QA.
*   **Compliance Matrix Drift**: Regulations or requirements change. Mitigation: store matrix entries in editable DB tables; Admins can update rules.

This PRD provides a clear blueprint for BLACK CORAL’s MVP development. It is the single source of truth for subsequent technical documents—tech stack details, frontend guidelines, backend structure, file organization, security policies, and implementation plans—ensuring consistency and eliminating ambiguity.
