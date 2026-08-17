"""Read-only endpoint exposing the languages a user may choose from.

The allowlist is defined once in core config and served from here rather than
duplicated client-side — the frontend language picker and the static-UI
translation layer both read it from this endpoint.

Unauthenticated, and the only endpoint outside ``auth`` that is: the translation
layer has to render the login, register and password-reset pages, which have no
token yet, and gating it there would force the frontend to carry the duplicate
list this endpoint exists to remove. What it serves is a compile-time constant —
the supported-language table and the platform default — so there is no user data,
no database read, and nothing to enumerate.
"""

from fastapi import APIRouter

from sparkth.api.v1.language.schemas import SupportedLanguage, SupportedLanguages
from sparkth.lib.language import SUPPORTED_LANGUAGES
from sparkth.lib.settings import get_settings

router = APIRouter()


@router.get("", response_model=SupportedLanguages)
async def list_languages() -> SupportedLanguages:
    """Return every supported language and the platform default."""
    languages = [
        SupportedLanguage(code=code, name=info.name, native_name=info.native_name)
        for code, info in SUPPORTED_LANGUAGES.items()
    ]
    return SupportedLanguages(languages=languages, default=get_settings().DEFAULT_LANGUAGE)
