import csv
import io
import logging
from collections import Counter, defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.survey import SurveyResponse, SurveyAnswer
from app.api.deps import require_role
from app.schemas.survey import (
    SurveyAnalyticsResponse, SurveyQuestionAnalytics, SurveyStatsResponse,
    SurveyResponseDetailOut, SurveyResponseListResponse, SurveyAnswerOut,
)
from app.services.survey_questions import get_questions_for_role, VALID_SURVEY_ROLES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/survey", tags=["Admin Survey"])


def _parse_date(date_str: str | None) -> datetime | None:
    """Parse a YYYY-MM-DD date string, or return None."""
    if not date_str:
        return None
    return datetime.strptime(date_str, "%Y-%m-%d")


def _apply_filters(query, role: str | None, date_from: str | None, date_to: str | None):
    """Apply role and date filters to a SurveyResponse query."""
    if role:
        query = query.filter(SurveyResponse.role == role)
    parsed_from = _parse_date(date_from)
    if parsed_from:
        query = query.filter(SurveyResponse.created_at >= parsed_from)
    parsed_to = _parse_date(date_to)
    if parsed_to:
        query = query.filter(SurveyResponse.created_at <= parsed_to)
    return query


def _get_all_question_map() -> dict[str, dict]:
    """Build a map of question_key -> question definition across all roles."""
    result: dict[str, dict] = {}
    for r in VALID_SURVEY_ROLES:
        questions = get_questions_for_role(r)
        if questions:
            for q in questions:
                result[q["key"]] = q
    return result


# ── GET /api/admin/survey/analytics ────────────────────────────────


@router.get("/analytics", response_model=SurveyAnalyticsResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def survey_analytics(
    request: Request,
    role: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Aggregated survey stats and per-question breakdowns."""
    # ── Stats ──
    base = db.query(SurveyResponse)
    base = _apply_filters(base, role, date_from, date_to)

    total_responses = base.count()
    completed_count = base.filter(SurveyResponse.completed.is_(True)).count()
    completion_rate = (completed_count / total_responses * 100) if total_responses else 0.0

    by_role: dict[str, int] = {}
    role_rows = (
        _apply_filters(db.query(SurveyResponse.role, sa_func.count()), role, date_from, date_to)
        .group_by(SurveyResponse.role)
        .all()
    )
    for r_name, cnt in role_rows:
        by_role[r_name] = cnt

    stats = SurveyStatsResponse(
        total_responses=total_responses,
        by_role=by_role,
        completion_rate=round(completion_rate, 1),
    )

    # ── Per-question analytics ──
    # Determine which questions to analyse
    if role:
        questions_list = get_questions_for_role(role) or []
    else:
        questions_list = []
        for r in sorted(VALID_SURVEY_ROLES):
            questions_list.extend(get_questions_for_role(r) or [])

    question_map = {q["key"]: q for q in questions_list}

    # Fetch all answers joined with responses (filtered)
    answer_query = (
        db.query(SurveyAnswer)
        .join(SurveyResponse, SurveyAnswer.response_id == SurveyResponse.id)
    )
    answer_query = _apply_filters(answer_query, role, date_from, date_to)
    all_answers = answer_query.all()

    # Group answers by question_key
    grouped: dict[str, list] = defaultdict(list)
    for ans in all_answers:
        grouped[ans.question_key].append(ans)

    question_analytics: list[SurveyQuestionAnalytics] = []
    for q in questions_list:
        key = q["key"]
        q_type = q["type"]
        answers = grouped.get(key, [])
        total_answers = len(answers)

        distribution: dict[str, int] | None = None
        average: float | None = None
        sub_item_averages: dict[str, float] | None = None
        free_text_responses: list[str] | None = None

        if q_type == "single_select":
            counter: Counter = Counter()
            for ans in answers:
                if isinstance(ans.answer_value, str):
                    counter[ans.answer_value] += 1
            distribution = dict(counter)

        elif q_type == "multi_select":
            counter = Counter()
            for ans in answers:
                if isinstance(ans.answer_value, list):
                    for item in ans.answer_value:
                        counter[item] += 1
            distribution = dict(counter)

        elif q_type == "likert":
            counter = Counter()
            values: list[int] = []
            for ans in answers:
                if isinstance(ans.answer_value, int):
                    counter[str(ans.answer_value)] += 1
                    values.append(ans.answer_value)
            distribution = dict(counter)
            average = round(sum(values) / len(values), 2) if values else None

        elif q_type == "likert_matrix":
            sub_totals: dict[str, list[int]] = defaultdict(list)
            for ans in answers:
                if isinstance(ans.answer_value, dict):
                    for sub_key, val in ans.answer_value.items():
                        if isinstance(val, int):
                            sub_totals[sub_key].append(val)
            sub_item_averages = {
                k: round(sum(v) / len(v), 2) for k, v in sub_totals.items() if v
            }

        elif q_type == "free_text":
            texts: list[str] = []
            for ans in answers:
                if isinstance(ans.answer_value, str) and ans.answer_value.strip():
                    texts.append(ans.answer_value)
                    if len(texts) >= 20:
                        break
            free_text_responses = texts

        question_analytics.append(SurveyQuestionAnalytics(
            question_key=key,
            question_text=q["text"],
            question_type=q_type,
            total_answers=total_answers,
            distribution=distribution,
            average=average,
            sub_item_averages=sub_item_averages,
            free_text_responses=free_text_responses,
        ))

    # ── Daily submissions ──
    daily_query = (
        _apply_filters(
            db.query(
                sa_func.date(SurveyResponse.created_at).label("day"),
                sa_func.count().label("count"),
            ),
            role, date_from, date_to,
        )
        .group_by(sa_func.date(SurveyResponse.created_at))
        .order_by(sa_func.date(SurveyResponse.created_at))
        .all()
    )
    daily_submissions = [{"date": str(row.day), "count": row.count} for row in daily_query]

    return SurveyAnalyticsResponse(
        stats=stats,
        questions=question_analytics,
        daily_submissions=daily_submissions,
    )


# ── GET /api/admin/survey/responses ────────────────────────────────


@router.get("/responses", response_model=SurveyResponseListResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_responses(
    request: Request,
    role: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Paginated list of survey responses."""
    query = db.query(SurveyResponse)
    query = _apply_filters(query, role, date_from, date_to)

    total = query.count()
    items = (
        query.order_by(SurveyResponse.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return SurveyResponseListResponse(items=items, total=total)


# ── GET /api/admin/survey/responses/{response_id} ──────────────────


@router.get("/responses/{response_id}", response_model=SurveyResponseDetailOut)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_response(
    response_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Get a single survey response with all answers."""
    resp = db.query(SurveyResponse).filter(SurveyResponse.id == response_id).first()
    if not resp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Survey response not found",
        )
    return resp


# ── GET /api/admin/survey/export/csv ───────────────────────────────


@router.get("/export/csv")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def export_csv(
    request: Request,
    role: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Export survey responses as CSV download."""
    question_map = _get_all_question_map()

    query = (
        db.query(SurveyAnswer, SurveyResponse)
        .join(SurveyResponse, SurveyAnswer.response_id == SurveyResponse.id)
    )
    query = _apply_filters(query, role, date_from, date_to)
    query = query.order_by(SurveyResponse.created_at.desc(), SurveyAnswer.id)

    rows = query.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "response_id", "session_id", "role", "completed_at",
        "question_key", "question_text", "answer_value",
    ])

    for answer, response in rows:
        q_def = question_map.get(answer.question_key, {})
        question_text = q_def.get("text", "")

        # Serialize answer_value to string
        val = answer.answer_value
        if isinstance(val, list):
            answer_str = "; ".join(str(v) for v in val)
        elif isinstance(val, dict):
            answer_str = "; ".join(f"{k}: {v}" for k, v in val.items())
        else:
            answer_str = str(val) if val is not None else ""

        writer.writerow([
            response.id,
            response.session_id,
            response.role,
            response.completed_at.isoformat() if response.completed_at else "",
            answer.question_key,
            question_text,
            answer_str,
        ])

    output.seek(0)
    filename = f"survey-export-{datetime.now().strftime('%Y-%m-%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
