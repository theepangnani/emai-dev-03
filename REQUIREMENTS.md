# ClassBridge (EMAI) - Product Requirements

**Product Name:** ClassBridge
**Author:** Theepan Gnanasabapathy
**Version:** 1.1 (Based on PRD v4)
**Last Updated:** 2026-03-22

---

## Document Structure

This requirements document is split into multiple files for easier navigation and tool access. Each file is under 1000 lines.

| File | Sections | Description |
|------|----------|-------------|
| **REQUIREMENTS.md** (this file) | 1-5 | Overview, vision, problem, goals, roles |
| [requirements/features-part1.md](requirements/features-part1.md) | 6.1-6.14 | Core features: Integrations, AI Study Tools, Registration, Courses, Content, Analytics, Communication, Teachers, Tasks, Audit |
| [requirements/features-part2.md](requirements/features-part2.md) | 6.15-6.28 | UI & Auth features: Themes, Layout, Search, Mobile, UI Polish, Calendar, Parent UX, Security, Multi-Role, Materials Lifecycle, Password Reset, Design Consistency (6.27), **Upload Modal Redesign (6.28)** |
| [requirements/features-part3.md](requirements/features-part3.md) | 6.27-6.113 | Extended features: Messaging, Teacher Linking, Roster, My Kids, Assignments, Enrollment, Invites, Security Phase 2, Reminders, Infrastructure, Admin, Onboarding, Verification, Course Planning, Emails, **Waitlist System (6.53)**, **AI Usage Limits (6.54)**, **Contextual Notes System (6.55)**, **Teacher Resource Links (6.57)**, **Image Retention in Study Guides (6.58)**, **AI Help Chatbot (6.59)**, **Digital Wallet & Subscriptions (6.60) + Interac e-Transfer (6.60.8, #1851)**, **Smart Daily Briefing (6.61)**, **Help My Kid (6.62)**, **Weekly Progress Pulse (6.63)**, **Parent-Child Study Link (6.64)**, **Dashboard Redesign (6.65)**, **Responsible AI Parent Tools (6.66)**, **Smart Data Import (6.67)**, **Per-Category Notifications (6.70)**, **Premium Storage Limits (6.71)**, **Sidebar Always-Expanded (6.72)**, **Briefing to My Kids (6.73)**, **Mind Map Generation (6.74)**, **Notes Revision History (6.75)**, **Course Material Grouping (6.76)**, **Daily Morning Email Digest (6.77)**, **ICS Calendar Import (6.78)**, **Tutorial Completion Tracking (6.79)**, **Command Palette Search (6.80)**, **Recent Activity Panel (6.81)**, **LaTeX Math Rendering (6.82)**, **Help/FAQ for Responsible AI (6.83)**, **Chat FAB & Study Guide UI (6.84)**, **Upload Wizard Fix (6.85)**, **Collapsible Panels (6.86)**, **Activity Feed Filter (6.87)**, **Create Class Wizard Polish (6.88)**, **Quick Actions Reorg (6.89)**, **MyKidsPage Polish (6.90)**, **Source Files Quick Nav (6.91)**, **Activity History Page (6.92)**, **GCS File Storage Migration (6.93)**, **Scroll-to-Top Button (6.94)**, **User Cloud Storage Destination (6.95)**, **Cloud File Import (6.96)**, **Railway Deployment for clazzbridge.com (6.101)**, **Help KB Expansion & Chatbot Search Parity (6.103)**, **Performance Optimization (6.104)**, **Consolidated Study Material Navigation (6.105)**, **Study Guide Strategy Pattern (6.106)**, **Study Streak & XP Point System (6.107)**, **Assessment Countdown Widget (6.108)**, **Multilingual Parent Summaries (6.109)**, **Personal Study History Timeline (6.110)**, **End-of-Term Report Card (6.111)**, **Is My Child On Track Signal (6.112)**, **Study With Me Pomodoro (6.113)**, **Streaming Study Guide Generation (6.115)**, **Document Privacy & IP Protection (6.119)**, **School Board Announcements (6.120)** |
| [requirements/dashboards.md](requirements/dashboards.md) | 7 | Role-Based Dashboards (Parent, Student, Teacher, Admin) |
| [design/UI_AUDIT_REPORT.md](design/UI_AUDIT_REPORT.md) | — | UI/UX Audit Report: User journeys, friction points, Phase 1 improvements, Phase 2 features (#668) |
| [docs/ClassBridge_UI_UX_Assessment_Report.docx](docs/ClassBridge_UI_UX_Assessment_Report.docx) | — | Comprehensive HCD Assessment Report: Design system audit, role-specific evaluation, accessibility, responsive, user journeys, risk register (#827) |
| [requirements/roadmap.md](requirements/roadmap.md) | 8 | Phased Roadmap (Phase 1-5) with progress checklists |
| [requirements/mobile.md](requirements/mobile.md) | 9 | Mobile App Development (Expo SDK 54, React Native) |
| [requirements/technical.md](requirements/technical.md) | 10-11 | Technical Architecture, API Endpoints, NFRs, KPIs |
| [requirements/tracking.md](requirements/tracking.md) | 12-13 | GitHub Issues Tracking, Development Setup |

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
| **Teacher (School)** | School teacher — may be on EMAI (platform teacher) or only referenced via Google Classroom sync (shadow record) |
| **Teacher (Private Tutor)** | Independent educator on EMAI — creates own courses, connects own Google Classroom, manages students directly. Phase 4 adds marketplace features (availability, profiles, booking) for teachers with `teacher_type=private_tutor` |
| **Administrator** | User management, analytics, compliance |

---

*For detailed feature specifications, dashboards, roadmap, and technical architecture, see the linked files in the Document Structure table above.*
