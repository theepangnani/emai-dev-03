# /messaging - Scaffold Secure Messaging Feature

Create the secure messaging system for parent-teacher communication.

## Feature Overview

Secure messaging provides:
- Direct parent <-> teacher communication
- School announcements
- Message threading
- Read receipts
- Message history and search

## Instructions

When implementing this feature, create the following:

### 1. Backend Models (app/models/message.py)

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    participant_1_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    participant_2_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Related student
    subject = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    participant_1 = relationship("User", foreign_keys=[participant_1_id])
    participant_2 = relationship("User", foreign_keys=[participant_2_id])
    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
    sender = relationship("User")


class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    is_pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    author = relationship("User")
    course = relationship("Course")
```

### 2. Backend Schema (app/schemas/message.py)

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: int
    sender_id: int
    sender_name: str
    content: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationCreate(BaseModel):
    participant_id: int
    student_id: Optional[int] = None
    subject: Optional[str] = None
    initial_message: str


class ConversationResponse(BaseModel):
    id: int
    participant_1_id: int
    participant_2_id: int
    subject: Optional[str]
    last_message: Optional[MessageResponse]
    unread_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class AnnouncementCreate(BaseModel):
    course_id: Optional[int] = None
    title: str
    content: str
    is_pinned: bool = False


class AnnouncementResponse(BaseModel):
    id: int
    author_id: int
    author_name: str
    course_id: Optional[int]
    title: str
    content: str
    is_pinned: bool
    created_at: datetime

    class Config:
        from_attributes = True
```

### 3. Backend Routes (app/api/routes/messages.py)

Key endpoints to implement:

```python
# Conversations
POST   /api/messages/conversations         # Start new conversation
GET    /api/messages/conversations         # List user's conversations
GET    /api/messages/conversations/{id}    # Get conversation with messages
DELETE /api/messages/conversations/{id}    # Delete conversation

# Messages
POST   /api/messages/conversations/{id}/messages  # Send message
PATCH  /api/messages/messages/{id}/read           # Mark as read
DELETE /api/messages/messages/{id}                # Delete message

# Announcements
POST   /api/messages/announcements         # Create announcement (teachers/admins)
GET    /api/messages/announcements         # List announcements
GET    /api/messages/announcements/{id}    # Get announcement
DELETE /api/messages/announcements/{id}    # Delete announcement
```

### 4. Frontend Components

- `MessagesPage.tsx` - Main messaging interface
- `ConversationList.tsx` - List of conversations
- `ConversationThread.tsx` - Message thread view
- `NewMessageModal.tsx` - Start new conversation
- `AnnouncementsBanner.tsx` - Display announcements

### 5. Real-time Updates (Optional Enhancement)

For real-time messaging, consider:
- WebSocket with FastAPI
- Server-Sent Events (SSE)
- Polling as fallback

## API Usage Examples

```bash
# Start a conversation
curl -X POST http://localhost:8000/api/messages/conversations \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "participant_id": 5,
    "student_id": 3,
    "subject": "Math homework question",
    "initial_message": "Hi, I have a question about the algebra assignment..."
  }'

# List conversations
curl http://localhost:8000/api/messages/conversations \
  -H "Authorization: Bearer <token>"

# Send a message
curl -X POST http://localhost:8000/api/messages/conversations/1/messages \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"content": "Thank you for clarifying!"}'

# Mark as read
curl -X PATCH http://localhost:8000/api/messages/messages/5/read \
  -H "Authorization: Bearer <token>"

# Create announcement (teacher)
curl -X POST http://localhost:8000/api/messages/announcements \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "course_id": 1,
    "title": "Test on Friday",
    "content": "Reminder: Chapter 5 test this Friday",
    "is_pinned": true
  }'
```

## Role-Based Access

| Action | Parent | Student | Teacher | Admin |
|--------|--------|---------|---------|-------|
| Send message | To child's teachers | To own teachers | To all | To all |
| Create announcement | No | No | Own classes | All |
| View announcements | Child's classes | Own classes | All | All |

## Security Considerations

- Validate participant relationships (parent must be linked to student)
- Sanitize message content (XSS prevention)
- Rate limiting on message sending
- Audit logging for compliance

## Related Issues

- GitHub Issue #20-23: Notifications (related feature)
