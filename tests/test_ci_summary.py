"""Unit tests for scripts/ci_summary.py (CI result summaries)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import ci_summary  # noqa: E402

JUNIT_PASSING = """<?xml version="1.0" encoding="utf-8"?>
<testsuites name="pytest tests"><testsuite name="pytest" errors="0" failures="0" skipped="2" tests="10" time="3.25">
<testcase classname="tests.test_a" name="test_ok" time="0.1"/>
</testsuite></testsuites>"""

JUNIT_FAILING = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" errors="1" failures="1" skipped="0" tests="5" time="1.0">
<testcase classname="tests.test_a" name="test_ok" time="0.1"/>
<testcase classname="tests.test_b" name="test_price" time="0.1"><failure message="assert 1 == 2"/></testcase>
<testcase classname="tests.test_c" name="test_db" time="0.1"><error message="boom"/></testcase>
</testsuite></testsuites>"""

COVERAGE = """<?xml version="1.0" ?>
<coverage lines-valid="10" lines-covered="8" branches-valid="4" branches-covered="2" line-rate="0.8" branch-rate="0.5">
<packages><package name="."><classes>
<class name="a.py" filename="a.py"><methods/><lines>
  <line number="1" hits="1"/><line number="2" hits="1"/><line number="3" hits="0"/>
  <line number="4" hits="1" branch="true" condition-coverage="50% (1/2)"/>
</lines></class>
<class name="b.py" filename="services/b.py"><methods/><lines><line number="1" hits="1"/></lines></class>
<class name="__init__.py" filename="__init__.py"><methods/><lines/></class>
</classes></package></packages></coverage>"""


@pytest.fixture
def write(tmp_path: Path):
    def _write(name: str, content: str) -> Path:
        path = tmp_path / name
        path.write_text(content, encoding="utf-8")
        return path

    return _write


def test_parse_junit_passing(write) -> None:
    results = ci_summary.parse_junit(write("j.xml", JUNIT_PASSING))

    assert (results.total, results.passed, results.skipped, results.ok) == (10, 8, 2, True)


def test_parse_junit_failing_lists_failed_tests(write) -> None:
    results = ci_summary.parse_junit(write("j.xml", JUNIT_FAILING))

    assert results.ok is False
    assert results.passed == 3
    assert results.failed_tests == ["tests.test_b::test_price", "tests.test_c::test_db"]


def test_render_tests_shows_status_and_failures(write) -> None:
    passing = ci_summary.render_tests(ci_summary.parse_junit(write("p.xml", JUNIT_PASSING)))
    failing = ci_summary.render_tests(ci_summary.parse_junit(write("f.xml", JUNIT_FAILING)))

    assert "✅ Unit tests: passed" in passing
    assert "| 10 | 8 | 0 | 0 | 2 | 3.2 s |" in passing
    assert "❌ Unit tests: FAILED" in failing
    assert "`tests.test_b::test_price`" in failing


def test_parse_coverage_matches_pytest_cov_total(write) -> None:
    results = ci_summary.parse_coverage(write("c.xml", COVERAGE))

    assert results.percent == pytest.approx(100 * (8 + 2) / (10 + 4))
    assert [f.filename for f in results.files] == ["a.py", "services/b.py"]  # lowest first, empty files skipped
    assert results.files[0].percent == pytest.approx(100 * (3 + 1) / (4 + 2))


def test_render_coverage_threshold(write) -> None:
    results = ci_summary.parse_coverage(write("c.xml", COVERAGE))

    assert "✅ Coverage: 71.4 % (minimum 70 %)" in ci_summary.render_coverage(results, 70)
    assert "❌ Coverage: 71.4 % (minimum 80 %)" in ci_summary.render_coverage(results, 80)
    assert "| `app/services/b.py` | 100.0 % |" in ci_summary.render_coverage(results)


def test_main_reports_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert ci_summary.main(["--junit", str(tmp_path / "missing.xml")]) == 0
    assert "was not produced" in capsys.readouterr().out


def test_main_requires_a_report() -> None:
    with pytest.raises(SystemExit):
        ci_summary.main([])
