# /logging - Application Logging Framework

Comprehensive logging for both backend and frontend with rolling log files.

## Features

- **Rolling log files**: 10 MB max size, 5 backups retained
- **Environment-aware**: DEBUG in development, WARNING in production
- **Frontend logging**: Console + backend forwarding
- **HTTP request logging**: All requests with timing and status

## Configuration

### Environment Variables

In `.env`:
```
ENVIRONMENT=development   # or "production"
LOG_LEVEL=               # Empty = auto (DEBUG for dev, WARNING for prod)
LOG_TO_FILE=true         # Set to false to disable file logging
```

### Log Levels

| Environment | Default Level | Console | File |
|-------------|--------------|---------|------|
| development | DEBUG | All levels | All levels |
| production | WARNING | WARNING+ | WARNING+ |

## Log File Location

```
logs/emai.log           # Current log
logs/emai.log.1         # Rotated backup 1
logs/emai.log.2         # Rotated backup 2
...
```

## API Endpoints

### Send Single Log (Frontend)
```bash
curl -X POST http://localhost:8000/api/logs \
  -H "Content-Type: application/json" \
  -d '{
    "level": "info",
    "message": "User clicked button",
    "context": {"page": "dashboard", "action": "click"}
  }'
```

### Send Batch Logs (Frontend)
```bash
curl -X POST http://localhost:8000/api/logs/batch \
  -H "Content-Type: application/json" \
  -d '{
    "logs": [
      {"level": "info", "message": "Action 1"},
      {"level": "warn", "message": "Warning 1"}
    ]
  }'
```

## Usage

### Backend (Python)

```python
import logging

logger = logging.getLogger(__name__)

# Log at different levels
logger.debug("Detailed debug info")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred", exc_info=True)
```

### Frontend (TypeScript)

```typescript
import { logger } from '../utils/logger';

// Log at different levels
logger.debug('Debug message', { extra: 'context' });
logger.info('Info message');
logger.warn('Warning message');
logger.error('Error message', { error: err.message });
```

## Log Format

```
2026-01-26 10:30:45,123 | INFO     | app.api.routes.study | study.py:45 | Processing request
```

Format: `timestamp | level | logger_name | file:line | message`

## Implementation Files

### Backend
- `app/core/logging_config.py` - Core logging setup with RotatingFileHandler
- `app/core/config.py` - Environment and log settings
- `app/api/routes/logs.py` - Frontend log receiving endpoints
- `main.py` - Logging initialization and HTTP middleware

### Frontend
- `frontend/src/utils/logger.ts` - Logger utility class

## HTTP Request Logging

All HTTP requests are automatically logged:
```
GET /api/users/me -> 200 (47.47ms) [client: 127.0.0.1]
POST /api/study/generate -> 201 (2341.23ms) [client: 127.0.0.1]
```

## Frontend Behavior

| Environment | Console Output | Backend Forwarding |
|-------------|---------------|-------------------|
| development | All levels | Immediate (each log) |
| production | Errors only | Batched (errors/warnings) |

## Notes

- Log files are created in the `logs/` directory (auto-created if missing)
- Rotation happens automatically when file exceeds 10 MB
- Frontend logs are prefixed with `[FRONTEND]` in backend logs
- Structured context is JSON-formatted in log messages
- HTTP middleware excludes `/api/logs` to prevent recursive logging
