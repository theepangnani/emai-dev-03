from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import insert

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.teacher import Teacher, TeacherType
from app.models.student import Student, parent_students, RelationshipType
from app.models.invite import Invite, InviteType
from app.schemas.user import UserCreate, UserResponse, Token
from app.schemas.invite import AcceptInviteRequest
from app.core.security import verify_password, get_password_hash, create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
        google_id=user_data.google_id,
        google_access_token=user_data.google_access_token,
        google_refresh_token=user_data.google_refresh_token,
    )
    db.add(user)
    db.flush()

    # Auto-create Teacher or Student record
    if user.role == UserRole.TEACHER:
        teacher_type_value = None
        if user_data.teacher_type:
            teacher_type_value = TeacherType(user_data.teacher_type)
        teacher = Teacher(user_id=user.id, teacher_type=teacher_type_value)
        db.add(teacher)
    elif user.role == UserRole.STUDENT:
        student = Student(user_id=user.id)
        db.add(student)

    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=access_token)


@router.post("/accept-invite", response_model=Token)
def accept_invite(data: AcceptInviteRequest, db: Session = Depends(get_db)):
    """Accept an invite and create a new user account."""
    # Validate token
    invite = db.query(Invite).filter(Invite.token == data.token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite token")

    if invite.accepted_at is not None:
        raise HTTPException(status_code=400, detail="This invite has already been accepted")

    if invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This invite has expired")

    # Check if email already registered
    existing_user = db.query(User).filter(User.email == invite.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    # Determine role from invite type
    if invite.invite_type == InviteType.STUDENT:
        role = UserRole.STUDENT
    else:
        role = UserRole.TEACHER

    # Create user
    user = User(
        email=invite.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        role=role,
    )
    db.add(user)
    db.flush()

    # Create Teacher or Student record
    if role == UserRole.TEACHER:
        teacher_type_value = None
        metadata = invite.metadata_json or {}
        if metadata.get("teacher_type"):
            teacher_type_value = TeacherType(metadata["teacher_type"])

        # Check if a shadow teacher exists with this email — claim it
        shadow = db.query(Teacher).filter(
            Teacher.google_email == invite.email,
            Teacher.is_shadow == True,
        ).first()
        if shadow:
            shadow.user_id = user.id
            shadow.is_shadow = False
            if teacher_type_value:
                shadow.teacher_type = teacher_type_value
            teacher = shadow
        else:
            teacher = Teacher(user_id=user.id, teacher_type=teacher_type_value)
            db.add(teacher)
    elif role == UserRole.STUDENT:
        student = Student(user_id=user.id)
        db.add(student)
        db.flush()

        # If invited by a parent, auto-link via parent_students
        inviter = db.query(User).filter(User.id == invite.invited_by_user_id).first()
        if inviter and inviter.role == UserRole.PARENT:
            metadata = invite.metadata_json or {}
            rel_type_str = metadata.get("relationship_type", "guardian")
            rel_type = RelationshipType(rel_type_str)
            db.execute(
                insert(parent_students).values(
                    parent_id=inviter.id,
                    student_id=student.id,
                    relationship_type=rel_type,
                )
            )

    # Mark invite as accepted
    invite.accepted_at = datetime.utcnow()
    db.commit()

    # Return JWT so the user is logged in immediately
    access_token = create_access_token(data={"sub": str(user.id)})
    return Token(access_token=access_token)
