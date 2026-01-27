# ClassBridge (EMAI) - Product Requirements

**Product Name:** ClassBridge
**Author:** Theepan Gnanasabapathy
**Version:** 1.0 (Based on PRD v4)
**Last Updated:** 2026-01-25

---

## 1. Executive Summary

ClassBridge is a unified, AI-powered education platform that connects parents, students, teachers, administrators, and (in later phases) tutors in one role-based application. It integrates with school systems, provides AI-driven study tools, simplifies communication, and enables parents to actively support their children's education while ensuring access to affordable tutoring and intelligent assistance.

---

## 2. Vision & Mission

### Vision
To become the trusted digital bridge between families and schools, empowering every student to succeed with the right support at the right time.

### Mission
ClassBridge empowers parents to actively participate in their children's education by providing intelligent tools, clear insights, and affordable access to trusted educators - all in one connected platform.

---

## 3. Problem Statement

Education ecosystems are fragmented:
- Parents struggle to track academic progress across multiple systems (Google Classroom, TeachAssist, etc.)
- Students lack structured organization and effective study tools
- Teachers rely on disconnected communication channels
- Affordable tutoring is difficult to discover and manage

---

## 4. Goals & Objectives

### Product Goals
- Provide a single role-based application for parents, students, teachers, and administrators
- Enable parents to support learning at home
- Improve student academic outcomes through AI insights
- Simplify teacher-parent communication

### Business Goals
- Build a scalable SaaS platform
- Partner with school boards
- Establish recurring revenue through subscriptions and future marketplace services

---

## 5. User Roles & Personas

| Role | Description |
|------|-------------|
| **Parent** | Visibility into progress, tools to help children study, access to tutoring (Phase 4) |
| **Student** | Organization, personalized study support, motivation |
| **Teacher** | Simple communication, upload/share materials, optional tutor role (Phase 4) |
| **Tutor** | Register, manage availability, offer services (Phase 4) |
| **Administrator** | User management, analytics, compliance |

---

## 6. Core Features

### 6.1 Integrations
- **Google Classroom** (Phase 1) - IMPLEMENTED
- **TeachAssist** (Phase 2)

### 6.2 AI Study Assistant (Phase 1) - IMPLEMENTED
- Generate study guides from assignment content
- Generate practice quizzes
- Generate flashcards
- Summarize teacher handouts
- Identify strengths and weaknesses

### 6.3 Manual Course Content Upload (Phase 1)
- Upload or enter course content manually
- Supported inputs: PDF, Word, text notes, images (OCR)
- Tag content to specific class or subject
- AI generates study materials from user-provided content
- Content privacy controls
- Version history

### 6.4 Performance Analytics (Phase 2)
- Subject-level insights
- Trend analysis
- Weekly progress reports

### 6.5 Communication (Phase 1)
- Secure Parent <-> Teacher messaging
- Announcements
- Message history

### 6.6 Student Organization (Phase 2)
- Class schedules
- Assignments calendar
- Notes management
- Project tracking

### 6.7 Central Document Repository (Phase 1)
- Store course materials
- Teacher handouts
- Student notes
- Organized by course/subject

### 6.8 Tutor Marketplace (Phase 4)
- Tutor registration (teachers + private instructors)
- Tutor profiles (skills, availability, ratings)
- Parent/student tutor search
- AI-powered tutor recommendations
- Booking workflow

### 6.9 AI Email Communication Agent (Phase 5)
- Compose messages inside ClassBridge
- AI formats and sends email to teacher
- Monitor teacher email replies
- AI summarizes responses
- Searchable email archive

---

## 7. Role-Based Dashboards

Each user role has a customized dashboard:

| Dashboard | Key Features |
|-----------|--------------|
| **Parent Dashboard** | Child progress, assignments, study materials, tutor access |
| **Student Dashboard** | Courses, assignments, study tools, calendar |
| **Teacher Dashboard** | Classes, assignments, messaging, material sharing |
| **Tutor Dashboard** | Bookings, availability, student assignments (Phase 4) |
| **Admin Dashboard** | User management, analytics, compliance (Phase 3) |

---

## 8. Phased Roadmap

### Phase 1 (MVP) - CURRENT
- [x] Google Classroom integration
- [x] Parent & Student dashboards
- [x] AI study tools (guides, quizzes, flashcards)
- [ ] Secure messaging
- [ ] Central document repository
- [ ] Manual content upload with OCR

### Phase 2
- [ ] TeachAssist integration
- [ ] Performance analytics dashboard
- [ ] Advanced notifications
- [ ] Student organization tools

### Phase 3
- [ ] Mobile-first optimization
- [ ] Multi-language support
- [ ] Advanced AI personalization
- [ ] Admin analytics

### Phase 4 (Tutor Marketplace)
- [ ] Tutor registration
- [ ] AI tutor matching
- [ ] Booking workflow
- [ ] Ratings & profiles

### Phase 5 (AI Email Agent)
- [ ] AI email sending
- [ ] Reply ingestion
- [ ] AI summaries
- [ ] Searchable archive

---

## 9. Technical Architecture

### Stack
- **Frontend:** React + TypeScript + Vite
- **Backend:** Python (FastAPI)
- **AI Services:** OpenAI GPT-4o-mini / Vertex AI
- **Database:** PostgreSQL (production), SQLite (development)
- **Object Storage:** Google Cloud Storage
- **Authentication:** OAuth2 + RBAC

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register` | POST | User registration |
| `/api/auth/login` | POST | User login |
| `/api/google/connect` | GET | Initiate Google OAuth |
| `/api/google/callback` | GET | Handle OAuth callback |
| `/api/google/sync-courses` | POST | Sync Google Classroom courses |
| `/api/courses` | GET | List user's courses |
| `/api/assignments` | GET | List assignments |
| `/api/study/generate` | POST | Generate study guide |
| `/api/study/quiz/generate` | POST | Generate quiz |
| `/api/study/flashcards/generate` | POST | Generate flashcards |
| `/api/study/guides` | GET | List study materials |

---

## 10. Non-Functional Requirements

- **Availability:** 99.9% uptime
- **Performance:** <2s response time
- **Scalability:** 100k+ users
- **Security:** Encryption in transit and at rest
- **Compliance:** FERPA, MFIPPA, PIPEDA, GDPR (if applicable)

---

## 11. Success Metrics (KPIs)

- Parent engagement rate
- Student grade improvement
- Daily active users
- Retention rate
- Teacher adoption rate

---

## 12. GitHub Issues Tracking

Current feature issues are tracked in GitHub:

### Phase 1
- Issue #15: AI Study Tools Backend
- Issue #16: AI Study Guide Generation
- Issue #17: AI Quiz Generation
- Issue #18: AI Flashcard Generation
- Issue #19: AI Study Tools Frontend
- Issue #25: Manual Content Upload with OCR
- Issue #28: Central Document Repository
- Issue #32: Role-Based Dashboards

### Phase 2
- Issue #26: Performance Analytics Dashboard
- Issue #27: Student Organization Tools
- Issue #29: TeachAssist Integration

### Phase 3+
- Issue #30: Tutor Marketplace
- Issue #31: AI Email Communication Agent

---

## 13. Development Setup

See individual skill files for development commands:
- `/start` - Start development servers
- `/build` - Build for production
- `/test` - Run test suite
- `/status` - Check project status
- `/db-reset` - Reset development database
- `/feature` - Create feature branch
- `/new-endpoint` - Scaffold new API endpoint
