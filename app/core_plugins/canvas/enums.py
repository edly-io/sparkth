from enum import Enum


class CourseFormat(str, Enum):
    ON_CAMPUS = "on_campus"
    ONLINE = "online"
    BLENDED = "blended"


class ModuleItemType(str, Enum):
    PAGE = "Page"
    QUIZ = "Quiz"


class EditingRoles(str, Enum):
    TEACHERS = "teachers"
    STUDENTS = "students"
    MEMBERS = "members"
    PUBLIC = "public"


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


class QuestionType(str, Enum):
    CALCULATED = "calculated_question"
    FILL_IN_MULTIPLE_BLANKS = "fill_in_multiple_blanks_question"
    MULTIPLE_CHOICE = "multiple_choice_question"
    TEXT_ONLY = "text_only_question"
    TRUE_FALSE = "true_false_question"
