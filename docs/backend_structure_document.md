# Backend Structure Document for BLACK CORAL

This document describes the backend setup for the BLACK CORAL MVP. It explains how everything fits together, from the core architecture to hosting, security, and maintenance. By the end, you’ll have a clear picture of the backend system without needing a deep technical background.

## 1. Backend Architecture

### Overall Design
- We’re using Django 5.2 (a popular Python web framework) as the core. Django follows the Model-View-Controller (MVC) pattern, which helps us keep business logic, data models, and user interfaces separate.
- All backend features (authentication, opportunity retrieval, document parsing, AI integrations, reporting) live in their own Django “apps.” This modular approach makes it easy to add or update features.
- For AI calls (Claude Code, Gemini), we wrap each provider behind an internal service layer. This lets us swap or add AI engines without touching the rest of the code.

### Scalability, Maintainability, Performance
- **Scalability** is achieved by:
  - Horizontally scaling Django servers behind a load balancer.
  - Offloading long-running tasks (document parsing, API polling) to background workers or scheduled jobs.
- **Maintainability** comes from Django’s clear conventions, modular apps, and reusable components (models, views, templates).
- **Performance** is boosted by:
  - Caching frequent queries (especially external API calls) in Redis.
  - Serving static assets (CSS, JS) via a CDN.

## 2. Database Management

### Technologies Used
- **Database Type:** Relational (SQL)
- **System:** PostgreSQL
- **File Storage:** Local file system (for MVP; can switch to S3 or similar later)

### Data Structure & Access
- Core tables include:
  - **Users & Roles** (Admin, Researcher, Reviewer, Compliance Monitor, QA, Submission Agent)
  - **Opportunities** (basic info, SOW text, metadata)
  - **NAICS Codes** (25+ codes and their relationships)
  - **Documents** (uploads, parsed content, file paths)
  - **AI Summaries** (text snippets, timestamps, authoring engine)
  - **Compliance Flags** and **QA Issues** (type, severity, linked records)
  - **Submission Logs** (timestamps, SAM API responses)
- Django’s ORM handles CRUD operations, transactions, and connection pooling. We tune connection settings for peak loads.
- We apply indexing on key columns (e.g., opportunity ID, NAICS code) to speed up lookups.

## 3. Database Schema

### Human-Readable Schema Overview
- **User**: Email, password, name, role
- **Role**: Name, description, permissions set
- **NAICSCode**: Code, description, parent/child relationships
- **Opportunity**: Title, agency, published date, SOW text, NAICS code reference
- **Document**: File name, file type, storage path, linked opportunity
- **AISummary**: Related document or requirement, engine used, summary text, created timestamp
- **ComplianceFlag**: Linked requirement, rule code, flag status, comments
- **Rating**: Past performance score, partner match score, linked opportunity
- **SubmissionLog**: Opportunity ID, submission timestamp, API response details

### SQL Schema (PostgreSQL)
```sql
-- Users & Roles
table role (
  id SERIAL PRIMARY KEY,
  name VARCHAR(50) UNIQUE,
  description TEXT
);

table app_user (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password VARCHAR(255) NOT NULL,
  name VARCHAR(100),
  role_id INT REFERENCES role(id)
);

-- NAICS Codes
table naics_code (
  id SERIAL PRIMARY KEY,
  code VARCHAR(10) UNIQUE NOT NULL,
  description TEXT,
  parent_id INT REFERENCES naics_code(id)
);

-- Opportunities
table opportunity (
  id SERIAL PRIMARY KEY,
  title TEXT,
  agency VARCHAR(100),
  published_date DATE,
  sow TEXT,
  naics_code_id INT REFERENCES naics_code(id)
);

-- Documents
table document (
  id SERIAL PRIMARY KEY,
  opportunity_id INT REFERENCES opportunity(id),
  file_name VARCHAR(255),
  file_type VARCHAR(50),
  file_path TEXT,
  uploaded_at TIMESTAMP DEFAULT now()
);

-- AI Summaries
table ai_summary (
  id SERIAL PRIMARY KEY,
  document_id INT REFERENCES document(id),
  engine VARCHAR(50),
  summary TEXT,
  created_at TIMESTAMP DEFAULT now()
);

-- Compliance Flags
table compliance_flag (
  id SERIAL PRIMARY KEY,
  opportunity_id INT REFERENCES opportunity(id),
  rule_code VARCHAR(50),
  status VARCHAR(20),
  comments TEXT
);

-- Ratings
table rating (
  id SERIAL PRIMARY KEY,
  opportunity_id INT REFERENCES opportunity(id),
  past_performance_score INT,
  partner_match_score INT
);

-- Submission Logs
table submission_log (
  id SERIAL PRIMARY KEY,
  opportunity_id INT REFERENCES opportunity(id),
  submitted_at TIMESTAMP DEFAULT now(),
  response JSONB
);
```

## 4. API Design and Endpoints

### Approach
- We follow RESTful conventions using Django’s built-in views and/or Django REST Framework for JSON endpoints.
- HTMX-driven interactions use small JSON or HTML snippets for partial page updates.

### Key Endpoints
- **Authentication**
  - `POST /api/login/` → obtain session cookie
  - `POST /api/logout/`
- **Opportunities**
  - `GET /api/opportunities/` → list with filters (NAICS, keywords, agency)
  - `GET /api/opportunities/{id}/` → detail + SOW + parsed docs
- **Document Upload & Parsing**
  - `POST /api/opportunities/{id}/documents/` → upload file
  - `GET /api/opportunities/{id}/documents/{doc_id}/parse/` → trigger parse (PDF, Word, OCR)
- **AI Summaries**
  - `POST /api/ai/summarize/` → send text or doc ID, get summary
- **Compliance & QA**
  - `POST /api/compliance/check/` → run checks on requirement set
  - `GET /api/qc/issues/` → list flagged issues
- **Submission**
  - `POST /api/submit/` → bundle volumes, send to SAM API, return confirmation

## 5. Hosting Solutions

- **Cloud Provider:** AWS (for reliability and easy scaling)
  - **Compute:** EC2 instances running Docker + Gunicorn + Nginx
  - **Database:** Amazon RDS for PostgreSQL (managed backups, multi-AZ)
  - **File Storage:** EBS volumes (for MVP local storage)
- **Benefits**
  - High availability and self-healing infrastructure
  - Easy to scale up/down per demand
  - Pay-as-you-go cost model

## 6. Infrastructure Components

- **Load Balancer:** AWS Application Load Balancer distributes traffic across EC2 instances.
- **Cache Layer:** Redis (ElastiCache) for:
  - Caching external API responses (SAM.gov, USASpending.gov)
  - Session storage and rate-limit tracking
- **CDN:** CloudFront to serve static assets (CSS, JS) and speed up page loads.
- **Background Tasks:** Django management commands or a simple worker (e.g., RQ) to handle document parsing and scheduled API polling.

## 7. Security Measures

- **Authentication & Authorization:** Django’s built-in system with role-based permissions.
- **Encryption:** HTTPS/TLS via Let’s Encrypt certificates on Nginx.
- **Data Protection:** Database encryption at rest (RDS), EBS encryption.
- **Input Sanitization:** Automatic escaping in Django templates; validation on all forms and API inputs.
- **API Keys & Secrets:** Stored securely in environment variables or AWS Secrets Manager.
- **Compliance:** Logging all access and changes for auditability. Regular reviews to align with FAR and agency rules.

## 8. Monitoring and Maintenance

- **Logging:** Centralized logs via AWS CloudWatch or ELK stack (Elasticsearch, Logstash, Kibana).
- **Error Tracking:** Sentry for real-time exception alerts and stack traces.
- **Performance Metrics:** CloudWatch or New Relic to monitor CPU, memory, response times.
- **Backups & Recovery:** Automated daily RDS snapshots and weekly full EBS backups.
- **Maintenance Strategy:**
  - Weekly dependency updates and security patching.
  - Monthly database health checks and index tuning.
  - Scheduled downtime windows communicated via system dashboard.

## 9. Conclusion and Overall Backend Summary

The BLACK CORAL backend uses Django and PostgreSQL to deliver a modular, scalable, and secure environment. By combining RESTful APIs, real-time HTMX updates, and AI integrations, we streamline government contracting tasks. AWS hosting, caching, and monitoring ensure reliability and performance. Role-based access, encrypted communications, and audit logs keep data safe and compliant. This setup not only meets the MVP goals but provides a solid foundation for future production growth.