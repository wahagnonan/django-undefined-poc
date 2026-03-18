"""
run_tests.py
~~~~~~~~~~~~

Tests autonomes des classes Undefined — pas de pytest requis.
Utilise uniquement la bibliothèque standard Python.

Run: python run_tests.py
"""

import sys
import os
import logging
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from django_undefined.undefined import (
    Undefined,
    SilentUndefined,
    LoggingUndefined,
    DebugUndefined,
    StrictUndefined,
    UndefinedVariableError,
    get_undefined_class,
)

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
passed = failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        print(f"  {PASS}  {label}")
        passed += 1
    else:
        print(f"  {FAIL}  {label}  ← FAILED")
        failed += 1


def section(title):
    print(f"\n── {title} {'─' * (50 - len(title))}")


# ---------------------------------------------------------------------------
section("SilentUndefined")
u = SilentUndefined("user.name")
check("str() == ''",             str(u) == "")
check("bool() is False",         bool(u) is False)
check("len() == 0",              len(u) == 0)
check("list() == []",            list(u) == [])
check("chained attr → same cls", isinstance(u.profile, SilentUndefined))
check("chained key → same cls",  isinstance(u["key"], SilentUndefined))
check("== '' is True",           u == "")
check("format() == ''",          f"{u}" == "")
check("'x' + u == 'x'",         "x" + u == "x")

# ---------------------------------------------------------------------------
section("DebugUndefined")
u = DebugUndefined("user.name")
check("str() == '{{ user.name }}'", str(u) == "{{ user.name }}")
check("bool() is False",            bool(u) is False)
check("len() == 0",                 len(u) == 0)
check("chained attr shows path",    "user.name.address" in str(u.address))

# ---------------------------------------------------------------------------
section("LoggingUndefined")
u = LoggingUndefined("user.name", origin="page.html")

# Capture log output
log_records = []
handler = logging.handlers_list = []

class CaptureHandler(logging.Handler):
    def emit(self, record):
        log_records.append(record)

capture = CaptureHandler()
djlog = logging.getLogger("django.template")
djlog.addHandler(capture)
djlog.setLevel(logging.WARNING)

str(u)  # triggers log

djlog.removeHandler(capture)

check("str() == ''",               str(u) == "")
check("bool() is False",           bool(u) is False)
check("emits WARNING log",         len(log_records) >= 1)
check("log contains var name",     any("user.name" in r.getMessage() for r in log_records))
check("log contains origin",       any("page.html" in r.getMessage() for r in log_records))

log_records.clear()
_ = bool(u)
check("bool() does NOT log",       len(log_records) == 0)

log_records.clear()
_ = list(u)
check("list() does NOT log",       len(log_records) == 0)

# ---------------------------------------------------------------------------
section("StrictUndefined")
u = StrictUndefined("user.name", origin="page.html")

raised = False
msg = ""
try:
    str(u)
except UndefinedVariableError as e:
    raised = True
    msg = str(e)

check("str() raises UndefinedVariableError", raised)
check("error msg contains var name",         "user.name" in msg)
check("error msg contains origin",           "page.html" in msg)
check("bool() does NOT raise",               bool(u) is False)
check("len() does NOT raise",                len(u) == 0)
check("list() does NOT raise",               list(u) == [])

child = u.address
check("chained attr → StrictUndefined",      isinstance(child, StrictUndefined))

child_raised = False
try:
    str(child)
except UndefinedVariableError:
    child_raised = True
check("chained attr raises on render",       child_raised)

# ---------------------------------------------------------------------------
section("get_undefined_class registry")
check('"silent" → SilentUndefined',   get_undefined_class("silent") is SilentUndefined)
check('"logging" → LoggingUndefined', get_undefined_class("logging") is LoggingUndefined)
check('"debug" → DebugUndefined',     get_undefined_class("debug") is DebugUndefined)
check('"strict" → StrictUndefined',   get_undefined_class("strict") is StrictUndefined)
check('class directly → itself',      get_undefined_class(DebugUndefined) is DebugUndefined)
check('dotted path works',
      get_undefined_class("django_undefined.undefined.DebugUndefined") is DebugUndefined)

raised_val = False
try:
    get_undefined_class("unknown.module.Cls")
except ValueError:
    raised_val = True
check("unknown path raises ValueError", raised_val)

# ---------------------------------------------------------------------------
section("Shared behavioural contract")
ALL = [SilentUndefined, LoggingUndefined, DebugUndefined, StrictUndefined]
for cls in ALL:
    u = cls("x")
    check(f"{cls.__name__}: bool() is False",       bool(u) is False)
    check(f"{cls.__name__}: len() == 0",            len(u) == 0)
    check(f"{cls.__name__}: list() == []",          list(u) == [])
    check(f"{cls.__name__}: is Undefined subclass", issubclass(cls, Undefined))
    check(f"{cls.__name__}: chained → same cls",    type(u.attr) is cls)

# ---------------------------------------------------------------------------
print(f"\n{'═' * 55}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"{'═' * 55}\n")
sys.exit(0 if failed == 0 else 1)