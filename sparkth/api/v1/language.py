"""Read-only endpoint exposing the languages the platform generates content in.

The frontend language picker and the static-UI translation layer both read this
list, so the allowlist is defined once in core config rather than duplicated.

Authenticated, matching the gate on the dashboard the picker lives in. The handler
needs no user object, so the dependency is declared on the route rather than as an
unused argument.
"""

from fastapi import APIRouter, Depends

from sparkth.lib.auth import get_current_user
from sparkth.lib.language import SUPPORTED_LANGUAGES
from sparkth.lib.settings import get_settings
from sparkth.schemas import SupportedLanguage, SupportedLanguages

router = APIRouter()


@router.get("", response_model=SupportedLanguages, dependencies=[Depends(get_current_user)])
async def list_languages() -> SupportedLanguages:
    """Return every supported language and the platform default."""
    languages = [
        SupportedLanguage(code=code, name=info.name, native_name=info.native_name)
        for code, info in SUPPORTED_LANGUAGES.items()
    ]
    return SupportedLanguages(languages=languages, default=get_settings().DEFAULT_LANGUAGE)
