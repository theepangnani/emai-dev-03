# ClassBridge (EMAI) - AI-Powered Education Management Platform

An AI-powered education management platform connecting parents, students, teachers, and admins with Google Classroom integration, AI study tools, and comprehensive communication features.

## 🚀 Quick Start

### Backend (FastAPI)
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest
```

### Frontend (React)
```bash
cd frontend
npm install
npm run dev        # Development server on :5173
npm run build      # Production build
```

### Mobile Apps (React Native)
See **[📱 MOBILE_DEV_GUIDE.md](MOBILE_DEV_GUIDE.md)** for complete mobile development documentation.

Quick start:
```bash
npx react-native init ClassBridgeMobile --template react-native-template-typescript
cd ClassBridgeMobile
npm install
npm run ios        # iOS simulator
npm run android    # Android emulator
```

---

## 📚 Documentation

### Core Documentation
- **[REQUIREMENTS.md](REQUIREMENTS.md)** - Complete product requirements & roadmap
- **[CLAUDE.md](CLAUDE.md)** - Development guide for Claude Code
- **[MOBILE_STRATEGY.md](examples/mobile/MOBILE_STRATEGY.md)** - Mobile app strategy & architecture

### Mobile Development
- **[📱 MOBILE_DEV_GUIDE.md](MOBILE_DEV_GUIDE.md)** - **Complete mobile development guide**
  - Quick start & prerequisites
  - Project structure
  - API integration
  - Push notifications
  - Testing & deployment
  - Troubleshooting

- **[⚡ .mobile-dev-checklist.md](.mobile-dev-checklist.md)** - **Daily development quick reference**
  - Common commands
  - Feature development workflow
  - Pre-commit checklist
  - Code review checklist

### Design & Architecture
- **[design/](design/)** - Database schemas, architecture diagrams, wireframes

---

## 🏗️ Architecture

### Tech Stack

**Backend:**
- FastAPI (Python 3.13+)
- SQLAlchemy 2.0 ORM
- PostgreSQL (production) / SQLite (development)
- JWT authentication
- OpenAI API (gpt-4o-mini)
- Google Classroom & Gmail APIs
- SendGrid email
- APScheduler (background jobs)

**Frontend:**
- React 19 + TypeScript
- Vite build tool
- React Router 7
- TanStack React Query
- Axios

**Mobile:**
- React Native + TypeScript
- React Navigation
- Firebase Cloud Messaging
- AsyncStorage
- TanStack React Query (shared with web)

**Deployment:**
- Google Cloud Run
- Cloud SQL (PostgreSQL)
- GitHub Actions CI/CD
- URL: https://www.classbridge.ca

---

## 🎯 Key Features

### For Parents
- 👨‍👩‍👧 Multiple children management
- 📊 Unified dashboard across all children
- 🔔 Assignment reminders & notifications
- 💬 Direct messaging with teachers
- 📧 Teacher email monitoring

### For Students
- 📚 Google Classroom integration
- 🧠 AI study tools (guides, quizzes, flashcards)
- ✅ Task management with reminders
- 📅 Assignment calendar
- 🎯 Self-enrollment in courses

### For Teachers
- 📖 Course & assignment management
- 👥 Student monitoring
- 📧 Email & announcement tracking
- 💬 Parent communication
- 🤖 AI content generation

### For Admins
- 👤 User management (CRUD)
- 📊 System analytics
- 📢 Broadcast messaging
- 🔐 Role-based access control

---

## 🔐 Authentication & Authorization

### User Roles
- **Parent:** Manage children, view their data
- **Student:** Access courses, assignments, AI study tools
- **Teacher:** Manage courses, monitor students
- **Admin:** Full system access

### API Authentication
All API routes (except `/health`, `/docs`) require JWT Bearer token:
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=password"

# Response: {"access_token": "...", "refresh_token": "..."}

# Use in requests:
curl http://localhost:8000/api/courses \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

---

## 📱 API Endpoints

### Base URL
- **Development:** `http://localhost:8000/api`
- **Production:** `https://www.classbridge.ca/api`
- **API Docs:** `/docs` (Swagger UI) or `/redoc`

### API Versioning
Mobile and web apps currently share `/api` endpoints.
Dedicated `/api/v1` endpoints will be created as mobile-specific features are needed.

See [Issue #355](https://github.com/theepangnani/emai-dev-03/issues/355) for API versioning strategy.

### Key Endpoints
```
POST   /api/auth/login          # Login
POST   /api/auth/register       # Register
GET    /api/courses             # List courses
GET    /api/assignments         # List assignments
POST   /api/study/generate      # Generate AI study guide
GET    /api/parent/children     # Get parent's children
POST   /api/messages            # Send message
GET    /api/notifications       # Get notifications
```

---

## 🗄️ Database

### Development (SQLite)
```bash
# Database file: emai.db
# Auto-created on first run
python main.py
```

### Production (PostgreSQL)
```bash
# Set in .env:
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

### Migrations
Database tables auto-created via SQLAlchemy `Base.metadata.create_all()`.
Column additions handled via startup migrations in `main.py`.

---

## 🧪 Testing

### Backend Tests
```bash
pytest                    # Run all tests
pytest -v                # Verbose output
pytest --cov             # Coverage report
```

### Frontend Tests
```bash
cd frontend
npm test                 # Run tests
npm test -- --coverage  # Coverage report
```

### Mobile Tests
See [MOBILE_DEV_GUIDE.md](MOBILE_DEV_GUIDE.md#testing)

---

## 🚀 Deployment

### Automatic Deployment
- **Trigger:** Push to `master` branch
- **CI/CD:** GitHub Actions (`.github/workflows/deploy.yml`)
- **Target:** Google Cloud Run
- **URL:** https://www.classbridge.ca

### Manual Deployment
```bash
# Deploy to Cloud Run
gcloud run deploy classbridge \
  --source . \
  --project emai-dev-01 \
  --region us-central1

# View logs
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=classbridge" \
  --project=emai-dev-01 \
  --limit=50
```

### Mobile Deployment
See [MOBILE_DEV_GUIDE.md - Building for Production](MOBILE_DEV_GUIDE.md#building-for-production)

---

## 🔧 Configuration

### Environment Variables
Create `.env` file (see `.env.example`):
```bash
# Database
DATABASE_URL=sqlite:///./emai.db

# Auth
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Google APIs
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/google/callback

# OpenAI
OPENAI_API_KEY=your-openai-key

# SendGrid
SENDGRID_API_KEY=your-sendgrid-key
SENDGRID_FROM_EMAIL=noreply@classbridge.com
```

---

## 📊 Project Status

### Current Phase: Phase 1 (MVP) - In Progress

**Recent Completions:**
- ✅ Multi-role registration system (#257)
- ✅ Auto-create user profiles (#256)
- ✅ Course content management (#116)
- ✅ Task reminders (#112)
- ✅ Calendar actions (#126)
- ✅ Self-enrollment (#81)
- ✅ Test suite setup (#71)
- ✅ API versioning strategy (#311, #355)
- ✅ Mobile development guide (#356)

**In Progress:**
- 🔄 Mobile app development (#323-#340)
- 🔄 Backend mobile preparation (#312-#322)
- 🔄 Accessibility improvements (#247)
- 🔄 CI test fixes (#273)

**Next Up:**
- Production go-live checklist (#265)
- Batch student invites (#294)

See [REQUIREMENTS.md](REQUIREMENTS.md) for complete roadmap.

---

## 🤝 Contributing

### Development Workflow
1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes
3. Run tests: `pytest` (backend), `npm test` (frontend)
4. Commit: `git commit -m "Description"`
5. Push: `git push origin feature/your-feature`
6. Create Pull Request

### Code Standards
- **Backend:** PEP 8 (Python)
- **Frontend:** ESLint + Prettier (TypeScript/React)
- **Mobile:** ESLint + Prettier (TypeScript/React Native)
- **Git:** Conventional commits

---

## 📝 License

[License info to be added]

---

## 🆘 Support

### Getting Help
- **Documentation:** Start with [REQUIREMENTS.md](REQUIREMENTS.md)
- **Mobile Development:** See [MOBILE_DEV_GUIDE.md](MOBILE_DEV_GUIDE.md)
- **Issues:** [GitHub Issues](https://github.com/theepangnani/emai-dev-03/issues)
- **API Docs:** http://localhost:8000/docs (when server running)

### Troubleshooting
- **Backend issues:** Check logs in terminal
- **Frontend issues:** Check browser console
- **Mobile issues:** See [Troubleshooting section](MOBILE_DEV_GUIDE.md#troubleshooting)
- **Database issues:** Delete `emai.db` to reset (development only!)

---

## 🔗 Quick Links

- **Production App:** https://www.classbridge.ca
- **API Documentation:** https://www.classbridge.ca/docs
- **GitHub Repository:** https://github.com/theepangnani/emai-dev-03
- **Issues Tracker:** https://github.com/theepangnani/emai-dev-03/issues

---

**Built with ❤️ for education**

Last updated: 2026-02-14
