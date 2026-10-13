"""Which changes to an activity's fields the learner state it already saved cannot survive.

pxc-lib hands a stored value to the sandbox as it is, without checking it against the field's
definition. So a field whose type, scope or nested schema changes would serve values in the old
shape, or strand them under another scope, and a removed field's values would come back if the
name were reused. A field's ``default`` is never stored, so changing it is safe, and so is adding a
field.
"""

from collections.abc import Mapping


def incompatible_field_changes(
    old_fields: Mapping[str, Mapping[str, object]], new_fields: Mapping[str, Mapping[str, object]]
) -> list[str]:
    """Describe, one entry per field, every change from ``old_fields`` that is not backward compatible.

    Only backward-compatible changes pass: adding a field, or changing a field's ``default``. A
    field missing from ``new_fields``, or one whose definition differs once ``default`` is set
    aside, is reported. The check covers each field's declared shape, not how the sandbox reads or
    writes values of that shape.
    """
    changes = []
    for name, definition in old_fields.items():
        if name not in new_fields:
            changes.append(f"field {name!r} was removed")
        elif _without_default(definition) != _without_default(new_fields[name]):
            changes.append(f"field {name!r} changed its type, scope or schema")
    return changes


def _without_default(definition: Mapping[str, object]) -> dict[str, object]:
    """A field's definition minus its ``default``, which saved values do not depend on."""
    return {key: value for key, value in definition.items() if key != "default"}
