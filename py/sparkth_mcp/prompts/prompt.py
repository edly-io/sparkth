from pathlib import Path


def get_course_generation_prompt(course_name: str, course_description: str) -> str:
    prompt_path = Path(__file__).parent / "course_generation_prompt.txt"
    template = prompt_path.read_text(encoding="utf-8")

    return template.format(course_name=course_name, course_description=course_description)
