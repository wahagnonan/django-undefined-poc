"""
tests/test_undefined.py
~~~~~~~~~~~~~~~~~~~~~~~

Tests for the Undefined class hierarchy.

Run with:  python -m pytest tests/ -v

These tests cover the Undefined classes themselves WITHOUT requiring a
full Django setup. Integration tests with a real Django engine are in
test_integration.py (requires Django installed).
"""

import logging
import pytest
import sys
import os

# Make sure the package is importable from this directory
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from django_undefined.undefined import (
    Undefined,
    SilentUndefined,
    LoggingUndefined,
    DebugUndefined,
    StrictUndefined,
    UndefinedVariableError,
    get_undefined_class,
)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def silent():
    return SilentUndefined("user.name")

@pytest.fixture
def logging_undef():
    return LoggingUndefined("user.name", origin="mytemplate.html")

@pytest.fixture
def debug():
    return DebugUndefined("user.name")

@pytest.fixture
def strict():
    return StrictUndefined("user.name", origin="mytemplate.html")


# ===========================================================================
# SilentUndefined — backward-compatible default
# ===========================================================================

class TestSilentUndefined:

    def test_str_returns_empty_string(self, silent):
        assert str(silent) == ""

    def test_bool_is_false(self, silent):
        """{% if missing_var %} should evaluate to False."""
        assert bool(silent) is False

    def test_len_is_zero(self, silent):
        assert len(silent) == 0

    def test_iteration_is_empty(self, silent):
        """{% for x in missing_list %} should produce no iterations."""
        assert list(silent) == []

    def test_chained_attr_access_returns_undefined(self, silent):
        """user.profile.city where user is undefined should stay undefined."""
        result = silent.profile
        assert isinstance(result, SilentUndefined)
        assert result._variable_name == "user.name.profile"

    def test_item_access_returns_undefined(self, silent):
        result = silent["key"]
        assert isinstance(result, SilentUndefined)

    def test_equality_with_empty_string(self, silent):
        """Filters that compare to '' should still work."""
        assert silent == ""

    def test_format_returns_empty_string(self, silent):
        assert f"{silent}" == ""

    def test_addition_with_string(self, silent):
        assert "prefix_" + silent == "prefix_"

    def test_repr(self, silent):
        assert "SilentUndefined" in repr(silent)
        assert "user.name" in repr(silent)


# ===========================================================================
# LoggingUndefined — logs but stays silent
# ===========================================================================

class TestLoggingUndefined:

    def test_str_returns_empty_string(self, logging_undef):
        assert str(logging_undef) == ""

    def test_emits_warning_log(self, logging_undef, caplog):
        with caplog.at_level(logging.WARNING, logger="django.template"):
            result = str(logging_undef)
        assert result == ""
        assert "user.name" in caplog.text
        assert "mytemplate.html" in caplog.text

    def test_log_level_is_warning(self, logging_undef, caplog):
        with caplog.at_level(logging.WARNING, logger="django.template"):
            str(logging_undef)
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_bool_is_false(self, logging_undef):
        assert bool(logging_undef) is False

    def test_no_log_on_bool(self, logging_undef, caplog):
        """Boolean check ({% if %}) should NOT trigger a log."""
        with caplog.at_level(logging.WARNING, logger="django.template"):
            _ = bool(logging_undef)
        assert not caplog.records

    def test_no_log_on_iteration(self, logging_undef, caplog):
        """Iteration ({% for %}) should NOT trigger a log."""
        with caplog.at_level(logging.WARNING, logger="django.template"):
            _ = list(logging_undef)
        assert not caplog.records

    def test_no_origin_in_log(self, caplog):
        """Without origin info the log should still be clean."""
        u = LoggingUndefined("missing_var")
        with caplog.at_level(logging.WARNING, logger="django.template"):
            str(u)
        assert "missing_var" in caplog.text


# ===========================================================================
# DebugUndefined — visible variable name
# ===========================================================================

class TestDebugUndefined:

    def test_str_shows_variable_name(self, debug):
        assert str(debug) == "{{ user.name }}"

    def test_format_shows_variable_name(self, debug):
        assert f"{debug}" == "{{ user.name }}"

    def test_bool_is_false(self, debug):
        assert bool(debug) is False

    def test_nested_lookup_shows_full_path(self, debug):
        result = debug.address.city
        assert str(result) == "{{ user.name.address.city }}"


# ===========================================================================
# StrictUndefined — raises on render
# ===========================================================================

class TestStrictUndefined:

    def test_str_raises_error(self, strict):
        with pytest.raises(UndefinedVariableError) as exc_info:
            str(strict)
        assert "user.name" in str(exc_info.value)
        assert "mytemplate.html" in str(exc_info.value)

    def test_format_raises_error(self, strict):
        with pytest.raises(UndefinedVariableError):
            f"{strict}"

    def test_bool_does_NOT_raise(self, strict):
        """{% if missing_var %} must NOT raise — it should just be False."""
        assert bool(strict) is False  # no exception

    def test_iteration_does_NOT_raise(self, strict):
        """{% for x in missing_list %} must NOT raise."""
        assert list(strict) == []  # no exception

    def test_len_does_NOT_raise(self, strict):
        assert len(strict) == 0  # no exception

    def test_chained_access_does_NOT_raise_until_render(self, strict):
        """Attribute access should return another StrictUndefined."""
        result = strict.profile.city  # no exception yet
        assert isinstance(result, StrictUndefined)
        with pytest.raises(UndefinedVariableError):
            str(result)  # raises only at render time

    def test_error_message_without_origin(self):
        u = StrictUndefined("some_var")
        with pytest.raises(UndefinedVariableError) as exc_info:
            str(u)
        assert "some_var" in str(exc_info.value)


# ===========================================================================
# get_undefined_class registry
# ===========================================================================

class TestGetUndefinedClass:

    def test_short_key_silent(self):
        assert get_undefined_class("silent") is SilentUndefined

    def test_short_key_logging(self):
        assert get_undefined_class("logging") is LoggingUndefined

    def test_short_key_debug(self):
        assert get_undefined_class("debug") is DebugUndefined

    def test_short_key_strict(self):
        assert get_undefined_class("strict") is StrictUndefined

    def test_class_directly(self):
        assert get_undefined_class(StrictUndefined) is StrictUndefined

    def test_dotted_path(self):
        cls = get_undefined_class("django_undefined.undefined.DebugUndefined")
        assert cls is DebugUndefined

    def test_invalid_key_raises(self):
        with pytest.raises(ValueError, match="Cannot import"):
            get_undefined_class("nonexistent.module.Class")

    def test_non_undefined_class_raises(self):
        with pytest.raises((ValueError, AttributeError)):
            get_undefined_class("builtins.str")


# ===========================================================================
# Cross-class behavioural contract
# ===========================================================================

class TestUndefinedContract:
    """
    All Undefined subclasses must satisfy this shared behavioural contract
    so that Django's template engine can treat them uniformly.
    """

    CLASSES = [SilentUndefined, LoggingUndefined, DebugUndefined, StrictUndefined]

    @pytest.mark.parametrize("cls", CLASSES)
    def test_bool_is_always_false(self, cls):
        u = cls("x")
        assert bool(u) is False

    @pytest.mark.parametrize("cls", CLASSES)
    def test_len_is_always_zero(self, cls):
        u = cls("x")
        assert len(u) == 0

    @pytest.mark.parametrize("cls", CLASSES)
    def test_iteration_is_always_empty(self, cls):
        u = cls("x")
        assert list(u) == []

    @pytest.mark.parametrize("cls", CLASSES)
    def test_chained_access_returns_same_class(self, cls):
        u = cls("x")
        result = u.attr
        assert type(result) is cls

    @pytest.mark.parametrize("cls", CLASSES)
    def test_is_subclass_of_undefined(self, cls):
        assert issubclass(cls, Undefined)