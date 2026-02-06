"""
AI Service for generating educational content using Anthropic Claude.
"""
import time
import anthropic
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def get_anthropic_client() -> anthropic.Anthropic:
    """Get configured Anthropic client."""
    if not settings.anthropic_api_key:
        logger.error("Anthropic API key not configured")
        raise ValueError("ANTHROPIC_API_KEY not configured")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


async def generate_content(
    prompt: str,
    system_prompt: str = "You are an educational assistant helping students learn effectively.",
    max_tokens: int = 2000,
    temperature: float = 0.7,
) -> str:
    """
    Generate content using Anthropic Claude API.

    Args:
        prompt: The user prompt/question
        system_prompt: The system context for the AI
        max_tokens: Maximum tokens in response
        temperature: Creativity level (0-1)

    Returns:
        Generated text content
    """
    start_time = time.time()
    logger.info(f"Starting AI content generation | model={settings.claude_model} | max_tokens={max_tokens}")
    logger.debug(f"Prompt length: {len(prompt)} chars")

    try:
        client = get_anthropic_client()

        message = client.messages.create(
            model=settings.claude_model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
        )

        duration_ms = (time.time() - start_time) * 1000
        content = message.content[0].text

        # Log usage stats
        logger.info(
            f"AI generation completed | duration={duration_ms:.2f}ms | "
            f"input_tokens={message.usage.input_tokens} | output_tokens={message.usage.output_tokens}"
        )

        return content

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"AI generation failed | duration={duration_ms:.2f}ms | error={str(e)}")
        raise


async def summarize_teacher_communication(
    subject: str,
    body: str,
    sender_name: str,
    comm_type: str = "email",
) -> str:
    """
    Generate a concise AI summary of a teacher communication.

    Returns a 1-3 sentence summary highlighting action items, deadlines, and key info.
    """
    logger.info(f"Summarizing teacher communication | type={comm_type} | subject={subject}")

    prompt = f"""Summarize the following {comm_type} from a teacher for a student/parent.
Focus on: action items, deadlines, key information.
Keep the summary to 1-3 sentences.

**From:** {sender_name}
**Subject:** {subject}

**Content:**
{body[:3000]}"""

    system_prompt = (
        "You are an educational assistant that summarizes teacher communications "
        "for students and parents. Be concise, highlight deadlines and action items. "
        "Use simple, clear language. Do not add information not in the original message."
    )

    return await generate_content(prompt, system_prompt, max_tokens=200, temperature=0.3)


async def generate_study_guide(
    assignment_title: str,
    assignment_description: str,
    course_name: str,
    due_date: str | None = None,
) -> str:
    """
    Generate a study guide for an assignment.

    Args:
        assignment_title: Title of the assignment
        assignment_description: Description/instructions
        course_name: Name of the course
        due_date: Optional due date string

    Returns:
        Markdown-formatted study guide
    """
    logger.info(f"Generating study guide | title={assignment_title} | course={course_name}")
    due_info = f"\nDue Date: {due_date}" if due_date else ""

    prompt = f"""Create a comprehensive study guide for the following assignment:

**Assignment:** {assignment_title}
**Course:** {course_name}{due_info}

**Description:**
{assignment_description}

Please include:
1. **Key Concepts** - Main topics and ideas to understand
2. **Important Terms** - Vocabulary with definitions
3. **Study Tips** - Strategies for mastering this material
4. **Practice Questions** - 3-5 questions to test understanding
5. **Resources** - Suggested areas to review

Format the response in Markdown for easy reading."""

    system_prompt = """You are an expert educational tutor. Create clear, well-organized study guides
that help students understand concepts deeply. Use simple language and provide practical examples.
Format responses in clean Markdown with proper headers and bullet points."""

    return await generate_content(prompt, system_prompt, max_tokens=2000)


async def generate_quiz(
    topic: str,
    content: str,
    num_questions: int = 5,
) -> str:
    """
    Generate a practice quiz from content.

    Args:
        topic: The topic/title for the quiz
        content: Content to base questions on
        num_questions: Number of questions to generate

    Returns:
        JSON string with quiz questions
    """
    logger.info(f"Generating quiz | topic={topic} | num_questions={num_questions}")
    prompt = f"""Create a {num_questions}-question multiple choice quiz about:

**Topic:** {topic}

**Content:**
{content}

For each question, provide:
1. The question text
2. Four options labeled A, B, C, D
3. The correct answer letter
4. A brief explanation of why it's correct

Format your response as a JSON array with this structure:
```json
[
  {{
    "question": "Question text here?",
    "options": {{
      "A": "First option",
      "B": "Second option",
      "C": "Third option",
      "D": "Fourth option"
    }},
    "correct_answer": "A",
    "explanation": "Explanation of why A is correct"
  }}
]
```

Return ONLY the JSON array, no other text."""

    system_prompt = """You are an expert quiz creator. Create clear, educational questions that test
understanding, not just memorization. Make wrong answers plausible but clearly incorrect.
Always return valid JSON."""

    return await generate_content(prompt, system_prompt, max_tokens=2000, temperature=0.5)


async def generate_flashcards(
    topic: str,
    content: str,
    num_cards: int = 10,
) -> str:
    """
    Generate flashcards from content.

    Args:
        topic: The topic for flashcards
        content: Content to create cards from
        num_cards: Number of flashcards to generate

    Returns:
        JSON string with flashcards
    """
    logger.info(f"Generating flashcards | topic={topic} | num_cards={num_cards}")
    prompt = f"""Create {num_cards} flashcards for studying:

**Topic:** {topic}

**Content:**
{content}

Create flashcards that cover the most important concepts, terms, and ideas.
Each flashcard should have:
- Front: A term, concept, or question
- Back: The definition, explanation, or answer

Format your response as a JSON array:
```json
[
  {{
    "front": "Term or question",
    "back": "Definition or answer"
  }}
]
```

Return ONLY the JSON array, no other text."""

    system_prompt = """You are an expert at creating effective study flashcards.
Focus on key concepts and important details. Make cards concise but informative.
Always return valid JSON."""

    return await generate_content(prompt, system_prompt, max_tokens=1500, temperature=0.5)
