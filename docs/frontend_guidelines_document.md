# Frontend Guideline Document

This document explains how the BLACK CORAL frontend is built, why we made certain choices, and how you can work with it day-to-day—even if you’re not a front-end expert.

## 1. Frontend Architecture

### 1.1 Overview
- We use **Django’s template engine** to render pages on the server.  This keeps the first load very fast and simplifies SEO and security.  
- For dynamic, partial page updates without full reloads, we use **HTMX**.  HTMX lets us request snippets of HTML from Django and swap them into the page.  
- For small amounts of client-side interactivity (toggles, modals, form enhancements), we use **Alpine.js**.  Alpine is lightweight (~10 KB) and easy to learn, so we avoid a heavier framework.  
- Styling is done with **Tailwind CSS** (utility-first), plus a small custom CSS file for overrides.  We configure Tailwind via a `tailwind.config.js` file and purge unused styles in production.

### 1.2 Scalability, Maintainability, Performance
- **Scalability**: Modular templates and HTMX endpoints mean we can add new features as self-contained “snippets.”  We don’t have one giant JavaScript bundle.
- **Maintainability**: Alpine components live next to their HTML markup, so you can see behavior and structure in the same place.  Tailwind’s utility classes reduce the need for multiple CSS files.  
- **Performance**: Server-side rendering gives a fast first paint.  HTMX updates only the parts that change.  Tailwind’s purge process and compressed static files keep download sizes small.

## 2. Design Principles

1. **Usability**: Clear labels, simple forms, inline help text.  We group related fields, use consistent button styles, and provide step-by-step progress indicators in workflows.
2. **Accessibility**: All interactive elements have appropriate ARIA roles and keyboard support.  We use semantic HTML (`<nav>`, `<main>`, `<section>`) and verify contrast ratios (WCAG AA).
3. **Responsiveness**: The layout adapts to mobile, tablet, and desktop breakpoints.  We use Tailwind’s responsive utilities (`sm:`, `md:`, `lg:`) to adjust spacing and visibility.
4. **Consistency**: Color, typography, and spacing follow guidelines in section 3.  Buttons, inputs, and alerts share the same patterns throughout.

## 3. Styling and Theming

### 3.1 Styling Approach
- **Tailwind CSS** (utility-first).  We avoid custom CSS class bloat by using prebuilt utilities.
- A small custom stylesheet (`custom.css`) holds any edge-case overrides.

### 3.2 Theming
- Themes are controlled via CSS custom properties in the root, configured in `tailwind.config.js`.  We support a single “modern professional” theme now, with room to add dark mode later.

### 3.3 Visual Style
- **Style**: Flat and modern, with occasional glassmorphism for modals or cards (semi-transparent background with subtle blur).

### 3.4 Color Palette
- Primary: `#1E3A8A` (indigo-800)
- Secondary: `#2563EB` (blue-600)
- Accent: `#F59E0B` (amber-500)
- Neutral (backgrounds and text):
  - Light bg: `#F3F4F6` (gray-100)
  - Dark text: `#111827` (gray-900)
  - Mid text: `#6B7280` (gray-500)

### 3.5 Typography
- **Font Family**: Inter (sans-serif) for body and headings.
- **Headings**: Bold weight, scale from 1.5rem (h2) to 3rem (h1).
- **Body Text**: 1rem, line-height 1.5.

## 4. Component Structure

### 4.1 Organization
- `/templates/components/` contains reusable HTML snippets (navigation, modals, cards).
- Each component has its own folder, with optional files:
  - `component.html` (markup)
  - `component.js` (Alpine logic, if needed)
  - `component.test.js` (unit or integration test)

### 4.2 Reuse and Composition
- Components are composed in higher-level templates:
  ```django
  {% include "components/cards/opportunity_card.html" with data=opportunity %}
  ```
- This approach avoids copy-pasting and makes updates easy.

### 4.3 Why Component-Based?
- Changes in one place update everywhere.
- Better collaboration: designers and developers can focus on small pieces.

## 5. State Management

### 5.1 Alpine.js for Local State
- Alpine.js stores simple boolean flags, form input values, or toggles directly in the HTML:
  ```html
  <div x-data="{ open: false }">
    <button @click="open = !open">Toggle</button>
    <div x-show="open">...content...</div>
  </div>
  ```

### 5.2 HTMX for Server-Driven State
- Rather than sync a large global store, we rely on HTMX requests.  Every action that changes data fires an HTMX request, the server updates the database, and returns the updated snippet.

### 5.3 Shared State (Advanced)
- If you need cross-component shared state on the client, you can use Alpine’s global store plugin (`Alpine.store('name', { ... })`).  Use sparingly.

## 6. Routing and Navigation

### 6.1 Django URLs + HTMX
- We define standard Django URL patterns in `urls.py`.
- HTMX-enabled links and forms include attributes like `hx-get`, `hx-post`, and `hx-target` to swap only parts of the page.

Example:
```html
<a href="/opportunities/" hx-get="/opportunities/" hx-target="#main-content">List Ops</a>
``` 

### 6.2 Navigation Structure
- **Header nav**: Main sections (Dashboard, Opportunities, Knowledge Base, Reports).
- **Sidebar** (desktop only): Contextual links for the current section (filters, settings, help).
- Breadcrumbs show the current position in the workflow.

## 7. Performance Optimization

1. **Tailwind PurgeCSS**: Removes unused utility classes in production builds.  
2. **Minification & Compression**: CSS and JS are minified; served with gzip or Brotli.
3. **HTMX Over Full Reloads**: Partial updates reduce bandwidth and speed up UI.
4. **Lazy Loading Images**: Use `loading="lazy"` on `<img>` tags for attachments or charts.
5. **Cache Control**: Static assets served with long cache lifetimes; HTML snippets have shorter TTL.
6. **Preconnect & Prefetch**: For third-party endpoints (e.g., Google Fonts) to reduce initial latency.

## 8. Testing and Quality Assurance

### 8.1 Unit and Integration Tests
- **Jest**: Test Alpine.js components and helper functions.
- **pytest-django**: Test template rendering and HTMX endpoints at the view level.

### 8.2 End-to-End Tests
- **Cypress** or **Playwright**: Simulate user workflows (login, filter opportunities, run AI summary).
- Tests run in CI on every pull request.

### 8.3 Accessibility Checks
- **axe-core** (via Cypress plugin) to catch color contrast or missing ARIA issues.

### 8.4 Linting
- **Prettier** for formatting.
- **ESLint** for JS (including Alpine.js patterns).
- **stylelint** for custom CSS.

## 9. Conclusion and Overall Frontend Summary

The BLACK CORAL frontend combines server-side rendering (Django templates) with modern tools (HTMX, Alpine.js, Tailwind CSS) to deliver a fast, maintainable, and user-friendly interface.  By following these guidelines, you’ll ensure that:
- UX is consistent and accessible.
- Components are reusable and easy to maintain.
- Performance stays high even as the app grows.

Unique Highlights:
- **HTMX-driven partial updates** let us avoid a heavy JavaScript bundle.
- **Alpine.js** keeps interactivity small and focused.
- **Tailwind CSS** ensures a consistent look with minimal custom CSS.

By sticking to these patterns, any developer can jump in and understand exactly how to build, style, and test new features in the BLACK CORAL frontend.  Let’s keep our UI fast, clear, and friendly for every user.