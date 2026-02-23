from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AuthenticationPayload(BaseModel):
    api_url: str
    api_token: str


class CourseParams(BaseModel):
    course_id: int
    auth: AuthenticationPayload


class PaginationParams(CourseParams):
    page: int


class CourseFormat(str, Enum):
    ON_CAMPUS = "on_campus"
    ONLINE = "online"
    BLENDED = "blended"


class Course(BaseModel):
    name: str
    course_code: str | None = None
    sis_course_id: int | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    is_public: bool | None = None
    course_format: CourseFormat | None = None
    post_manually: bool | None = None


class CoursePayload(BaseModel):
    course: Course
    enroll_me: bool
    offer: bool | None = None
    enable_sis_reactivation: bool | None = None
    account_id: int
    auth: AuthenticationPayload


class ModuleParams(BaseModel):
    auth: AuthenticationPayload
    course_id: int
    module_id: int
    page: int


class Module(BaseModel):
    name: str
    position: int | None = None
    unlock_at: datetime | None = None
    require_sequential_progress: bool | None = None
    prerequisite_module_ids: list[int] | None = None
    publish_final_grade: bool | None = None


class ModulePayload(BaseModel):
    module: Module
    course_id: int
    auth: AuthenticationPayload


class UpdatedModule(BaseModel):
    name: str | None = None
    position: int | None = None
    unlock_at: datetime | None = None
    require_sequential_progress: bool | None = None
    prerequisite_module_ids: list[int] | None = None
    publish_final_grade: bool | None = None
    published: bool | None = None


class UpdateModulePayload(BaseModel):
    module: UpdatedModule
    course_id: int
    module_id: int
    auth: AuthenticationPayload


class ModuleItemParams(BaseModel):
    auth: AuthenticationPayload
    course_id: int
    module_id: int
    module_item_id: int


class ModuleItemType(str, Enum):
    PAGE = "Page"
    QUIZ = "Quiz"


class ModuleItemCompletionRequirement(BaseModel):
    requirement_type: str
    min_score: float | None = None


class ModuleItem(BaseModel):
    title: str
    module_type: ModuleItemType = ModuleItemType.PAGE
    page_url: str | None = None
    content_id: str | None = None
    position: int | None = None
    indent: int | None = None
    new_tab: bool | None = None
    completion_requirement: ModuleItemCompletionRequirement | None = None

    def to_canvas_payload(self) -> dict[str, object]:
        data = self.model_dump()
        data["type"] = data.pop("module_type")
        return data


class ModuleItemPayload(BaseModel):
    module_id: int
    course_id: int
    module_item: ModuleItem
    auth: AuthenticationPayload


class UpdatedModuleItem(BaseModel):
    title: str | None = None
    position: int | None = None
    indent: int | None = None
    external_url: str | None = None
    new_tab: bool | None = None
    completion_requirement: ModuleItemCompletionRequirement | None = None
    module_id: int | None = None
    published: bool | None = None


class UpdateModuleItemPayload(BaseModel):
    module_id: int
    course_id: int
    item_id: int
    module_item: UpdatedModuleItem
    auth: AuthenticationPayload


class PageRequest(BaseModel):
    auth: AuthenticationPayload
    course_id: int
    page_url: str


class EditingRoles(str, Enum):
    TEACHERS = "teachers"
    STUDENTS = "students"
    MEMBERS = "members"
    PUBLIC = "public"


class Page(BaseModel):
    title: str
    editing_roles: EditingRoles = Field(default=EditingRoles.TEACHERS)
    body: str | None = None
    notify_of_update: bool | None = None
    published: bool | None = None
    front_page: bool | None = None
    publish_at: datetime | None = None


class PagePayload(BaseModel):
    auth: AuthenticationPayload
    course_id: int
    wiki_page: Page


class UpdatedPage(BaseModel):
    title: str
    body: str
    editing_roles: EditingRoles = Field(default=EditingRoles.TEACHERS)
    notify_of_update: bool | None = None
    published: bool | None = None
    publish_at: datetime | None = None
    front_page: bool | None = None


class UpdatePagePayload(BaseModel):
    auth: AuthenticationPayload
    course_id: int
    url_or_id: str
    wiki_page: UpdatedPage


class QuizParams(BaseModel):
    auth: AuthenticationPayload
    course_id: int
    quiz_id: int
    page: int


class QuizType(str, Enum):
    ASSIGNMENT = "assignment"
    PRACTICE_QUIZ = "practice_quiz"
    GRADED_SURVEY = "graded_survey"
    SURVEY = "survey"


class HideResults(str, Enum):
    ALWAYS = "always"
    UNTIL_AFTER_LAST_ATTEMPT = "until_after_last_attempt"


class ScoringPolicy(str, Enum):
    KEEP_HIGHEST = "keep_highest"
    KEEP_LATEST = "keep_latest"


class Quiz(BaseModel):
    title: str
    description: str
    quiz_type: QuizType
    assignment_group_id: int | None = None
    time_limit: int | None = None
    shuffle_answers: bool | None = None
    hide_results: HideResults | None = None
    show_correct_answers: bool | None = None
    allowed_attempts: int | None = None
    scoring_policy: ScoringPolicy | None = None
    one_question_at_a_time: bool | None = None
    cant_go_back: bool | None = None
    due_at: datetime | None = None
    lock_at: datetime | None = None
    unlock_at: datetime | None = None
    published: bool | None = None


class QuizPayload(BaseModel):
    auth: AuthenticationPayload
    course_id: int
    quiz: Quiz


class UpdatedQuiz(BaseModel):
    title: str | None = None
    description: str | None = None
    quiz_type: QuizType | None = None
    assignment_group_id: int | None = None
    time_limit: int | None = None
    shuffle_answers: bool | None = None
    hide_results: HideResults | None = None
    show_correct_answers: bool | None = None
    allowed_attempts: int | None = None
    scoring_policy: ScoringPolicy | None = None
    one_question_at_a_time: bool | None = None
    cant_go_back: bool | None = None
    due_at: datetime | None = None
    lock_at: datetime | None = None
    unlock_at: datetime | None = None
    published: bool | None = None


class UpdateQuizPayload(BaseModel):
    auth: AuthenticationPayload
    course_id: int
    quiz_id: int
    quiz: UpdatedQuiz


class QuestionParams(BaseModel):
    auth: AuthenticationPayload
    course_id: int
    quiz_id: int
    question_id: int


class Answer(BaseModel):
    answer_text: str
    answer_weight: int
    answer_comments: str | None = None


class QuestionType(str, Enum):
    CALCULATED = "calculated_question"
    FILL_IN_MULTIPLE_BLANKS = "fill_in_multiple_blanks_question"
    MULTIPLE_CHOICE = "multiple_choice_question"
    TEXT_ONLY = "text_only_question"
    TRUE_FALSE = "true_false_question"


class Question(BaseModel):
    question_name: str
    question_text: str
    quiz_group_id: int | None = None
    question_type: QuestionType | None = None
    position: int | None = None
    points_possible: float | None = None
    correct_comments: str | None = None
    incorrect_comments: str | None = None
    neutral_comments: str | None = None
    text_after_answers: str | None = None
    answers: list[Answer] | None = None


class QuestionPayload(BaseModel):
    question: Question
    course_id: int
    quiz_id: int
    auth: AuthenticationPayload


class UpdatedQuestion(BaseModel):
    question_name: str | None = None
    question_text: str | None = None
    quiz_group_id: int | None = None
    question_type: QuestionType | None = None
    position: int | None = None
    points_possible: float | None = None
    correct_comments: str | None = None
    incorrect_comments: str | None = None
    neutral_comments: str | None = None
    text_after_answers: str | None = None
    answers: list[Answer] | None = None


class UpdateQuestionPayload(BaseModel):
    question: UpdatedQuestion
    course_id: int
    quiz_id: int
    question_id: int
    auth: AuthenticationPayload
