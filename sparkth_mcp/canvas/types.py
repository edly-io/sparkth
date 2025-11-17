from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import datetime


class AuthenticationPayload(BaseModel):
    api_url: str
    api_token: str


class CourseParams(BaseModel):
    page: int
    course_id: int
    auth: AuthenticationPayload


class CourseFormat(str, Enum):
    ON_CAMPUS = "on_campus"
    ONLINE = "online"
    BLENDED = "blended"


class Course(BaseModel):
    name: str
    course_code: Optional[str] = None
    sis_course_id: Optional[int] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    is_public: Optional[bool] = None
    course_format: Optional[CourseFormat] = None
    post_manually: Optional[bool] = None


class CoursePayload(BaseModel):
    course: Course
    enroll_me: bool
    offer: Optional[bool] = None
    enable_sis_reactivation: Optional[bool] = None
    account_id: int
    auth: AuthenticationPayload


class ModuleParams(BaseModel):
    auth: AuthenticationPayload
    course_id: int
    module_id: int
    page: int


class Module(BaseModel):
    name: str
    position: Optional[int] = None
    unlock_at: Optional[datetime] = None
    require_sequential_progress: Optional[bool] = None
    prerequisite_module_ids: Optional[List[int]] = None
    publish_final_grade: Optional[bool] = None


class ModulePayload(BaseModel):
    module: Module
    course_id: int
    auth: AuthenticationPayload


class UpdatedModule(BaseModel):
    name: Optional[str] = None
    position: Optional[int] = None
    unlock_at: Optional[datetime] = None
    require_sequential_progress: Optional[bool] = None
    prerequisite_module_ids: Optional[List[int]] = None
    publish_final_grade: Optional[bool] = None
    published: Optional[bool] = None


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
    min_score: Optional[float] = None


class ModuleItem(BaseModel):
    title: str
    type: ModuleItemType = Field(alias="type")
    page_url: Optional[str] = None
    content_id: Optional[str] = None
    position: Optional[int] = None
    indent: Optional[int] = None
    new_tab: Optional[bool] = None
    completion_requirement: Optional[ModuleItemCompletionRequirement] = None


class ModuleItemPayload(BaseModel):
    module_id: int
    course_id: int
    module_item: ModuleItem
    auth: AuthenticationPayload


class UpdatedModuleItem(BaseModel):
    title: Optional[str] = None
    position: Optional[int] = None
    indent: Optional[int] = None
    external_url: Optional[str] = None
    new_tab: Optional[bool] = None
    completion_requirement: Optional[ModuleItemCompletionRequirement] = None
    module_id: Optional[int] = None
    published: Optional[bool] = None


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
    body: Optional[str] = None
    notify_of_update: Optional[bool] = None
    published: Optional[bool] = None
    front_page: Optional[bool] = None
    publish_at: Optional[datetime] = None


class PagePayload(BaseModel):
    auth: AuthenticationPayload
    course_id: int
    wiki_page: Page


class UpdatedPage(BaseModel):
    title: str
    body: str
    editing_roles: EditingRoles = Field(default=EditingRoles.TEACHERS)
    notify_of_update: Optional[bool] = None
    published: Optional[bool] = None
    publish_at: Optional[datetime] = None
    front_page: Optional[bool] = None


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
    assignment_group_id: Optional[int] = None
    time_limit: Optional[int] = None
    shuffle_answers: Optional[bool] = None
    hide_results: Optional[HideResults] = None
    show_correct_answers: Optional[bool] = None
    allowed_attempts: Optional[int] = None
    scoring_policy: Optional[ScoringPolicy] = None
    one_question_at_a_time: Optional[bool] = None
    cant_go_back: Optional[bool] = None
    due_at: Optional[datetime] = None
    lock_at: Optional[datetime] = None
    unlock_at: Optional[datetime] = None
    published: Optional[bool] = None


class QuizPayload(BaseModel):
    auth: AuthenticationPayload
    course_id: int
    quiz: Quiz


class UpdatedQuiz(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    quiz_type: Optional[QuizType] = None
    assignment_group_id: Optional[int] = None
    time_limit: Optional[int] = None
    shuffle_answers: Optional[bool] = None
    hide_results: Optional[HideResults] = None
    show_correct_answers: Optional[bool] = None
    allowed_attempts: Optional[int] = None
    scoring_policy: Optional[ScoringPolicy] = None
    one_question_at_a_time: Optional[bool] = None
    cant_go_back: Optional[bool] = None
    due_at: Optional[datetime] = None
    lock_at: Optional[datetime] = None
    unlock_at: Optional[datetime] = None
    published: Optional[bool] = None


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
    answer_comments: Optional[str] = None


class QuestionType(str, Enum):
    CALCULATED = "calculated_question"
    FILL_IN_MULTIPLE_BLANKS = "fill_in_multiple_blanks_question"
    MULTIPLE_CHOICE = "multiple_choice_question"
    TEXT_ONLY = "text_only_question"
    TRUE_FALSE = "true_false_question"


class Question(BaseModel):
    question_name: str
    question_text: str
    quiz_group_id: Optional[int] = None
    question_type: Optional[QuestionType] = None
    position: Optional[int] = None
    points_possible: Optional[float] = None
    correct_comments: Optional[str] = None
    incorrect_comments: Optional[str] = None
    neutral_comments: Optional[str] = None
    text_after_answers: Optional[str] = None
    answers: Optional[List[Answer]] = None


class QuestionPayload(BaseModel):
    question: Question
    course_id: int
    quiz_id: int
    auth: AuthenticationPayload


class UpdatedQuestion(BaseModel):
    question_name: Optional[str] = None
    question_text: Optional[str] = None
    quiz_group_id: Optional[int] = None
    question_type: Optional[QuestionType] = None
    position: Optional[int] = None
    points_possible: Optional[float] = None
    correct_comments: Optional[str] = None
    incorrect_comments: Optional[str] = None
    neutral_comments: Optional[str] = None
    text_after_answers: Optional[str] = None
    answers: Optional[List[Answer]] = None


class UpdateQuestionPayload(BaseModel):
    question: UpdatedQuestion
    course_id: int
    quiz_id: int
    question_id: int
    auth: AuthenticationPayload


PayloadType = Union[
    CoursePayload,
    ModulePayload,
    UpdateModulePayload,
    ModuleItemPayload,
    UpdateModuleItemPayload,
    PagePayload,
    UpdatePagePayload,
    QuizPayload,
    UpdateQuizPayload,
    QuestionPayload,
    UpdateQuestionPayload,
]
