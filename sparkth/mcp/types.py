from pydantic import BaseModel, Field


class CourseGenerationPromptRequest(BaseModel):
    course_name: str
    course_description: str
    # 35 is the practical ceiling for a registered BCP 47 tag, the bound ``User.language``
    # carries for the same reason. This field is read straight off an unauthenticated
    # request, so without it the caller decides how long the value travelling into the
    # resolver and the log is.
    language: str | None = Field(
        default=None,
        max_length=35,
        description=(
            "BCP 47 language tag for the generated course, e.g. 'en', 'es', 'de', 'pt-BR'. "
            "The whole course — titles, descriptions, lesson text, assessment questions, "
            "answer options and feedback — is written in it. Any language is accepted. "
            "Omit it, or pass a value that is not a valid language tag, and the platform "
            "default language is used — but a value longer than 35 characters is rejected "
            "outright rather than falling back, being far past the length of any real tag."
        ),
    )
