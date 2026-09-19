"""Turn a raw DOM field snapshot into a consistent list of ApplicationField.

Pure and browser-independent: takes the plain dicts a page.evaluate() call
produces, so it is unit-testable without Playwright. Radio buttons sharing
a `name` become one field; checkboxes are never treated as text fields.
"""
from __future__ import annotations

from app.applications.models import ApplicationField

# Richer than application_workflow.FORM_SNAPSHOT — adds `options` (for
# <select>) and explicit `visible`/`disabled`, which the answer resolver and
# validator both need. application_workflow.py's own FORM_SNAPSHOT stays
# unchanged; it only needs the fingerprint, not a full field schema.
FIELD_SNAPSHOT_JS = """() => Array.from(document.querySelectorAll('input,select,textarea'))
 .filter(e => e.type !== 'password' && e.type !== 'hidden')
 .map((e) => ({
   name: e.name, id: e.id,
   type: e.tagName.toLowerCase() === 'select' ? 'select' : e.type,
   label: (e.labels?.[0]?.innerText || e.getAttribute('aria-label')
     || e.placeholder || e.name || '').trim(),
   // For a radio/checkbox group, the per-input label is the option text
   // ("Yes"/"No") — the actual question lives on the group's fieldset
   // legend (or an aria-label on the fieldset), never on one option.
   group_label: (e.closest('fieldset')?.querySelector('legend')?.innerText
     || e.closest('fieldset')?.getAttribute('aria-label') || '').trim(),
   // A <select>'s .value is the selected <option>'s value ATTRIBUTE, which
   // is often not its visible text (<option value="linkedin">LinkedIn) —
   // read the visible text instead so this always matches `options` below
   // (also built from visible text). But check .value first: an unselected
   // placeholder option (value="") still has non-empty display text
   // ("Select an option") and the browser auto-selects it by default, so
   // reading text unconditionally would make an empty select look filled.
   value: e.tagName.toLowerCase() === 'select'
     ? (e.value ? (e.selectedOptions[0]?.text.trim() || '') : '')
     : e.type === 'file' ? Array.from(e.files || []).map(f => f.name).join(',') : e.value,
   checked: e.checked || false, required: e.required || false,
   options: e.tagName.toLowerCase() === 'select'
     ? Array.from(e.options).map(o => o.text.trim()).filter(t => t) : [],
   visible: !!e.getClientRects().length, disabled: e.disabled || false,
 }))"""

_TEXTLIKE_TYPES = {"text", "email", "tel", "url", "search"}


def _field_id(item: dict, index: int) -> str:
    return item.get("id") or item.get("name") or f"field_{index}"


def extract_fields(raw_fields: list[dict]) -> list[ApplicationField]:
    fields: list[ApplicationField] = []
    grouped: dict[str, list[dict]] = {}
    singles: list[dict] = []

    for item in raw_fields:
        kind = (item.get("type") or "text").lower()
        name = item.get("name") or ""
        if kind in {"radio", "checkbox"} and name:
            grouped.setdefault(name, []).append(item)
        else:
            singles.append(item)

    index = 0
    for name, group in grouped.items():
        kind = (group[0].get("type") or "").lower()
        options = [g.get("label", "") for g in group]
        required = any(g.get("required") for g in group)
        visible = any(g.get("visible", True) for g in group)
        disabled = all(g.get("disabled", False) for g in group)
        group_label = group[0].get("group_label") or group[0].get("label", name)
        if kind == "radio":
            selected = next((g.get("label", "") for g in group if g.get("checked")), None)
            fields.append(ApplicationField(
                field_id=name, label=group_label, normalized_key=None,
                input_type="radio", required=required, options=options, value=selected,
                visible=visible, disabled=disabled,
            ))
        elif len(group) == 1:
            # A checkbox "group" of one is just a single checkbox — most
            # HTML checkboxes have a unique `name`, so this is the common
            # case, not the exception. Keep it a plain boolean field.
            fields.append(ApplicationField(
                field_id=name, label=group[0].get("label", name), normalized_key=None,
                input_type="checkbox", required=required, value=bool(group[0].get("checked")),
                visible=visible, disabled=disabled,
            ))
        else:  # a real checkbox group (2+ checkboxes sharing a name)
            checked_labels = [g.get("label", "") for g in group if g.get("checked")]
            fields.append(ApplicationField(
                field_id=name, label=group_label, normalized_key=None,
                input_type="checkbox", required=required, options=options,
                value=checked_labels or None, visible=visible, disabled=disabled,
            ))
        index += 1

    for item in singles:
        kind = (item.get("type") or "text").lower()
        if kind in _TEXTLIKE_TYPES:
            input_type = "text"
        elif kind in {"textarea", "number", "date", "select", "file"}:
            input_type = kind
        elif kind == "checkbox":
            input_type = "checkbox"
        else:
            input_type = "text"

        value: str | bool | list[str] | None
        if input_type == "checkbox":
            value = bool(item.get("checked"))
        else:
            value = item.get("value") or None

        fields.append(ApplicationField(
            field_id=_field_id(item, index), label=item.get("label", ""), normalized_key=None,
            input_type=input_type, required=bool(item.get("required")),
            options=item.get("options", []) or [], value=value,
            visible=item.get("visible", True), disabled=item.get("disabled", False),
        ))
        index += 1

    return fields
