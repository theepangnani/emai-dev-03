# /ai-study - Generate AI Study Materials

Generate AI-powered study materials from any content.

## Usage

`/ai-study <type> [topic]`

Types:
- `guide` - Generate a study guide
- `quiz` - Generate a practice quiz
- `flashcards` - Generate flashcards

Example: `/ai-study quiz "World War 2"`

## API Endpoints

### Generate Study Guide
```bash
curl -X POST http://localhost:8000/api/study/generate \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Topic Name",
    "content": "Content to study..."
  }'
```

### Generate Quiz
```bash
curl -X POST http://localhost:8000/api/study/quiz/generate \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Topic Name",
    "content": "Content to base quiz on...",
    "num_questions": 5
  }'
```

### Generate Flashcards
```bash
curl -X POST http://localhost:8000/api/study/flashcards/generate \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Topic Name",
    "content": "Content to create flashcards from...",
    "num_cards": 10
  }'
```

### List Study Materials
```bash
curl http://localhost:8000/api/study/guides \
  -H "Authorization: Bearer <token>"
```

## Frontend Routes

- `/study/guide/:id` - View study guide
- `/study/quiz/:id` - Take quiz
- `/study/flashcards/:id` - Practice flashcards

## Implementation Files

### Backend
- `app/services/ai_service.py` - OpenAI integration
- `app/models/study_guide.py` - Database model
- `app/schemas/study.py` - Pydantic schemas
- `app/api/routes/study.py` - API endpoints

### Frontend
- `src/pages/StudyGuidePage.tsx` - Study guide viewer
- `src/pages/QuizPage.tsx` - Interactive quiz
- `src/pages/FlashcardsPage.tsx` - Flashcard practice
- `src/components/StudyToolsButton.tsx` - Generate from assignment

## Environment Variables

Required in `.env`:
```
OPENAI_API_KEY=sk-...
```

## Notes

- AI generation uses OpenAI GPT-4o-mini model
- Study guides are stored in the database with user association
- Quizzes support multiple choice (A-D) with explanations
- Flashcards use front/back format with flip interaction
