"""
django_undefined
~~~~~~~~~~~~~~~~

Proof-of-concept: Jinja2-style Undefined types for Django's template engine.

GSoC 2026 proposal for:
  "Add ergonomic control over behaviour of missing variables in templates"
  https://github.com/django/new-features/issues/5

Quick start
-----------
In your Django project's conftest.py (for tests with strict mode):

    from django_undefined.patch import patch_django_templates
    patch_django_templates("strict")

Classes available:

    SilentUndefined   — empty string, fully backward-compatible (default)
    LoggingUndefined  — logs a WARNING, returns empty string
    DebugUndefined    — renders {{ variable_name }} literally
    StrictUndefined   — raises UndefinedVariableError on render
"""

from .undefined import (
    Undefined,
    SilentUndefined,
    LoggingUndefined,
    DebugUndefined,
    StrictUndefined,
    UndefinedVariableError,
    get_undefined_class,
)

__all__ = [
    "Undefined",
    "SilentUndefined",
    "LoggingUndefined",
    "DebugUndefined",
    "StrictUndefined",
    "UndefinedVariableError",
    "get_undefined_class",
]

__version__ = "0.1.0-poc"
__author__ = "GSoC 2026 Django Contributor"