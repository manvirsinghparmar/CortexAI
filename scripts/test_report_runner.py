#!/usr/bin/env python3
"""Run tests from the repository test suite and generate an HTML report."""

from __future__ import annotations

import argparse
import html
import shutil
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class TestCaseResult:
    """Single test case outcome parsed from JUnit XML."""

    classname: str
    name: str
    duration_seconds: float
    status: str
    message: str = ""
    details: str = ""


@dataclass(frozen=True)
class TestRunSummary:
    """Aggregate test run metrics."""

    total: int
    passed: int
    failed: int
    errors: int
    skipped: int
    duration_seconds: float


class PytestHtmlReportRunner:
    """Execute pytest and emit a styled HTML summary report."""

    def __init__(
        self,
        repo_root: Path | None = None,
        tests_path: str = "tests",
        reports_dir: str = "reports/test-results",
        keep_runs: int = 20,
    ) -> None:
        self.repo_root = (repo_root or Path(__file__).resolve().parents[1]).resolve()
        self.tests_path = tests_path
        self.reports_dir = (self.repo_root / reports_dir).resolve()
        self.keep_runs = max(1, keep_runs)

    def run(self, pytest_args: Sequence[str] | None = None) -> int:
        """Run pytest for configured test path and generate an HTML report."""

        normalized_args = [arg for arg in (pytest_args or []) if arg != "--"]
        started_at = datetime.now(timezone.utc)
        run_stamp = started_at.strftime("%Y%m%d-%H%M%S")
        run_dir = self.reports_dir / run_stamp
        run_dir.mkdir(parents=True, exist_ok=True)

        junit_path = run_dir / "pytest-junit.xml"
        html_path = run_dir / "pytest-report.html"
        command = [
            sys.executable,
            "-m",
            "pytest",
            self.tests_path,
            "--junitxml",
            str(junit_path),
            *normalized_args,
        ]

        print(f"[test-runner] Running: {' '.join(command)}", flush=True)
        process = subprocess.run(command, cwd=self.repo_root, check=False)

        summary, cases = self._load_results(junit_path)
        self._write_html_report(
            report_path=html_path,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            command=command,
            summary=summary,
            cases=cases,
            exit_code=process.returncode,
            junit_path=junit_path,
        )
        self._update_latest_aliases(html_path, junit_path)
        self._prune_old_runs()

        print(f"[test-runner] HTML report: {html_path}")
        print(f"[test-runner] Latest report: {self.reports_dir / 'latest-report.html'}")
        print(f"[test-runner] JUnit XML: {junit_path}")
        return process.returncode

    def _load_results(self, junit_path: Path) -> tuple[TestRunSummary, list[TestCaseResult]]:
        if not junit_path.exists():
            empty = TestRunSummary(
                total=0,
                passed=0,
                failed=0,
                errors=0,
                skipped=0,
                duration_seconds=0.0,
            )
            return empty, []

        root = ET.parse(junit_path).getroot()
        total = 0
        failed = 0
        errors = 0
        skipped = 0
        duration = 0.0

        for suite in self._iter_suite_nodes(root):
            total += self._as_int(suite.attrib.get("tests"))
            failed += self._as_int(suite.attrib.get("failures"))
            errors += self._as_int(suite.attrib.get("errors"))
            skipped += self._as_int(suite.attrib.get("skipped"))
            duration += self._as_float(suite.attrib.get("time"))

        passed = max(0, total - failed - errors - skipped)
        summary = TestRunSummary(
            total=total,
            passed=passed,
            failed=failed,
            errors=errors,
            skipped=skipped,
            duration_seconds=duration,
        )

        cases: list[TestCaseResult] = []
        for case in root.findall(".//testcase"):
            status = "passed"
            message = ""
            details = ""
            if case.find("failure") is not None:
                failure = case.find("failure")
                status = "failed"
                message = (failure.attrib.get("message", "") if failure is not None else "").strip()
                details = self._compact_text(failure.text if failure is not None else "")
            elif case.find("error") is not None:
                error = case.find("error")
                status = "error"
                message = (error.attrib.get("message", "") if error is not None else "").strip()
                details = self._compact_text(error.text if error is not None else "")
            elif case.find("skipped") is not None:
                skipped_node = case.find("skipped")
                status = "skipped"
                message = (skipped_node.attrib.get("message", "") if skipped_node is not None else "").strip()
                details = self._compact_text(skipped_node.text if skipped_node is not None else "")

            cases.append(
                TestCaseResult(
                    classname=case.attrib.get("classname", "").strip(),
                    name=case.attrib.get("name", "").strip(),
                    duration_seconds=self._as_float(case.attrib.get("time")),
                    status=status,
                    message=message,
                    details=details,
                )
            )

        priority = {"failed": 0, "error": 1, "skipped": 2, "passed": 3}
        cases.sort(key=lambda item: (priority.get(item.status, 4), item.classname, item.name))
        return summary, cases

    @staticmethod
    def _iter_suite_nodes(root: ET.Element) -> list[ET.Element]:
        if root.tag == "testsuite":
            return [root]
        if root.tag == "testsuites":
            direct = root.findall("testsuite")
            return direct if direct else root.findall(".//testsuite")
        return root.findall(".//testsuite")

    @staticmethod
    def _as_int(raw: str | None) -> int:
        try:
            return int(raw or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _as_float(raw: str | None) -> float:
        try:
            return float(raw or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _compact_text(text: str | None) -> str:
        if not text:
            return ""
        return "\n".join(line.rstrip() for line in text.strip().splitlines())

    @staticmethod
    def _status_badge(status: str) -> str:
        return f"<span class='badge badge-{status}'>{html.escape(status.upper())}</span>"

    @staticmethod
    def _display_group_name(classname: str) -> str:
        if not classname:
            return "Unclassified"
        return classname.split(".")[-1] or classname

    def _group_cases_by_class(
        self, cases: Sequence[TestCaseResult]
    ) -> list[tuple[str, list[TestCaseResult]]]:
        grouped: dict[str, list[TestCaseResult]] = defaultdict(list)
        for case in cases:
            key = case.classname or "Unclassified"
            grouped[key].append(case)

        status_priority = {"failed": 0, "error": 1, "skipped": 2, "passed": 3}

        def sort_key(item: tuple[str, list[TestCaseResult]]) -> tuple[int, int, str]:
            classname, class_cases = item
            if not class_cases:
                return (4, 0, classname.lower())
            worst = min(status_priority.get(case.status, 4) for case in class_cases)
            non_pass = sum(1 for case in class_cases if case.status != "passed")
            return (worst, -non_pass, classname.lower())

        return sorted(grouped.items(), key=sort_key)

    def _write_html_report(
        self,
        report_path: Path,
        started_at: datetime,
        finished_at: datetime,
        command: Sequence[str],
        summary: TestRunSummary,
        cases: Sequence[TestCaseResult],
        exit_code: int,
        junit_path: Path,
    ) -> None:
        pass_percentage = (summary.passed / summary.total * 100.0) if summary.total else 0.0
        grouped_cases = self._group_cases_by_class(cases)
        grouped_sections: list[str] = []

        for classname, class_cases in grouped_cases:
            class_total = len(class_cases)
            class_passed = sum(1 for case in class_cases if case.status == "passed")
            class_failed = sum(1 for case in class_cases if case.status == "failed")
            class_errors = sum(1 for case in class_cases if case.status == "error")
            class_skipped = sum(1 for case in class_cases if case.status == "skipped")
            class_duration = sum(case.duration_seconds for case in class_cases)
            open_attr = " open" if (class_failed + class_errors) > 0 else ""
            class_label = self._display_group_name(classname)

            case_rows: list[str] = []
            for case in class_cases:
                details_block = "-"
                if case.message or case.details:
                    summary_line = html.escape(case.message or "View details")
                    details_text = html.escape(case.details or case.message)
                    details_block = (
                        "<details><summary>"
                        + summary_line
                        + "</summary><pre>"
                        + details_text
                        + "</pre></details>"
                    )
                case_rows.append(
                    "<tr>"
                    f"<td>{self._status_badge(case.status)}</td>"
                    f"<td>{html.escape(case.name or '-')}</td>"
                    f"<td>{case.duration_seconds:.3f}s</td>"
                    f"<td>{details_block}</td>"
                    "</tr>"
                )

            grouped_sections.append(
                "<details class='class-section'"
                + open_attr
                + "><summary><span class='class-name'>"
                + html.escape(class_label)
                + "</span><span class='class-meta'>"
                + html.escape(classname)
                + " | total="
                + str(class_total)
                + ", pass="
                + str(class_passed)
                + ", fail="
                + str(class_failed)
                + ", error="
                + str(class_errors)
                + ", skipped="
                + str(class_skipped)
                + ", duration="
                + f"{class_duration:.2f}s"
                + "</span></summary>"
                + "<table><thead><tr><th>Status</th><th>Test</th><th>Duration</th><th>Details</th></tr></thead><tbody>"
                + "".join(case_rows)
                + "</tbody></table></details>"
            )

        if not grouped_sections:
            grouped_sections.append(
                "<div class='empty-state'>No tests discovered in the generated JUnit XML.</div>"
            )

        generated_local = finished_at.astimezone()
        generated_utc = finished_at.astimezone(timezone.utc)

        title = "Pytest HTML Report"
        report_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ font-family: 'Segoe UI', Tahoma, sans-serif; margin: 24px; background: #f7f9fc; color: #1f2937; }}
    h1 {{ margin-bottom: 8px; }}
    .meta {{ margin-bottom: 16px; color: #374151; }}
    .overview {{ display: grid; grid-template-columns: minmax(200px, 280px) 1fr; gap: 16px; align-items: stretch; margin-bottom: 20px; }}
    .chart-panel {{ background: white; border-radius: 8px; padding: 14px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08); display: flex; flex-direction: column; justify-content: center; }}
    .chart-title {{ font-size: 13px; color: #4b5563; margin-bottom: 10px; }}
    .donut-wrap {{ display: flex; align-items: center; justify-content: center; }}
    .donut {{ width: 180px; height: 180px; border-radius: 50%; background: conic-gradient(#16a34a calc(var(--pass-pct) * 1%), #ef4444 0); display: flex; align-items: center; justify-content: center; }}
    .donut-hole {{ width: 120px; height: 120px; border-radius: 50%; background: #ffffff; display: flex; flex-direction: column; align-items: center; justify-content: center; box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.08); }}
    .donut-value {{ font-size: 22px; font-weight: 700; line-height: 1; }}
    .donut-label {{ font-size: 12px; color: #6b7280; margin-top: 4px; }}
    .donut-legend {{ margin-top: 10px; display: flex; justify-content: space-between; font-size: 12px; color: #374151; }}
    .legend-pass::before {{ content: ""; display: inline-block; width: 10px; height: 10px; background: #16a34a; border-radius: 2px; margin-right: 6px; }}
    .legend-other::before {{ content: ""; display: inline-block; width: 10px; height: 10px; background: #ef4444; border-radius: 2px; margin-right: 6px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }}
    .card {{ background: white; border-radius: 8px; padding: 12px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08); }}
    .label {{ display: block; font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.03em; }}
    .value {{ font-size: 22px; font-weight: 600; }}
    .value.fail {{ color: #b91c1c; }}
    .value.pass {{ color: #166534; }}
    .value.warn {{ color: #92400e; }}
    .class-list {{ display: grid; gap: 10px; }}
    .class-section {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08); }}
    .class-section > summary {{ list-style: none; cursor: pointer; padding: 12px; border-radius: 8px; display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: baseline; }}
    .class-section > summary::-webkit-details-marker {{ display: none; }}
    .class-section > summary::before {{ content: ">"; font-size: 11px; color: #6b7280; margin-right: 4px; }}
    .class-section[open] > summary::before {{ content: "v"; }}
    .class-name {{ font-weight: 700; color: #111827; }}
    .class-meta {{ font-size: 12px; color: #6b7280; }}
    table {{ width: 100%; border-collapse: collapse; background: white; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08); }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f4f6; font-weight: 600; }}
    tr:hover td {{ background: #fafafa; }}
    .badge {{ display: inline-block; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 999px; }}
    .badge-passed {{ background: #dcfce7; color: #166534; }}
    .badge-failed {{ background: #fee2e2; color: #991b1b; }}
    .badge-error {{ background: #ffedd5; color: #9a3412; }}
    .badge-skipped {{ background: #e5e7eb; color: #374151; }}
    code {{ background: #eef2ff; padding: 2px 6px; border-radius: 4px; }}
    details pre {{ white-space: pre-wrap; margin: 8px 0 0; max-height: 240px; overflow-y: auto; }}
    .empty-state {{ background: white; border-radius: 8px; padding: 14px; color: #6b7280; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08); }}
    @media (max-width: 900px) {{ .overview {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="meta">
    <div><strong>Generated (local):</strong> {html.escape(generated_local.strftime("%Y-%m-%d %H:%M:%S %Z"))}</div>
    <div><strong>Generated (UTC):</strong> {html.escape(generated_utc.strftime("%Y-%m-%d %H:%M:%S %Z"))}</div>
    <div><strong>Started (UTC):</strong> {html.escape(started_at.isoformat())}</div>
    <div><strong>Finished (UTC):</strong> {html.escape(finished_at.isoformat())}</div>
    <div><strong>Command:</strong> <code>{html.escape(' '.join(command))}</code></div>
    <div><strong>Pytest exit code:</strong> <code>{exit_code}</code></div>
    <div><strong>JUnit XML:</strong> <code>{html.escape(str(junit_path))}</code></div>
  </div>
  <section class="overview">
    <article class="chart-panel">
      <div class="chart-title">Overall Pass Percentage</div>
      <div class="donut-wrap">
        <div class="donut" style="--pass-pct:{pass_percentage:.2f}">
          <div class="donut-hole">
            <span class="donut-value">{pass_percentage:.1f}%</span>
            <span class="donut-label">passed</span>
          </div>
        </div>
      </div>
      <div class="donut-legend">
        <span class="legend-pass">Passed: {summary.passed}</span>
        <span class="legend-other">Other: {summary.total - summary.passed}</span>
      </div>
    </article>
    <section class="cards">
      <article class="card"><span class="label">Total</span><span class="value">{summary.total}</span></article>
      <article class="card"><span class="label">Passed</span><span class="value pass">{summary.passed}</span></article>
      <article class="card"><span class="label">Failed</span><span class="value fail">{summary.failed}</span></article>
      <article class="card"><span class="label">Errors</span><span class="value fail">{summary.errors}</span></article>
      <article class="card"><span class="label">Skipped</span><span class="value warn">{summary.skipped}</span></article>
      <article class="card"><span class="label">Duration</span><span class="value">{summary.duration_seconds:.2f}s</span></article>
    </section>
  </section>
  <section class="class-list">
    {''.join(grouped_sections)}
  </section>
</body>
</html>
"""
        report_path.write_text(report_html, encoding="utf-8")

    def _update_latest_aliases(self, html_path: Path, junit_path: Path) -> None:
        latest_html = self.reports_dir / "latest-report.html"
        latest_xml = self.reports_dir / "latest-junit.xml"
        shutil.copy2(html_path, latest_html)
        if junit_path.exists():
            shutil.copy2(junit_path, latest_xml)

    def _prune_old_runs(self) -> None:
        run_dirs = [path for path in self.reports_dir.iterdir() if path.is_dir()]
        run_dirs.sort(key=lambda path: path.name, reverse=True)
        for stale in run_dirs[self.keep_runs :]:
            shutil.rmtree(stale, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run pytest for OpenAIProject/tests and build an HTML report."
    )
    parser.add_argument(
        "--tests-path",
        default="tests",
        help="Path passed to pytest as test target (default: tests).",
    )
    parser.add_argument(
        "--reports-dir",
        default="reports/test-results",
        help="Directory where timestamped run reports are stored.",
    )
    parser.add_argument(
        "--keep-runs",
        type=int,
        default=20,
        help="Number of timestamped report folders to retain (default: 20).",
    )
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional pytest args. Use '--' before pytest args.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runner = PytestHtmlReportRunner(
        tests_path=args.tests_path,
        reports_dir=args.reports_dir,
        keep_runs=args.keep_runs,
    )
    return runner.run(pytest_args=args.pytest_args)


if __name__ == "__main__":
    raise SystemExit(main())
