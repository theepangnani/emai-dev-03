import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import setup_logging, get_logger, RequestLogger
from app.db.database import Base, engine
from app.api.routes import auth, users, students, courses, assignments, google_classroom, study, logs

# Initialize logging first (auto-determines level based on environment)
setup_logging(
    app_name="emai",
    log_level=settings.log_level,  # Empty = auto (DEBUG in dev, WARNING in prod)
    environment=settings.environment,
    enable_console=True,
    enable_file=settings.log_to_file,
)

logger = get_logger(__name__)
request_logger = RequestLogger(get_logger("emai.requests"))

logger.info("Starting EMAI application...")

# Create database tables
from app.models import User, Student, Teacher, Course, Assignment, StudyGuide
Base.metadata.create_all(bind=engine)
logger.info("Database tables created/verified")

app = FastAPI(
    title=settings.app_name,
    description="AI-powered education management platform",
    version="0.1.0",
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with timing."""
    start_time = time.time()

    # Get client IP
    client_ip = request.client.host if request.client else "unknown"

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000

    # Get user ID from request state if available
    user_id = getattr(request.state, "user_id", None)

    # Log the request
    request_logger.log_request(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        client_ip=client_ip,
        user_id=user_id,
    )

    return response


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(students.router, prefix="/api")
app.include_router(courses.router, prefix="/api")
app.include_router(assignments.router, prefix="/api")
app.include_router(google_classroom.router, prefix="/api")
app.include_router(study.router, prefix="/api")
app.include_router(logs.router, prefix="/api")

logger.info("All routers registered")


def hello_world() -> str:
    return "Hello World"


@app.get("/")
def root():
    return {"message": hello_world(), "app": settings.app_name}


@app.get("/health")
def health_check():
    logger.debug("Health check requested")
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    logger.info("EMAI application started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("EMAI application shutting down")
