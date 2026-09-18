from enum import Enum


class QuestionType(str, Enum):
    MULTICHOICE = "multichoice"
    TRUEFALSE = "truefalse"
