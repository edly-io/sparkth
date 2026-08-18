"""Permission domain-exception messages are translated into the active locale.

The exceptions are raised during request handling, so the message template is
translated at raise time; all classes share the same marking pattern, exercised
here through one formatted and one already-covered plain representative.
"""

from sparkth.core.i18n import locale_context
from sparkth.core.permissions.exceptions import RoleAlreadyExists, RoleNotFound
from sparkth.lib.testing import AddTranslation


def test_role_not_found_translates_the_message_template(translation_catalog: AddTranslation) -> None:
    translation_catalog("Role not found: {role_name}", "Rol no encontrado: {role_name}")
    with locale_context("es"):
        assert str(RoleNotFound("editor")) == "Rol no encontrado: editor"


def test_role_already_exists_translates_the_message_template(translation_catalog: AddTranslation) -> None:
    translation_catalog("Role already exists: {name}", "El rol ya existe: {name}")
    with locale_context("es"):
        assert str(RoleAlreadyExists("editor")) == "El rol ya existe: editor"


def test_messages_fall_back_to_english_outside_a_request_locale() -> None:
    assert str(RoleNotFound("editor")) == "Role not found: editor"
