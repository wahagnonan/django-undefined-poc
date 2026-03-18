"""
django_undefined.undefined
~~~~~~~~~~~~~~~~~~~~~~~~~~

Proof-of-concept: Jinja2-style Undefined types for Django's template engine.

This module introduces a configurable ``Undefined`` class hierarchy that
replaces Django's current hard-coded ``string_if_invalid`` behaviour when a
template variable cannot be resolved from the context.

Inspired by:
  - Jinja2's undefined types (https://jinja.palletsprojects.com/en/stable/api/#undefined-types)
  - Adam Johnson's suggestion on the Django Forum (March 2025)
  - Ticket #28618 (open since 2017, patch still marked "needs improvement")

Proposed location in Django core: ``django/template/undefined.py``
"""

import logging
import warnings

logger = logging.getLogger("django.template")


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class Undefined:
    """
    Base class for undefined template variables.

    When Django's template engine fails to resolve a variable from the
    context, it will return an instance of the configured ``Undefined``
    subclass instead of the current hard-coded empty string ``""``.

    Subclasses control the behaviour by overriding ``__str__`` and/or
    ``__repr__``.  All other magic methods delegate to the empty-string
    equivalent so that the object behaves naturally in template control
    flow (``{% if %}``, ``{% for %}``, filters, etc.).
    """

    def __init__(self, variable_name: str, origin: str = ""):
        """
        Parameters
        ----------
        variable_name:
            The dotted lookup path that failed, e.g. ``"user.profile.age"``.
        origin:
            The template name / file path where the failure occurred.
            Empty string when unavailable (e.g. from-string templates).
        """
        self._variable_name = variable_name
        self._origin = origin

    # ------------------------------------------------------------------
    # String protocol — subclasses override this
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        """Return the string representation rendered into the template."""
        return ""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self._variable_name!r}>"

    # ------------------------------------------------------------------
    # Boolean protocol — keeps {% if missing_var %} working as before
    # ------------------------------------------------------------------

    def __bool__(self) -> bool:
        return False

    # ------------------------------------------------------------------
    # Iteration protocol — keeps {% for x in missing_list %} safe
    # ------------------------------------------------------------------

    def __iter__(self):
        return iter([])

    def __len__(self) -> int:
        return 0

    # ------------------------------------------------------------------
    # Attribute / item access — keeps chained lookups from crashing
    #   e.g. {{ user.profile.city }} where user is undefined
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> "Undefined":
        # Avoid infinite recursion on private attributes
        if name.startswith("_"):
            raise AttributeError(name)
        return self.__class__(
            variable_name=f"{self._variable_name}.{name}",
            origin=self._origin,
        )

    def __getitem__(self, key) -> "Undefined":
        return self.__class__(
            variable_name=f"{self._variable_name}[{key!r}]",
            origin=self._origin,
        )

    # ------------------------------------------------------------------
    # Arithmetic / comparison — safe no-ops so filters don't crash
    # ------------------------------------------------------------------

    def __add__(self, other):      return ""
    def __radd__(self, other):     return other
    def __mul__(self, other):      return ""
    def __eq__(self, other):       return isinstance(other, Undefined) or other == ""
    def __lt__(self, other):       return True
    def __gt__(self, other):       return False
    def __hash__(self):            return hash(self._variable_name)

    # ------------------------------------------------------------------
    # Format protocol — so {{ var|date:"Y" }} doesn't crash
    # ------------------------------------------------------------------

    def __format__(self, format_spec: str) -> str:
        return ""


# ---------------------------------------------------------------------------
# Concrete implementations
# ---------------------------------------------------------------------------

class SilentUndefined(Undefined):
    """
    Silently returns an empty string, exactly like Django's current default.

    This is the **backward-compatible default**.  Switching to this class
    produces zero behaviour change in existing projects.

    Recommended for: production environments.
    """

    def __str__(self) -> str:
        return ""


class LoggingUndefined(Undefined):
    """
    Returns an empty string but emits a ``WARNING`` log message.

    The log record includes the variable name and template origin, making
    it easy to catch accidental omissions in staging without breaking the
    page for end users.

    Recommended for: staging / CI environments.
    """

    def __str__(self) -> str:
        origin_info = f" in template '{self._origin}'" if self._origin else ""
        logger.warning(
            "Undefined template variable %r%s",
            self._variable_name,
            origin_info,
        )
        return ""


class DebugUndefined(Undefined):
    """
    Renders the variable name visually so it stands out in the output.

    Example: ``{{ user.age }}`` renders as ``{{ user.age }}`` literally,
    making missing variables immediately visible during development without
    raising an exception.

    Recommended for: local development when you want quick visual feedback.
    """

    def __str__(self) -> str:
        return f"{{{{ {self._variable_name} }}}}"


class StrictUndefined(Undefined):
    """
    Raises ``UndefinedVariableError`` (a subclass of Django's
    ``VariableDoesNotExist``) the moment the undefined value is rendered
    or coerced to a string.

    The exception message includes the full lookup path and template origin
    so developers can pinpoint the bug immediately.

    Recommended for: development / test environments.

    Compatibility note
    ------------------
    Control-flow tags (``{% if %}``, ``{% for %}``) call ``bool()`` or
    ``len()`` on variables, not ``str()``.  Because ``__bool__`` returns
    ``False`` and ``__len__`` returns ``0`` (inherited from ``Undefined``),
    existing ``{% if missing_var %}`` guards continue to work correctly —
    they just evaluate to ``False`` instead of raising.
    """

    def __str__(self) -> str:
        origin_info = f" (in template '{self._origin}')" if self._origin else ""
        raise UndefinedVariableError(
            f"Variable '{self._variable_name}' is undefined{origin_info}. "
            f"Use SilentUndefined or DebugUndefined if you expect this "
            f"variable to sometimes be missing."
        )


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class UndefinedVariableError(Exception):
    """
    Raised by ``StrictUndefined.__str__()`` when a template variable
    cannot be resolved.

    Inherits from ``Exception`` directly in this PoC.  In the real Django
    implementation it would inherit from
    ``django.template.base.VariableDoesNotExist`` so that existing
    ``except VariableDoesNotExist`` handlers continue to work.
    """


# ---------------------------------------------------------------------------
# Registry helper
# ---------------------------------------------------------------------------

# Maps the short name used in TEMPLATES['OPTIONS'] to the class.
_REGISTRY: dict[str, type[Undefined]] = {
    "silent":  SilentUndefined,
    "logging": LoggingUndefined,
    "debug":   DebugUndefined,
    "strict":  StrictUndefined,
}


def get_undefined_class(name_or_class) -> type[Undefined]:
    """
    Resolve the ``undefined`` option from ``TEMPLATES['OPTIONS']`` to an
    actual class.

    Accepts:
    - A short string key: ``"silent"``, ``"logging"``, ``"debug"``, ``"strict"``
    - A full dotted path: ``"myapp.template_utils.CustomUndefined"``
    - A class directly (for programmatic use / tests)

    Returns the resolved ``Undefined`` subclass.

    Raises ``ValueError`` if the name is unknown or the class does not
    inherit from ``Undefined``.
    """
    if isinstance(name_or_class, type) and issubclass(name_or_class, Undefined):
        return name_or_class

    if isinstance(name_or_class, str):
        if name_or_class in _REGISTRY:
            return _REGISTRY[name_or_class]

        # Dotted import path
        try:
            module_path, class_name = name_or_class.rsplit(".", 1)
            import importlib
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
        except (ValueError, ImportError, AttributeError) as exc:
            raise ValueError(
                f"Cannot import undefined class {name_or_class!r}: {exc}"
            ) from exc

        if not (isinstance(cls, type) and issubclass(cls, Undefined)):
            raise ValueError(
                f"{name_or_class!r} must be a subclass of "
                f"django.template.undefined.Undefined"
            )
        return cls

    raise ValueError(
        f"Expected a string or Undefined subclass, got {type(name_or_class)!r}"
    )