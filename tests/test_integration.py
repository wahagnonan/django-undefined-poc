"""
tests/test_integration.py
~~~~~~~~~~~~~~~~~~~~~~~~~

Integration tests with a real Django template engine.

These tests verify that the monkey-patch works correctly and that the
Undefined classes behave as expected end-to-end.

Run with:  python -m pytest tests/test_integration.py -v

Requires: Django installed (pip install django)
"""

import pytest
import django
from django.conf import settings

# Minimal Django config for testing
if not settings.configured:
    settings.configure(
        TEMPLATES=[{
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [],
            "APP_DIRS": False,
            "OPTIONS": {"string_if_invalid": ""},
        }],
        INSTALLED_APPS=[],
    )
    django.setup()

from django.template import Template, Context

from django_undefined.undefined import (
    SilentUndefined,
    LoggingUndefined,
    DebugUndefined,
    StrictUndefined,
    UndefinedVariableError,
)
from django_undefined.patch import patch_django_templates, unpatch_django_templates


@pytest.fixture(autouse=True)
def restore_patch():
    """Always restore the original Django resolve after each test."""
    yield
    unpatch_django_templates()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def render(template_str, context_dict=None):
    t = Template(template_str)
    c = Context(context_dict or {})
    return t.render(c)


# ---------------------------------------------------------------------------
# SilentUndefined — default, zero behaviour change
# ---------------------------------------------------------------------------

class TestSilentIntegration:

    def test_missing_variable_renders_empty(self):
        patch_django_templates("silent")
        result = render("Hello {{ name }}!")
        assert result == "Hello !"

    def test_present_variable_renders_correctly(self):
        patch_django_templates("silent")
        result = render("Hello {{ name }}!", {"name": "Django"})
        assert result == "Hello Django!"

    def test_if_tag_with_missing_var(self):
        patch_django_templates("silent")
        result = render("{% if name %}yes{% else %}no{% endif %}")
        assert result == "no"

    def test_for_tag_with_missing_list(self):
        patch_django_templates("silent")
        result = render("{% for x in items %}{{ x }},{% endfor %}end")
        assert result == "end"

    def test_chained_missing_attr(self):
        patch_django_templates("silent")
        result = render("{{ user.profile.city }}")
        assert result == ""

    def test_filter_on_missing_var(self):
        patch_django_templates("silent")
        result = render('{{ name|default:"stranger" }}')
        # With SilentUndefined, name == "" which is falsy → default applies
        assert result == "stranger"


# ---------------------------------------------------------------------------
# DebugUndefined — visible output
# ---------------------------------------------------------------------------

class TestDebugIntegration:

    def test_missing_variable_shows_name(self):
        patch_django_templates("debug")
        result = render("Hello {{ name }}!")
        assert result == "Hello {{ name }}!"

    def test_present_variable_renders_correctly(self):
        patch_django_templates("debug")
        result = render("Hello {{ name }}!", {"name": "Django"})
        assert result == "Hello Django!"

    def test_chained_missing_attr_shows_path(self):
        patch_django_templates("debug")
        result = render("{{ user.profile.city }}")
        # Shows the full failed lookup path
        assert "user" in result

    def test_if_tag_with_missing_var_is_false(self):
        patch_django_templates("debug")
        result = render("{% if name %}yes{% else %}no{% endif %}")
        assert result == "no"


# ---------------------------------------------------------------------------
# LoggingUndefined — warning log
# ---------------------------------------------------------------------------

class TestLoggingIntegration:
    import logging

    def test_missing_variable_logs_warning(self, caplog):
        import logging
        patch_django_templates("logging")
        with caplog.at_level(logging.WARNING, logger="django.template"):
            result = render("Hello {{ name }}!")
        assert result == "Hello !"
        assert "name" in caplog.text

    def test_present_variable_no_log(self, caplog):
        import logging
        patch_django_templates("logging")
        with caplog.at_level(logging.WARNING, logger="django.template"):
            render("Hello {{ name }}!", {"name": "Django"})
        assert not caplog.records


# ---------------------------------------------------------------------------
# StrictUndefined — raises on render
# ---------------------------------------------------------------------------

class TestStrictIntegration:

    def test_missing_variable_raises(self):
        patch_django_templates("strict")
        with pytest.raises(UndefinedVariableError) as exc_info:
            render("Hello {{ name }}!")
        assert "name" in str(exc_info.value)

    def test_present_variable_does_not_raise(self):
        patch_django_templates("strict")
        result = render("Hello {{ name }}!", {"name": "Django"})
        assert result == "Hello Django!"

    def test_if_tag_does_not_raise(self):
        """{% if missing %} must evaluate to False, not raise."""
        patch_django_templates("strict")
        result = render("{% if name %}yes{% else %}no{% endif %}")
        assert result == "no"  # no UndefinedVariableError

    def test_for_tag_does_not_raise(self):
        """{% for x in missing %} must produce no iterations, not raise."""
        patch_django_templates("strict")
        result = render("{% for x in items %}{{ x }}{% endfor %}done")
        assert result == "done"

    def test_partial_context_raises_only_for_missing(self):
        """Only truly missing vars raise; present vars render normally."""
        patch_django_templates("strict")
        with pytest.raises(UndefinedVariableError):
            render("{{ greeting }} {{ name }}!", {"greeting": "Hello"})


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:

    def test_admin_style_templates_work_with_silent(self):
        """
        Simulate the Django admin relying on missing vars silently becoming ''.
        This is the primary compatibility concern.
        """
        patch_django_templates("silent")
        # Admin templates often do things like {{ cl.result_list|... }}
        # where cl might not have all attributes.
        result = render(
            "{% if opts.module_name %}{{ opts.module_name }}{% endif %}"
        )
        assert result == ""  # no crash, no output

    def test_switch_between_modes_in_tests(self):
        """Demonstrate switching modes between test runs."""
        # Strict for unit tests
        patch_django_templates("strict")
        with pytest.raises(UndefinedVariableError):
            render("{{ missing }}")

        # Silent for legacy tests
        patch_django_templates("silent")
        result = render("{{ missing }}")
        assert result == ""