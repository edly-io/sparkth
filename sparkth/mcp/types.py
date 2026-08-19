from pydantic import BaseModel, Field


class CourseGenerationPromptRequest(BaseModel):
    course_name: str
    course_description: str
    language: str | None = Field(
        default=None,
        description=(
            "BCP 47 language tag for the generated course, e.g. 'en', 'es', 'de', 'pt-BR'. "
            "The whole course — titles, descriptions, lesson text, assessment questions, "
            "answer options and feedback — is written in it. Any language is accepted. "
            "Omit it, or pass a value that is not a valid language tag, and the platform "
            "default language is used."
        ),
    )
