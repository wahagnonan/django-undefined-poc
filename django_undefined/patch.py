"""
django_undefined.patch
~~~~~~~~~~~~~~~~~~~~~~

Monkey-patch Django's ``Variable.resolve()`` to use the configurable
``Undefined`` class system instead of the hard-coded ``string_if_invalid``.

This demonstrates exactly where and how the real Django core change would
be made in ``django/template/base.py``.

Usage (in your Django project's settings or conftest.py):

    from django_undefined.patch import patch_django_templates
    patch_django_templates(undefined_class="strict")   # or "logging", "debug"

Or per-engine in TEMPLATES settings (the proposed final API):

    TEMPLATES = [{
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "OPTIONS": {
            "undefined": "strict",  # or full dotted path to custom class
        }
    }]
"""

from django.template.base import Variable
from django.template.exceptions import VariableDoesNotExist

from .undefined import Undefined, SilentUndefined, get_undefined_class


# Keep a reference to the original method so we can restore it in tests.
_original_resolve = Variable._resolve_lookup


def _patched_resolve_lookup(self, context, undefined_class=SilentUndefined):
    """
    Replacement for ``Variable._resolve_lookup()``.

    On a successful lookup the behaviour is identical to the original.
    On failure, instead of returning ``string_if_invalid`` (a hard-coded
    string), we return an instance of the configured ``Undefined`` class.

    This method mirrors the logic of the original ``_resolve_lookup`` in
    ``django/template/base.py`` but replaces the final fallback.

    In the real implementation this would receive the ``undefined_class``
    from the engine's options, not as a parameter.
    """
    current = context
    try:
        for bit in self.lookups:
            try:
                # Dict lookup
                current = current[bit]
            except (TypeError, AttributeError, KeyError, ValueError,
                    IndexError):
                try:
                    # Attribute lookup
                    current = getattr(current, bit)
                except (TypeError, AttributeError):
                    try:
                        # List-index lookup
                        current = current[int(bit)]
                    except (
                        IndexError,
                        ValueError,
                        KeyError,
                        TypeError,
                    ):
                        raise VariableDoesNotExist(
                            "Failed lookup for key [%s] in %r",
                            (bit, current),
                        )
            if callable(current):
                try:
                    current = current()
                except Exception:
                    raise VariableDoesNotExist(
                        "Failed lookup for key [%s] in %r",
                        (bit, current),
                    )
        return current
    except Exception:
        # --- THE KEY CHANGE ---
        # Instead of: return string_if_invalid % self.var  (current Django)
        # We return a configurable Undefined instance:
        origin = getattr(context, "template", None)
        origin_name = getattr(origin, "name", "") or ""
        return undefined_class(
            variable_name=self.var,
            origin=origin_name,
        )


def patch_django_templates(undefined_class="strict"):
    """
    Apply the monkey-patch to Django's template engine.

    This is the simplest way to test the PoC in an existing Django project
    without modifying Django's source code.

    Parameters
    ----------
    undefined_class : str or type
        The ``Undefined`` class to use. Accepts the same values as
        ``get_undefined_class()``: ``"silent"``, ``"logging"``,
        ``"debug"``, ``"strict"``, or a full dotted import path.

    Example
    -------
    In your ``conftest.py`` (pytest) or ``manage.py`` / ``settings.py``:

        from django_undefined.patch import patch_django_templates
        patch_django_templates("strict")

    This will make every missing template variable raise
    ``UndefinedVariableError`` during rendering, immediately revealing
    typos and missing context variables in your test suite.
    """
    cls = get_undefined_class(undefined_class)

    def _bound_resolve(self, context):
        return _patched_resolve_lookup(self, context, undefined_class=cls)

    Variable._resolve_lookup = _bound_resolve
    return cls


def unpatch_django_templates():
    """Restore the original ``Variable._resolve_lookup()`` method."""
    Variable._resolve_lookup = _original_resolve