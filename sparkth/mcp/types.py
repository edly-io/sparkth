from pydantic import BaseModel, Field


class CourseGenerationPromptRequest(BaseModel):
    course_name: str
    course_description: str
    language: str | None = Field(
        default=None,
        description=(
            "BCP 47 language tag for the generated course, e.g. 'en', 'es', 'fr'. "
            "The whole course — titles, descriptions, lesson text, assessment questions, "
            "answer options and feedback — is written in it. Omit it, or pass a tag the "
            "platform does not support, and the platform default language is used."
        ),
    )
