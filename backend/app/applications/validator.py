"""Replaces the required-field heuristic that let unchecked required
checkboxes/radio groups pass because their raw HTML `value` was non-empty.

Operates on ApplicationField after answer resolution has populated
`.value` — checkbox/radio/select values are already normalized (True/False,
selected label, or None), not the raw DOM attribute, so this checks the
real semantic state. Browser-native checkValidity() and visible ATS error
scanning still happen in application_workflow.py against the live page;
this module only owns the parts that don't need a browser.
"""
from __future__ import annotations

import re

from app.applications.models import ApplicationField, ValidationIssue

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[+\d][\d\s().-]{6,}$")


def validate_fields(fields: list[ApplicationField]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for field in fields:
        if not field.visible or field.disabled:
            continue
        if field.required and is_empty(field):
            issues.append(ValidationIssue(
                field_id=field.field_id, message=_missing_message(field),
            ))
            continue
        is_email_field = field.normalized_key == "personal.email" and isinstance(field.value, str)
        if field.value and is_email_field and not EMAIL_RE.match(field.value):
            issues.append(ValidationIssue(field_id=field.field_id, message="Invalid email format"))
        is_phone_field = field.normalized_key == "personal.phone" and isinstance(field.value, str)
        if field.value and is_phone_field and not PHONE_RE.match(field.value):
            issues.append(ValidationIssue(field_id=field.field_id, message="Invalid phone format"))
        invalid_select = (
            field.input_type == "select" and field.value is not None
            and field.value not in field.options
        )
        if invalid_select:
            issues.append(ValidationIssue(
                field_id=field.field_id, message="Selected option is not valid",
            ))
    return issues


def is_empty(field: ApplicationField) -> bool:
    if field.input_type == "checkbox":
        # A single required checkbox must be checked (True); a checkbox
        # *group* must have at least one option checked (non-empty list).
        return field.value is False or field.value is None or field.value == []
    if field.input_type == "radio":
        return not field.value
    if field.input_type == "select":
        return not field.value
    if field.input_type == "file":
        return not field.value
    return field.value is None or (isinstance(field.value, str) and not field.value.strip())


def _missing_message(field: ApplicationField) -> str:
    if field.input_type == "checkbox":
        return f"'{field.label}' must be checked"
    if field.input_type == "radio":
        return f"'{field.label}' requires one selected option"
    if field.input_type == "select":
        return f"'{field.label}' requires a valid selection"
    if field.input_type == "file":
        return f"'{field.label}' requires an uploaded file"
    return f"'{field.label}' is required"
