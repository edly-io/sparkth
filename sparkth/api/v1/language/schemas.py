"""Pydantic models for the supported-languages API."""

from pydantic import BaseModel


class SupportedLanguage(BaseModel):
    """One language the platform can generate content in."""

    code: str
    name: str
    native_name: str


class SupportedLanguages(BaseModel):
    """The full allowlist plus the default applied to users who never chose."""

    languages: list[SupportedLanguage]
    default: str
