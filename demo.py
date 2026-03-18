"""
demo.py
~~~~~~~

Quick demo of the 4 Undefined classes WITHOUT requiring Django.

Run with: python demo.py

Shows how each class behaves when a template variable is missing.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from django_undefined.undefined import (
    SilentUndefined,
    LoggingUndefined,
    DebugUndefined,
    StrictUndefined,
    UndefinedVariableError,
)

LINE = "─" * 55


def demo_class(cls, label, description):
    print(f"\n{LINE}")
    print(f"  {label}")
    print(f"  {description}")
    print(LINE)

    u = cls("user.name", origin="profile.html")

    # Rendering (str)
    if cls is StrictUndefined:
        try:
            rendered = str(u)
        except UndefinedVariableError as e:
            rendered = f"[RAISES] {e}"
    else:
        rendered = str(u)

    print(f"  str(u)          → {rendered!r}")
    bool_val = bool(u)
    len_val = len(u)
    list_val = list(u)
    print(f"  bool(u)         → {bool_val!r}   ({'{%'} if u {'%}'} safe)")
    print(f"  len(u)          → {len_val!r}     ({'{%'} for {'%}'} safe)")
    print(f"  list(u)         → {list_val!r}  ({'{%'} for {'%}'} safe)")

    # Chained access
    child = u.address
    print(f"  u.address       → {type(child).__name__}({child._variable_name!r})")

    if cls is StrictUndefined:
        try:
            _ = str(child)
        except UndefinedVariableError as e:
            print(f"  str(u.address)  → [RAISES] {type(e).__name__}")
    else:
        print(f"  str(u.address)  → {str(child)!r}")


if __name__ == "__main__":
    print("\n" + "═" * 55)
    print("  django-undefined — GSoC 2026 PoC")
    print("  Jinja2-style Undefined types for Django templates")
    print("═" * 55)

    demo_class(
        SilentUndefined,
        "1. SilentUndefined  (default, backward-compatible)",
        "Returns '' — identical to current Django behaviour."
    )

    demo_class(
        DebugUndefined,
        "2. DebugUndefined",
        "Renders the variable name visually for quick inspection."
    )

    demo_class(
        LoggingUndefined,
        "3. LoggingUndefined  (check your terminal for WARNING)",
        "Returns '' but emits a WARNING log with the variable name."
    )

    demo_class(
        StrictUndefined,
        "4. StrictUndefined",
        "Raises UndefinedVariableError on render. Safe for if/for."
    )

    print(f"\n{LINE}")
    print("  Key insight:")
    print("  ALL classes have bool()=False and len()=0")
    print("  → {% if missing %} and {% for x in missing %} always safe")
    print("  Only str() / rendering differs between classes")
    print(LINE + "\n")