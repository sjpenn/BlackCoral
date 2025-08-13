# Tech Stack Document for BLACK CORAL

This document explains, in everyday language, the technology choices behind the BLACK CORAL MVP. You don’t need a technical background to understand why we picked each tool and how they work together to build a fast, reliable prototype for government contracting workflows.

## 1. Frontend Technologies

We want a smooth, desktop-like experience in the browser without the complexity of a heavy JavaScript framework. Here’s how we do it:

- **Django Templates**
  - Built-in HTML templates that come with Django 5.2.
  - Let us generate pages on the server, then enhance them in the browser.

- **HTMX**
  - Loads small pieces of HTML on demand, without reloading the whole page.
  - Makes forms, lists, and dashboards update instantly when you change filters or click buttons.
  - Keeps things simple—no full-page reloads or big JavaScript bundles.

- **Alpine.js**
  - A lightweight JavaScript library for small interactive bits (dropdowns, modals, inline edits).
  - Works alongside HTMX to handle user interactions without React or Vue.

- **CSS / Styling**
  - Basic, clean styles driven by a simple CSS setup (you can plug in Tailwind or another library later).
  - Ensures readability and a professional look that aligns with government contract standards.

Why these choices help you:
- Pages feel snappy because we only update parts that change.
- The code is easier to maintain—no huge JavaScript frameworks to learn.
- Users on slower connections get a better experience.

## 2. Backend Technologies

Our server side does the heavy lifting: talking to external data sources, storing information, running AI agents, and enforcing user permissions.

- **Python & Django 5.2**
  - Python is easy to read and widely used for web apps and AI integrations.
  - Django provides a mature web framework with built-in patterns for URLs, views, models, and templates.

- **Django Authentication & Role-Based Access Control**
  - Handles login, password security, and user sessions out of the box.
  - We define roles (Admin, Researcher, Reviewer, Compliance Monitor, QA, Submission Agent) with clear permissions.

- **PostgreSQL**
  - A reliable, open-source relational database for storing opportunities, SOW/PWS text, NAICS codes, user data, AI-generated drafts, and compliance logs.
  - Supports full-text search and advanced queries for fast lookups.

- **Custom Django Data Models (Shared Knowledge Base)**
  - Tailored tables to hold requirements, pricing data, draft content, compliance checks, partner matches, and more.
  - Ensures every "agent" (process or user) reads and writes to the same up-to-date data.

- **Local File Storage**
  - Saves PDFs, Word docs, ZIPs, images, and other attachments fetched from URLs.
  - Allows OCR and parsing so that scanned documents become searchable text.

- **Internal AI Integration Layer**
  - Wraps calls to external AI coding and writing assistants (Claude Code, Gemini, free-cursor) behind a single internal API.
  - Keeps our code clean and makes switching or adding AI services straightforward.

## 3. Infrastructure and Deployment

To get BLACK CORAL up and running—and keep it reliable as we improve it—we chose straightforward hosting and automated workflows.

- **Version Control with Git**
  - Every line of code is tracked in a Git repository (e.g., GitHub or GitLab).
  - Ensures we can roll back mistakes and collaborate safely.

- **CI/CD Pipeline (e.g., GitHub Actions or GitLab CI)**
  - Automatically runs tests and linting whenever code is pushed.
  - Builds and deploys the app to our hosting environment after passing checks.

- **Containerization (optional, Docker)**
  - Encapsulates the Django app, database, and services in containers for consistent deployment.
  - You can spin up the entire stack locally or in the cloud with a single command.

- **Hosting Platform**
  - For an MVP, lightweight platforms like Heroku, AWS Elastic Beanstalk, or DigitalOcean work well.
  - We can easily switch providers once we scale.

How this helps:
- Developers get immediate feedback on code changes.
- Deployments are repeatable and less error-prone.
- We can scale services (web, database) independently as usage grows.

## 4. Third-Party Integrations

To power real-time opportunity data and AI-driven content, we connect to: 

- **sam.gov API**
  - Retrieves new government contracting opportunities based on NAICS codes, titles, agencies, etc.

- **USASpending.gov API**
  - Pulls spending data, agency budgets, and past performance metrics.

- **GAO API (and other public sources)**
  - Fetches relevant GAO reports, forecasts, and oversight information.

- **OSDBU / Small Business Office Forecasts**
  - Integrate agency-specific initiatives when available via public feeds or downloadable files.

- **Claude Code, Gemini, Free-Cursor**
  - AI helpers that generate draft proposal sections, compliance checks, summaries, and pricing models.
  - Accessed via our internal AI API—so the rest of the app doesn’t need to know which AI service we’re using.

Benefits of these integrations:
- Automates research steps that used to take hours.
- Keeps data fresh by pulling directly from official sources.
- Provides a centralized view of opportunity, compliance, and past performance.

## 5. Security and Performance Considerations

We built BLACK CORAL with best practices to protect sensitive data and keep the app responsive:

- **Authentication & Authorization**
  - Secure login via Django’s authentication.
  - Role-based access control ensures users only see and edit what they should.

- **Secure Data Storage**
  - Database credentials and API keys stored in environment variables (never in code).
  - HTTPS everywhere to protect data in transit.

- **Continuous Compliance Monitoring**
  - Real-time compliance checks using AI agents to catch issues early.
  - Inline flags and pop-ups alert users to critical errors.

- **Performance Optimizations**
  - Database indexes on common queries (NAICS filters, opportunity IDs).
  - HTMX partial updates reduce full-page reloads and bandwidth.
  - Caching of static assets and API responses where appropriate.

- **Logging & Monitoring**
  - Track application errors and usage metrics in a centralized log.
  - Alerts for failed background tasks (e.g., document parsing, AI calls).

## 6. Conclusion and Overall Tech Stack Summary

BLACK CORAL’s MVP tech stack is designed to deliver a high-impact proof of concept with minimal overhead. By choosing Django 5.2, HTMX, and Alpine.js, we get a modern, interactive interface without the complexity of heavier JavaScript frameworks. PostgreSQL and custom Django models give us a reliable shared knowledge base for all agents and users. Real-time data comes from sam.gov, USASpending.gov, GAO, and other public APIs, while AI-powered content generation speeds up drafting and compliance checking.

This combination ensures:
- Rapid development and iteration for an internal prototype.
- A clear migration path to a full production system when you’re ready.
- A user experience that feels fast and intuitive for non-technical and technical users alike.

Together, these choices align with BLACK CORAL’s goal: to transform the government contracting workflow into a dynamic, parallelized, AI-augmented process that gets proposals out the door faster and with fewer errors.

---

*End of Tech Stack Document*