"""Tests for the mechanism which counts what the suite verifies."""

import json
from pathlib import Path

import pytest
from beartype import beartype

from tests.mock_vws.verification import (
    RUNTIME_UNVERIFIED,
    UnverifiedReason,
    VuforiaAPI,
    api_for_test_path,
    marker_detail,
    marker_reason,
    mock_only,
    unverified_at_runtime,
)

pytestmark = mock_only(
    reason=UnverifiedReason.NO_VUFORIA_CLAIM,
    detail=("These cover this test suite's own record of what it verifies."),
)

_PLUGIN_CONFTEST = """\
pytest_plugins = ["tests.mock_vws.fixtures.verification"]
"""

_BACKEND_CONFTEST = (
    _PLUGIN_CONFTEST
    + '''
import pytest


@pytest.fixture(
    params=["Real Vuforia", "In Memory Mock Vuforia"],
    ids=["Real Vuforia", "In Memory Mock Vuforia"],
)
def backend(request):
    """A backend to run a test against."""
    return request.param
'''
)


@pytest.fixture(name="no_recorded_downgrades", autouse=True)
def fixture_no_recorded_downgrades() -> None:
    """Do not let these tests add to the run's recorded downgrades."""
    RUNTIME_UNVERIFIED.clear()


class TestApiForTestPath:
    """Tests for classifying a test module by the API it exercises."""

    @staticmethod
    def test_known_module() -> None:
        """A classified module gives its API."""
        api = api_for_test_path(path=Path("tests/mock_vws/test_query.py"))
        assert api == VuforiaAPI.QUERY

    @staticmethod
    def test_unknown_module() -> None:
        """An unclassified module says what to do about it."""
        with pytest.raises(expected_exception=KeyError) as exc:
            api_for_test_path(path=Path("tests/mock_vws/test_new_api.py"))

        assert "test_new_api is not listed" in str(object=exc.value)


class TestMarker:
    """Tests for reading a ``mock_only`` marker."""

    @staticmethod
    def test_reason_and_detail() -> None:
        """A marker gives back the reason and detail it was made with."""
        decorator = mock_only(
            reason=UnverifiedReason.NEVER_ATTEMPTED,
            detail="Nobody has asked Vuforia.",
        )
        mark = decorator.mark
        assert marker_reason(mark=mark) == UnverifiedReason.NEVER_ATTEMPTED
        assert marker_detail(mark=mark) == "Nobody has asked Vuforia."

    @staticmethod
    @pytest.mark.parametrize(
        argnames="kwargs",
        argvalues=[
            pytest.param({"detail": "detail"}, id="no-reason"),
            pytest.param(
                {"reason": UnverifiedReason.NEVER_ATTEMPTED},
                id="no-detail",
            ),
            pytest.param(
                {"reason": "never-attempted", "detail": "detail"},
                id="reason-is-not-a-category",
            ),
        ],
    )
    def test_invalid_marker(*, kwargs: dict[str, object]) -> None:
        """A marker without a valid reason and detail is rejected."""
        mark = pytest.mark.mock_only(**kwargs).mark
        with pytest.raises(expected_exception=TypeError) as exc:
            marker_reason(mark=mark)

        assert "takes a reason from UnverifiedReason" in str(object=exc.value)


class TestUnverifiedAtRuntime:
    """Tests for a test which gives up on verifying anything."""

    @staticmethod
    def test_records_and_stops() -> None:
        """The test is recorded, and ends as an expected failure."""
        with pytest.raises(expected_exception=pytest.xfail.Exception):
            unverified_at_runtime(
                reason=UnverifiedReason.TEMPORARILY_UNVERIFIABLE,
                detail="The allowance is spent.",
            )

        assert len(RUNTIME_UNVERIFIED) == 1
        node_id, reason, detail = RUNTIME_UNVERIFIED[0]
        assert node_id.endswith("test_records_and_stops")
        assert reason == UnverifiedReason.TEMPORARILY_UNVERIFIABLE
        assert detail == "The allowance is spent."


_REPOSITORY_ROOT = Path(__file__).parents[2]


@beartype
def _write_plugin_test(
    *,
    pytester: pytest.Pytester,
    monkeypatch: pytest.MonkeyPatch,
    conftest: str,
    source: str,
) -> None:
    """Write a test which runs with the verification plugin.

    The runs are subprocess runs, because an in-process run inherits
    this run's plugins without their options.  The repository has to be
    importable in the subprocess for the plugin to load.

    Args:
        pytester: The ``pytester`` fixture.
        monkeypatch: The ``monkeypatch`` fixture.
        conftest: The contents of the ``conftest.py`` to write.
        source: The contents of the test module to write.
    """
    monkeypatch.setenv(name="PYTHONPATH", value=str(object=_REPOSITORY_ROOT))
    pytester.makeconftest(source=conftest)
    pytester.makepyfile(test_verification=source)


class TestCollection:
    """Tests for what the plugin does at collection time."""

    @staticmethod
    def test_undeclared_test_is_an_error(
        *,
        pytester: pytest.Pytester,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A test which never reaches real Vuforia must say why."""
        _write_plugin_test(
            pytester=pytester,
            monkeypatch=monkeypatch,
            conftest=_PLUGIN_CONFTEST,
            source="def test_example():\n    pass\n",
        )

        result = pytester.runpytest_subprocess("--collect-only")

        result.stderr.fnmatch_lines(
            lines2=["*never run against the real Vuforia*"],
        )
        assert result.ret == pytest.ExitCode.USAGE_ERROR

    @staticmethod
    def test_unclassified_module_is_an_error(
        *,
        pytester: pytest.Pytester,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A test module must say which API it exercises."""
        monkeypatch.setenv(
            name="PYTHONPATH",
            value=str(object=_REPOSITORY_ROOT),
        )
        pytester.makeconftest(source=_PLUGIN_CONFTEST)
        pytester.makepyfile(
            test_a_module_which_is_not_classified=(
                "def test_example():\n    pass\n"
            ),
        )

        result = pytester.runpytest_subprocess("--collect-only")

        result.stderr.fnmatch_lines(
            lines2=["*test_a_module_which_is_not_classified.py*"],
        )
        assert result.ret == pytest.ExitCode.USAGE_ERROR

    @staticmethod
    def test_declared_test_is_counted(
        *,
        pytester: pytest.Pytester,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A declared test is counted under its reason."""
        _write_plugin_test(
            pytester=pytester,
            monkeypatch=monkeypatch,
            conftest=_PLUGIN_CONFTEST,
            source=(
                "from tests.mock_vws.verification import (\n"
                "    UnverifiedReason,\n"
                "    mock_only,\n"
                ")\n"
                "\n"
                "\n"
                "@mock_only(\n"
                "    reason=UnverifiedReason.NEVER_ATTEMPTED,\n"
                '    detail="Nobody has asked Vuforia.",\n'
                ")\n"
                "def test_example():\n"
                "    pass\n"
            ),
        )

        result = pytester.runpytest_subprocess("--collect-only")

        result.stdout.fnmatch_lines(
            lines2=["*Mock tooling: verified 0, never-attempted 1*"],
        )
        assert result.ret == pytest.ExitCode.OK

    @staticmethod
    def test_declared_test_skips_the_real_backend(
        *,
        pytester: pytest.Pytester,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A declared test does not run against real Vuforia."""
        _write_plugin_test(
            pytester=pytester,
            monkeypatch=monkeypatch,
            conftest=_BACKEND_CONFTEST,
            source=(
                "from tests.mock_vws.verification import (\n"
                "    UnverifiedReason,\n"
                "    mock_only,\n"
                ")\n"
                "\n"
                "\n"
                "@mock_only(\n"
                "    reason=UnverifiedReason.INHERENTLY_UNVERIFIABLE,\n"
                '    detail="Vuforia cannot be asked this.",\n'
                ")\n"
                "def test_example(backend):\n"
                "    assert backend != 'Real Vuforia'\n"
            ),
        )

        result = pytester.runpytest_subprocess("-v")

        result.assert_outcomes(passed=1, skipped=1)
        result.stdout.fnmatch_lines(
            lines2=["*Mock tooling: verified 0, inherently-unverifiable 1*"],
        )

    @staticmethod
    def test_test_which_reaches_real_vuforia_is_verified(
        *,
        pytester: pytest.Pytester,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A test parametrized over real Vuforia counts as verified."""
        _write_plugin_test(
            pytester=pytester,
            monkeypatch=monkeypatch,
            conftest=_BACKEND_CONFTEST,
            source="def test_example(backend):\n    assert backend\n",
        )

        result = pytester.runpytest_subprocess()

        result.assert_outcomes(passed=2)
        result.stdout.fnmatch_lines(lines2=["*Mock tooling: verified 1*"])


class TestRuntimeReporting:
    """Tests for reporting tests which stop verifying anything."""

    _SOURCE = (
        "from tests.mock_vws.verification import (\n"
        "    UnverifiedReason,\n"
        "    unverified_at_runtime,\n"
        ")\n"
        "\n"
        "\n"
        "def test_example(backend):\n"
        "    unverified_at_runtime(\n"
        "        reason=UnverifiedReason.TEMPORARILY_UNVERIFIABLE,\n"
        '        detail="The allowance is spent.",\n'
        "    )\n"
    )

    def test_reported_in_the_summary(
        self,
        *,
        pytester: pytest.Pytester,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The tests which gave up are named in the summary."""
        _write_plugin_test(
            pytester=pytester,
            monkeypatch=monkeypatch,
            conftest=_BACKEND_CONFTEST,
            source=self._SOURCE,
        )

        result = pytester.runpytest_subprocess()

        result.stdout.fnmatch_lines(
            lines2=["*stopped verifying anything while running*"],
        )
        assert result.ret == pytest.ExitCode.OK

    def test_written_to_a_report(
        self,
        *,
        pytester: pytest.Pytester,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The split and the downgrades are written as JSON."""
        _write_plugin_test(
            pytester=pytester,
            monkeypatch=monkeypatch,
            conftest=_BACKEND_CONFTEST,
            source=self._SOURCE,
        )
        report_path = pytester.path / "report.json"

        pytester.runpytest_subprocess(f"--verification-report={report_path}")

        report = json.loads(s=report_path.read_text(encoding="utf-8"))
        assert report["split"] == {"Mock tooling": {"verified": 1}}
        downgrades = report["runtime_unverified"]
        assert [downgrade["test"] for downgrade in downgrades] == [
            "test_verification.py::test_example[Real Vuforia]",
            "test_verification.py::test_example[In Memory Mock Vuforia]",
        ]
        assert {downgrade["reason"] for downgrade in downgrades} == {
            "temporarily-unverifiable",
        }
        assert {downgrade["detail"] for downgrade in downgrades} == {
            "The allowance is spent.",
        }

    def test_failing_on_downgrades(
        self,
        *,
        pytester: pytest.Pytester,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A run can be made to fail when a test gives up."""
        _write_plugin_test(
            pytester=pytester,
            monkeypatch=monkeypatch,
            conftest=_BACKEND_CONFTEST,
            source=self._SOURCE,
        )

        result = pytester.runpytest_subprocess("--fail-on-runtime-unverified")

        assert result.ret == pytest.ExitCode.TESTS_FAILED
