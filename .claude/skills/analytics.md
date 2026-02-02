# /analytics - Scaffold Performance Analytics

Create the performance analytics dashboard feature.

## Feature Overview

Performance analytics provides:
- Subject-level insights
- Grade trend analysis
- Weekly progress reports
- Strengths and weaknesses identification

## Instructions

When implementing this feature, create the following:

### 1. Backend Model (app/models/analytics.py)

```python
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.database import Base


class GradeRecord(Base):
    __tablename__ = "grade_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=True)
    grade = Column(Float)
    max_grade = Column(Float)
    percentage = Column(Float)
    recorded_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    course = relationship("Course")
    assignment = relationship("Assignment")


class ProgressReport(Base):
    __tablename__ = "progress_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    report_type = Column(String(50))  # weekly, monthly, course
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    data = Column(JSON)  # Flexible JSON for report data
    generated_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
```

### 2. Backend Schema (app/schemas/analytics.py)

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class SubjectInsight(BaseModel):
    course_id: int
    course_name: str
    average_grade: float
    trend: str  # "improving", "declining", "stable"
    assignment_count: int
    last_grade: Optional[float]


class StrengthWeakness(BaseModel):
    category: str
    type: str  # "strength" or "weakness"
    description: str
    recommendations: List[str]


class WeeklyReport(BaseModel):
    week_start: datetime
    week_end: datetime
    courses_summary: List[SubjectInsight]
    assignments_completed: int
    average_performance: float
    ai_recommendations: List[str]


class AnalyticsDashboard(BaseModel):
    overall_average: float
    courses: List[SubjectInsight]
    strengths: List[StrengthWeakness]
    weaknesses: List[StrengthWeakness]
    recent_trend: str
```

### 3. Backend Routes (app/api/routes/analytics.py)

Key endpoints to implement:
- `GET /api/analytics/dashboard` - Main analytics dashboard data
- `GET /api/analytics/course/{id}` - Course-specific analytics
- `GET /api/analytics/trends` - Grade trends over time
- `GET /api/analytics/reports/weekly` - Weekly progress report
- `POST /api/analytics/ai-insights` - AI-generated insights

### 4. Analytics Service (app/services/analytics_service.py)

```python
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

async def calculate_course_average(db: Session, user_id: int, course_id: int) -> float:
    """Calculate average grade for a course."""
    pass

async def analyze_trend(grades: list[float]) -> str:
    """Determine if grades are improving, declining, or stable."""
    pass

async def generate_weekly_report(db: Session, user_id: int) -> dict:
    """Generate weekly progress report."""
    pass

async def identify_strengths_weaknesses(db: Session, user_id: int) -> dict:
    """Use AI to identify strengths and areas for improvement."""
    pass
```

### 5. Frontend Components

- `AnalyticsDashboard.tsx` - Main analytics page
- `GradeChart.tsx` - Grade trend visualization
- `SubjectCard.tsx` - Per-subject performance card
- `WeeklyReportCard.tsx` - Weekly summary

## Chart Libraries

Recommended for frontend:
- `recharts` - React charting library
- `chart.js` with `react-chartjs-2`

Install:
```bash
cd frontend
npm install recharts
# or
npm install chart.js react-chartjs-2
```

## API Usage Example

```bash
# Get dashboard data
curl http://localhost:8000/api/analytics/dashboard \
  -H "Authorization: Bearer <token>"

# Get weekly report
curl http://localhost:8000/api/analytics/reports/weekly \
  -H "Authorization: Bearer <token>"

# Get course trends
curl "http://localhost:8000/api/analytics/trends?course_id=1&days=30" \
  -H "Authorization: Bearer <token>"
```

## AI Insights Integration

The analytics feature integrates with OpenAI to provide:
- Personalized study recommendations
- Performance pattern analysis
- Predictive grade insights

## Related Issues

- GitHub Issue #26: Performance Analytics Dashboard
- GitHub Issue #27: Student Organization Tools
