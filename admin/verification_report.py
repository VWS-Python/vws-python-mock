"""Report how much of the test suite verifies the mock against Vuforia.

Run this with no arguments to check ``verification.toml`` against the
suite and the documentation, or with ``--update`` to rewrite the counts
in it.

The counts matter because they move quietly.  When the Model Target
credentials were revoked, 102 tests stopped verifying anything and CI
stayed green; the split in ``verification.toml`` is the thing which
would have turned that into one visible change.
"""

import argparse
import json
import subprocess
import sys
import tempfile
import tomllib
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from beartype import beartype
from pydantic import BaseModel, ConfigDict

# The tests package holds the categories, so that the tests and this
# tool cannot disagree about them.  Run this as
# ``python -m admin.verification_report`` from the repository root, so
# that the package is importable.
from tests.mock_vws.verification import UnverifiedReason, VuforiaAPI

_REPOSITORY_ROOT = Path(__file__).parent.parent
_INVENTORY_PATH = _REPOSITORY_ROOT / "verification.toml"
_INVENTORY_DOCUMENT = (
    _REPOSITORY_ROOT / "docs" / "source" / "unverified-behavior.rst"
)
_DIFFERENCES_DOCUMENT = (
    _REPOSITORY_ROOT / "docs" / "source" / "differences-to-vws.rst"
)
_VERIFIED = "verified"
_CLAIM_ANCHOR_PREFIX = ".. _unverified-"


@beartype
def _collect_split() -> dict[str, Counter[str]]:
    """The verified and unverified split of the whole test suite.

    Returns:
        The counts for each API, from a collection-only ``pytest`` run.

    Raises:
        RuntimeError: Collecting the test suite failed.
    """
    with tempfile.TemporaryDirectory() as directory:
        report_path = Path(directory) / "verification.json"
        result = subprocess.run(  # noqa: S603
            args=[
                sys.executable,
                "-m",
                "pytest",
                "tests/",
                "--collect-only",
                "--quiet",
                "--no-header",
                f"--verification-report={report_path}",
            ],
            cwd=_REPOSITORY_ROOT,
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode != 0:
            message = (
                "Collecting the test suite failed:\n"
                f"{result.stdout}\n{result.stderr}"
            )
            raise RuntimeError(message)
        report = json.loads(s=report_path.read_text(encoding="utf-8"))

    return {api: Counter(counts) for api, counts in report["split"].items()}


class _Inventory(BaseModel):
    """The contents of ``verification.toml``."""

    model_config = ConfigDict(extra="forbid")

    counts: dict[str, dict[str, int]]


@beartype
def _inventory() -> _Inventory:
    """The recorded inventory and counts.

    Returns:
        The parsed contents of ``verification.toml``.
    """
    return _Inventory(
        **tomllib.loads(_INVENTORY_PATH.read_text(encoding="utf-8")),
    )


@beartype
def _recorded_counts(*, inventory: _Inventory) -> dict[str, Counter[str]]:
    """The counts recorded in the inventory.

    Args:
        inventory: The parsed inventory.

    Returns:
        The recorded counts for each API.
    """
    return {
        api: Counter(api_counts)
        for api, api_counts in inventory.counts.items()
    }


@beartype
def _counts_document(*, split: Mapping[str, Counter[str]]) -> str:
    """The ``counts`` section of the inventory, as TOML.

    Args:
        split: The counts to record.

    Returns:
        The TOML to write for the given counts.
    """
    keys = [_VERIFIED, *[reason.value for reason in UnverifiedReason]]
    lines = [
        "# The verified and unverified split of the test suite, per API.",
        "#",
        "# Rewrite this file with:",
        "#",
        "#     python -m admin.verification_report --update",
        "#",
        "# A change here is a change in how much of the mock is checked",
        "# against real Vuforia, so it belongs in the diff of whatever",
        "# caused it. The claims behind the unverified counts are listed",
        "# in docs/source/unverified-behavior.rst.",
        "",
    ]
    for api in VuforiaAPI:
        counts = split.get(api.value)
        if counts is None:
            continue
        lines.append(f'[counts."{api.value}"]')
        lines.extend(f'"{key}" = {counts[key]}' for key in keys if counts[key])
        lines.append("")
    return "\n".join(lines)


@beartype
def _differences(
    *,
    split: Mapping[str, Counter[str]],
    recorded: Mapping[str, Counter[str]],
) -> list[str]:
    """Descriptions of every count which has changed.

    Args:
        split: The counts which the suite has now.
        recorded: The counts which the inventory records.

    Returns:
        One description per changed count, saying which way it moved.
    """
    keys = [_VERIFIED, *[reason.value for reason in UnverifiedReason]]
    descriptions: list[str] = []
    for api in {*split, *recorded}:
        now = split.get(api, Counter())
        before = recorded.get(api, Counter())
        for key in keys:
            if now[key] == before[key]:
                continue
            wrong_way = (
                now[key] < before[key]
                if key == _VERIFIED
                else now[key] > before[key]
            )
            direction = "  <-- the wrong way" if wrong_way else ""
            descriptions.append(
                f"{api}: {key}: {before[key]} -> {now[key]}{direction}"
            )
    return sorted(descriptions)


@beartype
def _claims(*, text: str) -> dict[str, tuple[str, str]]:
    """The claims which the inventory document lists.

    Args:
        text: The text of the inventory document.

    Returns:
        The category and API which the document gives for each claim.
    """
    claims: dict[str, tuple[str, str]] = {}
    for part in str.split(text, sep=_CLAIM_ANCHOR_PREFIX)[1:]:
        identifier = str.partition(part, ":")[0]
        claims[identifier] = (
            _field(text=part, name="Category"),
            _field(text=part, name="API"),
        )
    return claims


@beartype
def _field(*, text: str, name: str) -> str:
    """The value of one field of a claim's section.

    Args:
        text: The text of the document, from the claim's anchor on.
        name: The name of the field to read.

    Returns:
        The value which the field gives, or an empty string if the claim
        does not give the field before the next claim starts.
    """
    section = str.partition(text, _CLAIM_ANCHOR_PREFIX)[0]
    marker = f":{name}: "
    if marker not in section:
        return ""
    return str.strip(str.partition(str.partition(section, marker)[2], "\n")[0])


@beartype
def _claim_problems() -> list[str]:
    """Every problem with the inventory of unverified claims.

    Returns:
        One description per problem found.
    """
    claims = _claims(text=_INVENTORY_DOCUMENT.read_text(encoding="utf-8"))
    categories = {reason.value for reason in UnverifiedReason}
    apis = {api.value for api in VuforiaAPI}
    problems = [
        f"{identifier}: {category!r} is not one of {sorted(categories)}."
        for identifier, (category, _) in claims.items()
        if category not in categories
    ]
    problems.extend(
        f"{identifier}: {api!r} is not one of {sorted(apis)}."
        for identifier, (_, api) in claims.items()
        if api not in apis
    )
    differences = _DIFFERENCES_DOCUMENT.read_text(encoding="utf-8")
    problems.extend(
        f"{reference}: {_DIFFERENCES_DOCUMENT.name} refers to it, but "
        f"{_INVENTORY_DOCUMENT.name} does not list it."
        for reference in sorted(_referenced_claims(text=differences))
        if reference not in claims
    )
    return problems


@beartype
def _referenced_claims(*, text: str) -> set[str]:
    """The claims which a document refers to.

    Args:
        text: The text of the document.

    Returns:
        The identifier of each claim which the document refers to.
    """
    marker = ":ref:`unverified-"
    return {
        str.partition(part, "`")[0] for part in str.split(text, sep=marker)[1:]
    }


@beartype
def _check(*, split: Mapping[str, Counter[str]]) -> Sequence[str]:
    """Every way in which the inventory does not match the repository.

    Args:
        split: The counts which the suite has now.

    Returns:
        One description per problem found.
    """
    inventory = _inventory()
    problems = _claim_problems()
    differences = _differences(
        split=split,
        recorded=_recorded_counts(inventory=inventory),
    )
    if differences:
        problems.extend(
            [
                "The verified and unverified split has changed:",
                *differences,
                (
                    "Record it with ``python -m admin.verification_report "
                    "--update``, and say in the change why it moved."
                ),
            ],
        )
    return problems


@beartype
def _update(*, split: Mapping[str, Counter[str]]) -> None:
    """Rewrite the counts in the inventory.

    Args:
        split: The counts to record.
    """
    _INVENTORY_PATH.write_text(
        data=_counts_document(split=split),
        encoding="utf-8",
    )


@beartype
def main() -> None:
    """Check the inventory, or update the counts in it.

    Raises:
        SystemExit: The inventory does not match the repository.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update",
        action="store_true",
        help="Rewrite the counts in the inventory rather than checking them.",
    )
    arguments = parser.parse_args()
    split = _collect_split()
    if arguments.update:
        _update(split=split)
        return

    problems = _check(split=split)
    if problems:
        raise SystemExit("\n".join(problems))


if __name__ == "__main__":
    main()
