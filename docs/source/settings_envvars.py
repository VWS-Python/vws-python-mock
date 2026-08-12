"""A Sphinx extension which documents pydantic settings as environment
variables.

``pydantic-settings`` derives an environment variable from each field of
a settings class. Generating the documentation from those classes means
that the two cannot drift, in the same way that ``autoflask`` generates
the endpoint documentation from the applications themselves.

This provides:

* A ``pydantic-envvars`` directive which documents either the required
  or the optional environment variables as ``envvar`` entries.
* A ``|env-<variable-name>|`` substitution per environment variable, so
  that example commands use generated names too.

Configure it with ``pydantic_envvars_settings``, which maps a
description of what reads a settings class to that class as
``module:name``, and ``pydantic_envvars_undocumented``, which lists
fields to leave undocumented.

This knows nothing about any particular application, so that it can move
to a package of its own.
"""

import importlib
import re
import textwrap
from enum import StrEnum

from docutils import nodes
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings
from sphinx.application import Sphinx
from sphinx.config import Config
from sphinx.errors import ExtensionError
from sphinx.util.docutils import SphinxDirective
from sphinx.util.typing import ExtensionMetadata

# The prefix of the substitution which each environment variable name is
# available under.
_SUBSTITUTION_PREFIX = "env-"
_SUBSTITUTION_PATTERN = re.compile(
    pattern=rf"\|{_SUBSTITUTION_PREFIX}[a-z0-9-]+\|",
)

_REQUIRED = "required"
_OPTIONAL = "optional"


class _EnvironmentVariable:
    """An environment variable which one or more settings classes read."""

    def __init__(
        self,
        *,
        field_name: str,
        field: FieldInfo,
        description: str,
    ) -> None:
        """
        Args:
            field_name: The name of the settings field.
            field: The settings field.
            description: The description of the setting.
        """
        self.name = field_name.upper()
        self.field = field
        self.description = description
        self.read_by: list[str] = []

    @property
    def is_required(self) -> bool:
        """Whether the setting has no default."""
        return self.field.is_required()

    @property
    def default(self) -> str:
        """The default value, as it is shown in the documentation."""
        default = self.field.default
        if isinstance(default, StrEnum):
            return default.value
        return str(object=default)

    @property
    def read_by_sentence(self) -> str:
        """A sentence naming what reads this environment variable."""
        *first, last = self.read_by
        names = f"{', '.join(first)} and {last}" if first else last
        return f"Read by {names}."

    @property
    def substitution(self) -> str:
        """The substitution which this variable's name is available
        under.
        """
        name = self.name.lower().replace("_", "-")
        return f"|{_SUBSTITUTION_PREFIX}{name}|"


def _settings_class(*, target: str) -> type[BaseSettings]:
    """Return the settings class which the given ``module:name`` target
    names.

    Raises:
        ExtensionError: The target does not name a settings class.
    """
    module_name, class_name = target.split(sep=":", maxsplit=1)
    module = importlib.import_module(name=module_name)
    settings_class = vars(module).get(class_name)
    if not isinstance(settings_class, type) or not issubclass(
        settings_class,
        BaseSettings,
    ):
        msg = (
            f"'{target}' in pydantic_envvars_settings does not name a "
            "pydantic-settings class."
        )
        raise ExtensionError(message=msg)
    return settings_class


def _environment_variables(*, config: Config) -> list[_EnvironmentVariable]:
    """Return every environment variable to document.

    Raises:
        ExtensionError: A setting has no description and is not listed in
            ``pydantic_envvars_undocumented``, or two settings classes
            describe one environment variable differently.
    """
    settings_targets: dict[str, str] = config.pydantic_envvars_settings
    undocumented: list[str] = config.pydantic_envvars_undocumented

    variables: dict[str, _EnvironmentVariable] = {}
    for read_by, target in settings_targets.items():
        settings_class = _settings_class(target=target)
        fields: dict[str, FieldInfo] = dict(settings_class.model_fields)
        for field_name, field in fields.items():
            if field_name in undocumented:
                continue
            if field.description is None:
                msg = (
                    f"{settings_class.__name__}.{field_name} has no "
                    "description, so it cannot be documented. Give it a "
                    "``Field(description=...)``, or add it to "
                    "``pydantic_envvars_undocumented``."
                )
                raise ExtensionError(message=msg)
            variable = variables.setdefault(
                field_name,
                _EnvironmentVariable(
                    field_name=field_name,
                    field=field,
                    description=field.description,
                ),
            )
            if variable.description != field.description:
                msg = (
                    f"{field_name.upper()} is described differently by "
                    f"{settings_class.__name__} and another settings class. "
                    "Share one description between them."
                )
                raise ExtensionError(message=msg)
            variable.read_by.append(read_by)
    return list(variables.values())


class _PydanticEnvVarsDirective(SphinxDirective):
    """Document environment variables which pydantic settings classes read."""

    required_arguments = 1

    def run(self) -> list[nodes.Node]:
        """Return the documentation for the matching environment variables.

        Returns:
            Nodes documenting either the required or the optional
            environment variables.

        Raises:
            ExtensionError: The directive's argument is neither
                ``required`` nor ``optional``.
        """
        (requirement,) = self.arguments
        if requirement not in {_REQUIRED, _OPTIONAL}:
            msg = (
                f"{self.get_location()}: the pydantic-envvars directive "
                f"takes '{_REQUIRED}' or '{_OPTIONAL}', not '{requirement}'."
            )
            raise ExtensionError(message=msg)

        blocks: list[str] = []
        for variable in _environment_variables(config=self.config):
            if variable.is_required != (requirement == _REQUIRED):
                continue
            body = f"{variable.description}\n{variable.read_by_sentence}\n"
            if not variable.is_required:
                body += f"\nDefault: ``{variable.default}``\n"
            blocks.append(
                f".. envvar:: {variable.name}\n\n"
                + textwrap.indent(text=body, prefix="   "),
            )

        return self.parse_text_to_nodes("\n".join(blocks))


def _add_environment_variable_substitutions(
    _app: Sphinx,
    config: Config,
) -> None:
    """Define a substitution for each environment variable name.

    ``|env-target-manager-base-url|`` in the documentation becomes
    ``TARGET_MANAGER_BASE_URL``, so example commands cannot name a
    variable which no settings class reads.
    """
    substitutions = "\n".join(
        f".. {variable.substitution} replace:: {variable.name}"
        for variable in _environment_variables(config=config)
    )
    config.rst_prolog = f"{config.rst_prolog or ''}\n{substitutions}\n"


def _check_environment_variable_substitutions(
    app: Sphinx,
    docname: str,
    source: list[str],
) -> None:
    """Reject a reference to an environment variable which does not exist.

    ``sphinx-substitution-extensions`` leaves an undefined substitution
    in a code block as it is rather than reporting it, so a renamed
    setting would otherwise reach the rendered page as literal
    ``|env-...|`` text.

    Raises:
        ExtensionError: The document uses a ``|env-...|`` substitution
            which no settings class defines.
    """
    known = {
        variable.substitution
        for variable in _environment_variables(config=app.config)
    }
    used = set(_SUBSTITUTION_PATTERN.findall(string="\n".join(source)))
    unknown = sorted(used - known)
    if unknown:
        msg = (
            f"{docname}: {', '.join(unknown)} "
            "names an environment variable which nothing reads."
        )
        raise ExtensionError(message=msg)


def setup(app: Sphinx) -> ExtensionMetadata:
    """Register the configuration values, the directive and the
    substitutions.

    Args:
        app: The Sphinx application.

    Returns:
        Metadata for Sphinx.
    """
    app.add_config_value(
        name="pydantic_envvars_settings",
        default={},
        rebuild="env",
        types=frozenset({dict}),
        description=(
            "A map of a description of what reads a pydantic settings "
            "class to that class, as ``module:name``."
        ),
    )
    app.add_config_value(
        name="pydantic_envvars_undocumented",
        default=[],
        rebuild="env",
        types=frozenset({list}),
        description="Settings fields to leave undocumented.",
    )
    app.add_directive(name="pydantic-envvars", cls=_PydanticEnvVarsDirective)
    app.connect(
        event="config-inited",
        callback=_add_environment_variable_substitutions,
    )
    app.connect(
        event="source-read",
        callback=_check_environment_variable_substitutions,
    )
    return {"parallel_read_safe": True, "parallel_write_safe": True}
