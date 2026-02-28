from pydantic import BaseModel
from datetime import datetime


class ConsentPreferences(BaseModel):
    """Cookie / data-processing consent preferences (#797)."""
    essential: bool = True  # Always on — cannot be disabled
    analytics: bool = False
    ai_processing: bool = False


class ConsentPreferencesResponse(BaseModel):
    essential: bool
    analytics: bool
    ai_processing: bool
    consent_given_at: datetime | None = None

    class Config:
        from_attributes = True


class ConsentStatusResponse(BaseModel):
    """Age-based consent status for a student (#783)."""
    student_id: int
    consent_status: str  # pending, parent_only, dual_required, given
    age: int | None = None
    requires_parent_consent: bool = False
    requires_student_consent: bool = False
    parent_consent_given: bool = False
    student_consent_given: bool = False
    parent_consent_given_at: datetime | None = None
    student_consent_given_at: datetime | None = None


class GiveConsentRequest(BaseModel):
    """Request body when a student gives their own consent."""
    accept: bool = True
