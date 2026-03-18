# django-undefined — GSoC 2026 Proof of Concept

**Proposal:** *Add ergonomic control over behaviour of missing variables in templates*  
**Issue:** [django/new-features#5](https://github.com/django/new-features/issues/5)  
**Ticket:** [#28618](https://code.djangoproject.com/ticket/28618) (open since 2017)  
**Author:** soro wahagnonan jean — GSoC 2026 applicant

---

## The Problem

Django templates silently convert missing variables to empty strings:

```html
<!-- template.html -->
Hello {{ usre.name }}!  {# typo: "usre" instead of "user" #}
```

```
Output: "Hello !"   ← no error, no warning, silent failure
```

The existing `string_if_invalid` setting is documented as a debugging tool
but is [known to break rendering](https://adamj.eu/tech/2023/08/09/django-perils-string-if-invalid/)
in many cases (filters, URL tags, template inheritance). The existing PR
[#19353](https://github.com/django/django/pull/19353) was marked
**"needs improvement"** because it only provides a blunt global toggle.

---

## The Solution: Jinja2-style Undefined Types

Inspired by [Jinja2's undefined types](https://jinja.palletsprojects.com/en/stable/api/#undefined-types)
and [Adam Johnson's suggestion](https://forum.djangoproject.com/t/raise-error-for-missing-variable-used-in-template/39776)
on the Django Forum, this PoC introduces a configurable `Undefined` class
hierarchy that replaces the hard-coded empty string fallback.

### The Four Classes

| Class | Behaviour | Use case |
|---|---|---|
| `SilentUndefined` | Returns `""` — identical to current Django | Production (default) |
| `LoggingUndefined` | Returns `""` + emits a `WARNING` log | Staging / CI |
| `DebugUndefined` | Renders `{{ variable_name }}` visually | Local dev |
| `StrictUndefined` | Raises `UndefinedVariableError` on render | Dev / test |

### Proposed Configuration

```python
# settings.py
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "OPTIONS": {
        # Default: "silent" (fully backward-compatible)
        "undefined": "strict",   # raise in development/tests
        # "undefined": "logging", # log warnings in staging
        # "undefined": "debug",   # visual rendering in local dev
        # "undefined": "myapp.utils.CustomUndefined",  # custom class
    }
}]
```

---

## Key Design Decisions

### ✅ `{% if missing_var %}` still works correctly

`StrictUndefined.__bool__()` returns `False` — it never raises.
Only `__str__()` / `__format__()` raise, i.e. only when the value is
actually rendered into output. This means:

```django
{% if user %}          {# → False, no exception #}
    {{ user.name }}    {# → UndefinedVariableError #}
{% endif %}
```

### ✅ Zero migration cost

`SilentUndefined` is the default. Existing templates, the Django admin,
and third-party packages require zero changes.

### ✅ Fully extensible

Teams can subclass `Undefined` for custom behaviour (e.g. Sentry reporting):

```python
class SentryUndefined(Undefined):
    def __str__(self):
        sentry_sdk.capture_message(f"Undefined template variable: {self._variable_name}")
        return ""
```

### ✅ Deprecates `string_if_invalid`

This approach naturally supersedes `string_if_invalid`. A deprecation
warning will be added in the GSoC implementation.

---

## Repository Structure

```
django_undefined/
├── __init__.py        # Public API
├── undefined.py       # The 4 Undefined classes + get_undefined_class()
└── patch.py           # Monkey-patch for PoC demo (not part of final PR)

tests/
├── test_undefined.py      # Unit tests (no Django required)
└── test_integration.py    # Integration tests (Django required)
```

---

## Running the Tests

```bash
# Unit tests only (no Django needed)
pip install pytest
python -m pytest tests/test_undefined.py -v

# Integration tests (requires Django)
pip install django pytest-django
python -m pytest tests/test_integration.py -v
```

---

## Where the Real Change Lives in Django

The actual Django PR would modify two files:

**`django/template/undefined.py`** (new file) — the 4 `Undefined` classes.

**`django/template/base.py`** — one key change in `Variable._resolve_lookup()`:

```python
# BEFORE (current Django ~line 850):
except Exception:
    if string_if_invalid:
        ...
        return string_if_invalid % self.var
    else:
        return string_if_invalid  # i.e. ""

# AFTER (proposed):
except Exception:
    undefined_class = context.template.engine.undefined_class
    origin = getattr(context.template, "name", "") or ""
    return undefined_class(variable_name=self.var, origin=origin)
```

---

## Forum Discussion

- [GSoC 2026 pre-proposal on Django Forum](https://forum.djangoproject.com/c/internals/mentorship/gsoc/33)
- [Original feature discussion (March 2025)](https://forum.djangoproject.com/t/raise-error-for-missing-variable-used-in-template/39776)
- [Ticket #28618](https://code.djangoproject.com/ticket/28618)

---

*This is a proof-of-concept for a GSoC 2026 application. It is not production-ready.*