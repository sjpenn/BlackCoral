# BLACK CORAL - Quick Start Guide

## 🚀 Start the Application

```bash
# Navigate to project directory
cd /Users/sjpenn/Sites/BlackCoral

# Run the development server
python manage.py runserver
```

## 🌐 Access the Application

### Landing Page
**URL**: http://localhost:8000/

- **Public access** - no authentication required
- Modern, professional showcase of BLACK CORAL capabilities
- Interactive HTMX-powered feature cards
- Click any feature card or "Access Platform" to be redirected to login

### Login & Authentication
**URL**: http://localhost:8000/auth/login/

**Demo Credentials**:
- Username: `admin`
- Password: `admin123`

### Dashboard (Protected)
**URL**: http://localhost:8000/dashboard/

- **Requires authentication**
- Role-based interface showing widgets based on user permissions
- Six user roles: Admin, Researcher, Reviewer, Compliance Monitor, QA, Submission Agent

## 🔗 Navigation Flow

```
Landing Page (/) 
    ↓ Click "Access Platform" or any feature
Login Page (/auth/login/) 
    ↓ Successful authentication
Dashboard (/dashboard/)
    ↓ Navigate to features
Feature Pages (/opportunities/, /documents/, /ai/, /compliance/)
```

## ✨ HTMX Features Implemented

1. **Interactive Landing Page**
   - Feature cards with hover effects
   - Smooth scrolling to sections
   - HTMX-powered navigation to protected routes

2. **Seamless Authentication**
   - HTMX form submissions
   - Automatic redirects with HX-Redirect headers
   - No page reloads during login flow

3. **Protected Route Handling**
   - Automatic login redirects for unauthenticated users
   - HTMX-aware authentication checks
   - Smooth transitions between authenticated and public areas

## 🎯 Key Features Showcase

- **Modern Design**: Professional gradient hero section with clear value proposition
- **Feature Highlights**: Interactive cards showcasing all 6 major capabilities
- **Stats Section**: Platform impact metrics with visual appeal
- **Workflow Steps**: Clear 4-step process visualization
- **Responsive Design**: Works on desktop and mobile devices
- **Professional UX**: Senior-level Django + HTMX implementation

## 🔐 User Roles & Permissions

When logged in as admin, you have access to all features:

- ✅ **Admin**: User management and system configuration
- ✅ **Researcher**: Opportunity discovery (Phase 2)
- ✅ **Reviewer**: Content review workflows (Phase 4) 
- ✅ **Compliance Monitor**: Regulatory oversight (Phase 3)
- ✅ **QA**: Quality assurance (Phase 3)
- ✅ **Submission Agent**: Proposal submission (Phase 4)

## 📱 Mobile-First Design

The landing page is fully responsive with:
- Adaptive grid layouts
- Mobile-optimized navigation
- Touch-friendly interactive elements
- Professional appearance on all devices

---

**Ready to experience BLACK CORAL?** Visit http://localhost:8000/ to see the modern landing page in action!