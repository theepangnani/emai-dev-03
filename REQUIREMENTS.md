# ClassBridge (EMAI) - Product Requirements

**Product Name:** ClassBridge
**Author:** Theepan Gnanasabapathy
**Version:** 1.0 (Based on PRD v4)
**Last Updated:** 2026-02-18

---

## Document Structure

This requirements document is split into multiple files for easier navigation and tool access. Each file is under 1000 lines.

| File | Sections | Description |
|------|----------|-------------|
| **REQUIREMENTS.md** (this file) | 1-5 | Overview, vision, problem, goals, roles |
| [requirements/features-part1.md](requirements/features-part1.md) | 6.1-6.14 | Core features: Integrations, AI Study Tools, Registration, Courses, Content, Analytics, Communication, Teachers, Tasks, Audit |
| [requirements/features-part2.md](requirements/features-part2.md) | 6.15-6.26 | UI & Auth features: Themes, Layout, Search, Mobile, UI Polish, Calendar, Parent UX, Security, Multi-Role, Materials Lifecycle, Password Reset |
| [requirements/features-part3.md](requirements/features-part3.md) | 6.27-6.50 | Extended features: Messaging, Teacher Linking, Roster, My Kids, Assignments, Enrollment, Invites, Security Phase 2, Reminders, Infrastructure, Admin, Onboarding, Verification, Course Planning, Emails |
| [requirements/dashboards.md](requirements/dashboards.md) | 7 | Role-Based Dashboards (Parent, Student, Teacher, Admin) |
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
