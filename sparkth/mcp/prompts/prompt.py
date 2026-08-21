from pathlib import Path

from sparkth.lib.language import language_display_name


def get_course_generation_prompt(course_name: str, course_description: str, language: str | None) -> str:
    """Render the course-generation prompt for a course written in ``language``.

    ``language`` is a BCP 47 tag supplied by the calling agent, or ``None``. Any tag is
    accepted, not only the ones the platform ships an interface in; an absent or
    unparseable tag falls back to the platform default. The language's English name
    reaches the model, matching the chat system prompt.
    """
    prompt_path = Path(__file__).parent / "course_generation_prompt.txt"
    template = prompt_path.read_text(encoding="utf-8")

    return template.format(
        course_name=course_name,
        course_description=course_description,
        language_name=language_display_name(language),
    )
