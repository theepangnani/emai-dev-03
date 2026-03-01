"""AI-powered task extraction from uploaded documents.

Uses Anthropic Claude to analyze document text and extract actionable tasks,
assignments, and deadlines.
"""
import json
import time
from datetime import datetime

from app.core.logging_config import get_logger
from app.services.ai_service import get_anthropic_client
from app.core.config import settings

logger = get_logger(__name__)


async def extract_tasks_from_document(
    content: str,
    filename: str,
) -> list[dict]:
    """Use AI to extract actionable tasks with due dates from document text.

    Args:
        content: The extracted text content of the document.
        filename: Original filename for context.

    Returns:
        List of task dicts with keys: title, description, due_date, priority.
    """
    if not content or not content.strip():
        logger.info("Empty document content, returning no tasks")
        return []

    # Truncate very long documents to stay within token limits
    max_chars = 12000
    truncated = content[:max_chars]
    if len(content) > max_chars:
        truncated += "\n\n[Document truncated for analysis]"

    today = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""Analyze this document and extract all actionable tasks, assignments,
or deadlines that a student would need to act on. For each, return:
- title: short task title (max 100 chars)
- description: brief description of what needs to be done (max 300 chars)
- due_date: ISO date (YYYY-MM-DD) if a specific date is found, null if not
- priority: "high" for exams/tests/major projects, "medium" for homework/assignments, "low" for optional/review items

IMPORTANT RULES:
- Today's date is {today}. If a date does not include a year (e.g., "Due Mar 3"), assume the nearest future occurrence from today.
- Only extract ACTUAL student deadlines and action items. Do NOT extract historical dates, reference dates, or dates that are part of the subject matter.
- If no actionable tasks are found, return an empty JSON array [].
- Return ONLY a valid JSON array, no other text.

Document filename: {filename}

Document content:
{truncated}"""

    system_prompt = (
        "You are an educational assistant that analyzes course documents to find "
        "student tasks, assignments, and deadlines. Return ONLY a valid JSON array. "
        "Be precise about dates and conservative about what constitutes an actionable task."
    )

    start_time = time.time()
    logger.info(
        f"Extracting tasks from document | filename={filename} | "
        f"content_length={len(content)} | model={settings.claude_model}"
    )

    try:
        client = get_anthropic_client()

        message = client.messages.create(
            model=settings.claude_model,
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        duration_ms = (time.time() - start_time) * 1000
        raw_response = message.content[0].text

        logger.info(
            f"Task extraction completed | duration={duration_ms:.2f}ms | "
            f"input_tokens={message.usage.input_tokens} | "
            f"output_tokens={message.usage.output_tokens}"
        )

        # Parse JSON response — handle markdown code blocks
        text = raw_response.strip()
        if text.startswith("```"):
            # Remove markdown code fence
            lines = text.split("\n")
            # Drop first line (```json or ```) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        tasks = json.loads(text)

        if not isinstance(tasks, list):
            logger.warning("AI returned non-list response for task extraction")
            return []

        # Validate and sanitize each task
        validated: list[dict] = []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            title = str(task.get("title", "")).strip()
            if not title:
                continue

            priority = str(task.get("priority", "medium")).lower()
            if priority not in ("low", "medium", "high"):
                priority = "medium"

            due_date = task.get("due_date")
            if due_date:
                # Validate date format
                try:
                    datetime.strptime(str(due_date), "%Y-%m-%d")
                    due_date = str(due_date)
                except (ValueError, TypeError):
                    due_date = None

            validated.append({
                "title": title[:255],
                "description": str(task.get("description", "")).strip()[:500] or None,
                "due_date": due_date,
                "priority": priority,
            })

        logger.info(f"Extracted {len(validated)} tasks from document {filename}")
        return validated

    except json.JSONDecodeError as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Failed to parse AI task extraction response | "
            f"duration={duration_ms:.2f}ms | error={e}"
        )
        return []
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Task extraction failed | duration={duration_ms:.2f}ms | error={e}"
        )
        raise
