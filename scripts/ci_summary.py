"""Turn pytest JUnit XML and coverage (Cobertura) XML into a Markdown CI summary.

Used by the CI workflows to show results on the run page instead of only in logs:

    python scripts/ci_summary.py --junit test-results.xml >> "$GITHUB_STEP_SUMMARY"
    python scripts/ci_summary.py --coverage coverage.xml --threshold 80 >> "$GITHUB_STEP_SUMMARY"

Only the standard library is used, so the script runs before or without project dependencies.
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestResults:
    total: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    time: float = 0.0
    failed_tests: list[str] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return self.total - self.failures - self.errors - self.skipped

    @property
    def ok(self) -> bool:
        return self.failures == 0 and self.errors == 0


@dataclass
class FileCoverage:
    filename: str
    percent: float


@dataclass
class CoverageResults:
    percent: float
    files: list[FileCoverage]


def parse_junit(path: Path) -> TestResults:
    """Read totals and failing test names from a pytest JUnit XML report."""
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    results = TestResults()
    for suite in suites:
        results.total += int(suite.get("tests", 0))
        results.failures += int(suite.get("failures", 0))
        results.errors += int(suite.get("errors", 0))
        results.skipped += int(suite.get("skipped", 0))
        results.time += float(suite.get("time", 0.0))
        for case in suite.iter("testcase"):
            if case.find("failure") is not None or case.find("error") is not None:
                results.failed_tests.append(f"{case.get('classname', '')}::{case.get('name', '')}")
    return results


def _rate(lines_covered: int, lines_valid: int, branches_covered: int, branches_valid: int) -> float:
    """Combined line + branch coverage, the same number pytest-cov reports as TOTAL."""
    valid = lines_valid + branches_valid
    return 100.0 if valid == 0 else 100.0 * (lines_covered + branches_covered) / valid


def parse_coverage(path: Path) -> CoverageResults:
    """Read total and per-file coverage from a Cobertura XML report."""
    root = ET.parse(path).getroot()
    total = _rate(
        int(root.get("lines-covered", 0)),
        int(root.get("lines-valid", 0)),
        int(root.get("branches-covered", 0)),
        int(root.get("branches-valid", 0)),
    )
    files = []
    for cls in root.iter("class"):
        lines = cls.findall("lines/line")
        covered = sum(1 for line in lines if int(line.get("hits", 0)) > 0)
        branch_valid = branch_covered = 0
        for line in lines:
            condition = line.get("condition-coverage")  # e.g. "50% (1/2)"
            if condition and "(" in condition:
                done, all_ = condition.split("(")[1].rstrip(")").split("/")
                branch_covered += int(done)
                branch_valid += int(all_)
        if lines:
            files.append(
                FileCoverage(cls.get("filename", "?"), _rate(covered, len(lines), branch_covered, branch_valid))
            )
    files.sort(key=lambda f: (f.percent, f.filename))
    return CoverageResults(total, files)


def render_tests(results: TestResults) -> str:
    icon = "✅" if results.ok else "❌"
    out = [
        f"## {icon} Unit tests: {'passed' if results.ok else 'FAILED'}",
        "",
        "| Total | Passed | Failed | Errors | Skipped | Time |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {results.total} | {results.passed} | {results.failures} | {results.errors} "
        f"| {results.skipped} | {results.time:.1f} s |",
    ]
    if results.failed_tests:
        out += ["", "**Failed tests:**", ""] + [f"- `{name}`" for name in results.failed_tests]
    return "\n".join(out) + "\n"


def render_coverage(results: CoverageResults, threshold: float | None = None) -> str:
    ok = threshold is None or results.percent >= threshold
    icon = "✅" if ok else "❌"
    limit = f" (minimum {threshold:.0f} %)" if threshold is not None else ""
    out = [
        f"## {icon} Coverage: {results.percent:.1f} %{limit}",
        "",
        "| File | Coverage |",
        "| :--- | ---: |",
    ]
    out += [f"| `app/{f.filename}` | {f.percent:.1f} % |" for f in results.files]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--junit", type=Path, help="pytest JUnit XML report")
    parser.add_argument("--coverage", type=Path, help="Cobertura coverage XML report")
    parser.add_argument("--threshold", type=float, help="minimum coverage percent shown in the summary")
    args = parser.parse_args(argv)
    if not args.junit and not args.coverage:
        parser.error("give --junit and/or --coverage")

    parts = []
    for path, parse, render in (
        (args.junit, parse_junit, render_tests),
        (args.coverage, parse_coverage, lambda r: render_coverage(r, args.threshold)),
    ):
        if path is None:
            continue
        if not path.is_file():
            parts.append(f"> ⚠️ Report `{path}` was not produced; see the job log.\n")
            continue
        parts.append(render(parse(path)))
    sys.stdout.write("\n".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
