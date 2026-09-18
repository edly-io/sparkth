from pydantic import BaseModel, Field

from sparkth.plugins.moodle.enums import QuestionType


class Auth(BaseModel):
    api_url: str = Field(..., description="Moodle site URL")
    api_token: str = Field(..., description="Moodle web service token")


class CoursePayload(BaseModel):
    auth: Auth
    fullname: str = Field(..., description="Course full name")
    shortname: str = Field(..., description="Course short name, unique on the site")
    categoryid: int = Field(1, description="Category to create the course in")
    summary: str = Field("", description="Course summary HTML")
    lang: str = Field("", description="Course language code, empty for the site default")


class SectionPayload(BaseModel):
    auth: Auth
    courseid: int = Field(..., description="Course to append the section to")
    name: str = Field(..., description="Section name")
    summary: str = Field("", description="Section summary HTML")


class PagePayload(BaseModel):
    auth: Auth
    courseid: int = Field(..., description="Course containing the section")
    sectionnum: int = Field(..., description="Section number returned by moodle_create_section")
    name: str = Field(..., description="Activity name")
    content: str = Field(..., description="Page body HTML")
    intro: str = Field("", description="Activity description HTML")


class Question(BaseModel):
    qtype: QuestionType = Field(..., description="Question type")
    name: str = Field(..., description="Question name")
    questiontext: str = Field(..., description="Question text HTML")
    answers: list[str] = Field(default_factory=list, description="Options; multichoice only")
    correctindex: int = Field(0, description="Index into answers that is correct; multichoice only")
    correcttrue: bool = Field(True, description="Whether True is correct; truefalse only")


class QuizPayload(BaseModel):
    auth: Auth
    courseid: int = Field(..., description="Course containing the section")
    sectionnum: int = Field(..., description="Section number returned by moodle_create_section")
    name: str = Field(..., description="Quiz name")
    intro: str = Field("", description="Quiz description HTML")
    questions: list[Question] = Field(..., description="Questions to create in the quiz")
