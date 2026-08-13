from pathlib import Path

from sparkth.lib.language import SUPPORTED_LANGUAGES


def get_course_generation_prompt(course_name: str, course_description: str, language: str) -> str:
    """Render the course-generation prompt for a course written in ``language``.

    ``language`` is an already-resolved, allowlisted BCP 47 tag — the caller resolves the
    agent-supplied value with :func:`sparkth.lib.language.resolve_language` first. The
    tag's English name reaches the model, matching the chat system prompt.
    """
    prompt_path = Path(__file__).parent / "course_generation_prompt.txt"
    template = prompt_path.read_text(encoding="utf-8")

    return template.format(
        course_name=course_name,
        course_description=course_description,
        language_name=SUPPORTED_LANGUAGES[language].name,
    )
