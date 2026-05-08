from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"
SOURCE_SHEET = "\u7b14\u8bb0\u660e\u7ec6"
KEY_COLUMNS = [
    "\u6e90\u8868\u884c\u53f7",
    "\u6807\u9898",
    "\u7b14\u8bb0\u94fe\u63a5",
    "\u5c01\u9762",
    "\u6587\u6848",
    "\u8bdd\u9898",
    "\u8fbe\u4eba\u6635\u79f0",
    "\u7c89\u4e1d\u91cf",
    "\u70b9\u8d5e\u6570",
    "\u6536\u85cf\u6570",
    "\u8bc4\u8bba\u6570",
    "\u5206\u4eab\u6570",
    "\u5185\u5bb9\u7c7b\u578b",
    "\u521b\u610f\u5efa\u8bae",
    "\u4eba\u7fa4\u5708\u9009\u7b56\u7565",
    "\u91c7\u96c6\u72b6\u6001",
]
VOLATILE_NUMERIC_COLUMNS = {
    "\u7c89\u4e1d\u91cf",
    "\u70b9\u8d5e\u6570",
    "\u6536\u85cf\u6570",
    "\u8bc4\u8bba\u6570",
    "\u5206\u4eab\u6570",
}


def request_json(base_url: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    if payload is None:
        with urllib.request.urlopen(url, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def find_source_workbook() -> Path:
    preferred_dir = BASE_DIR / "\u7a7a\u8c03\u5185\u5bb9\u5206\u6790"
    search_roots = [preferred_dir, BASE_DIR]
    for root in search_roots:
        if not root.exists():
            continue
        for path in root.rglob("*.xlsx"):
            if path.name.startswith("~"):
                continue
            try:
                workbook = load_workbook(path, read_only=True, data_only=True)
                if any(sheet.title == SOURCE_SHEET for sheet in workbook.worksheets):
                    return path
            except Exception:
                continue
    raise FileNotFoundError(f"No workbook with sheet {SOURCE_SHEET!r} found under {BASE_DIR}")


def read_csv(path: str) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        return columns, list(reader)


def submit_and_wait(base_url: str, payload: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    created = request_json(base_url, "/api/v1/jobs", payload)
    job_id = created["job_id"]
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        job = request_json(base_url, f"/api/v1/jobs/{job_id}")
        if job["status"] in {"succeeded", "failed"}:
            return job
        time.sleep(1)
    raise TimeoutError(f"Job {job_id} did not finish within {timeout_seconds}s")


def completion(rows: list[dict[str, str]], columns: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for column in columns:
        result[column] = sum(1 for row in rows if str(row.get(column, "")).strip())
    return result


def compare_rows(
    legacy_rows: list[dict[str, str]],
    split_rows: list[dict[str, str]],
    columns: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    diffs: list[dict[str, Any]] = []
    tolerated: list[dict[str, Any]] = []
    for row_index, (legacy_row, split_row) in enumerate(zip(legacy_rows, split_rows), start=1):
        for column in columns:
            legacy_value = str(legacy_row.get(column, ""))
            split_value = str(split_row.get(column, ""))
            if legacy_value != split_value:
                if column in VOLATILE_NUMERIC_COLUMNS and within_numeric_tolerance(legacy_value, split_value):
                    tolerated.append(
                        {
                            "row": row_index,
                            "column": column,
                            "graph_legacy": legacy_value,
                            "graph_split": split_value,
                        }
                    )
                    continue
                diffs.append(
                    {
                        "row": row_index,
                        "column": column,
                        "graph_legacy": legacy_value,
                        "graph_split": split_value,
                    }
                )
    return diffs, tolerated


def parse_number(value: str) -> float | None:
    value = str(value or "").strip().replace(",", "")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def within_numeric_tolerance(left: str, right: str) -> bool:
    left_number = parse_number(left)
    right_number = parse_number(right)
    if left_number is None or right_number is None:
        return False
    diff = abs(left_number - right_number)
    baseline = max(abs(left_number), abs(right_number), 1.0)
    return diff <= max(5.0, baseline * 0.01)


def write_report(report: dict[str, Any], report_path: Path) -> None:
    json_path = report_path.with_suffix(".json")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Execution Mode Consistency Report",
        "",
        f"- Input: `{report['input']}`",
        f"- Limit: `{report['limit']}`",
        f"- Crawl enabled: `{not report['no_crawl']}`",
        f"- Overall: `{report['overall']}`",
        "",
        "## Jobs",
        "",
    ]
    for mode, job in report["jobs"].items():
        lines.extend(
            [
                f"- {mode}: `{job['status']}`",
                f"  - job_id: `{job['job_id']}`",
                f"  - csv: `{job.get('csv_output', '')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            f"- Row count match: `{report['checks']['row_count_match']}`",
            f"- Columns match: `{report['checks']['columns_match']}`",
            f"- Key field diffs: `{len(report['key_field_diffs'])}`",
            f"- Tolerated volatile numeric diffs: `{len(report.get('tolerated_volatile_diffs', []))}`",
            "",
            "## Completion",
            "",
        ]
    )
    for column, values in report["completion_compare"].items():
        lines.append(f"- {column}: legacy `{values['graph_legacy']}`, split `{values['graph_split']}`")
    if report["key_field_diffs"]:
        lines.extend(["", "## First Diffs", ""])
        for diff in report["key_field_diffs"][:20]:
            lines.append(
                f"- row {diff['row']} `{diff['column']}`: legacy `{diff['graph_legacy']}` vs split `{diff['graph_split']}`"
            )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare graph_legacy and graph_split outputs.")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--input", default="")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--crawl", action="store_true", help="Enable real XHS crawling. Default is no-crawl.")
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9222")
    parser.add_argument("--crawl-delay", type=float, default=8.0)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--legacy-csv", default="")
    parser.add_argument("--split-csv", default="")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    input_path = Path(args.input).expanduser().resolve() if args.input else find_source_workbook()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_payload: dict[str, Any] = {
        "input": str(input_path),
        "description": f"\u5bf9\u6bd4\u6267\u884c\u6a21\u5f0f\uff0c\u524d{args.limit}\u6761",
        "limit": args.limit,
        "no_crawl": not args.crawl,
        "headless": True,
        "cdp_url": args.cdp_url if args.crawl else None,
        "crawl_delay": args.crawl_delay,
        "download_covers": args.crawl,
        "embed_covers": False,
        "crawl_pgy": False,
        "use_llm": False,
    }

    jobs: dict[str, dict[str, Any]]
    if args.legacy_csv and args.split_csv:
        jobs = {
            "graph_legacy": {
                "job_id": "existing-csv",
                "status": "succeeded",
                "csv_output": str(Path(args.legacy_csv).expanduser().resolve()),
                "output": "",
                "summary": {},
                "plan": [],
            },
            "graph_split": {
                "job_id": "existing-csv",
                "status": "succeeded",
                "csv_output": str(Path(args.split_csv).expanduser().resolve()),
                "output": "",
                "summary": {},
                "plan": [],
            },
        }
    else:
        jobs = {}
        for mode in ["graph_legacy", "graph_split"]:
            payload = {
                **base_payload,
                "execution_mode": mode,
                "output": str((OUTPUT_DIR / f"mode_compare_{stamp}_{mode}.xlsx").resolve()),
            }
            jobs[mode] = submit_and_wait(args.api, payload, timeout_seconds=args.timeout)

    legacy_job = jobs["graph_legacy"]
    split_job = jobs["graph_split"]
    if legacy_job["status"] != "succeeded" or split_job["status"] != "succeeded":
        report = {
            "overall": "failed",
            "input": str(input_path),
            "limit": args.limit,
            "no_crawl": not args.crawl,
            "jobs": jobs,
            "checks": {},
            "completion_compare": {},
            "key_field_diffs": [],
            "tolerated_volatile_diffs": [],
        }
        write_report(report, OUTPUT_DIR / f"mode_compare_report_{stamp}.md")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    legacy_columns, legacy_rows = read_csv(legacy_job["csv_output"])
    split_columns, split_rows = read_csv(split_job["csv_output"])
    shared_key_columns = [column for column in KEY_COLUMNS if column in legacy_columns and column in split_columns]
    completion_columns = [
        column
        for column in KEY_COLUMNS
        if column in legacy_columns or column in split_columns
    ]
    legacy_completion = completion(legacy_rows, completion_columns)
    split_completion = completion(split_rows, completion_columns)
    diffs, tolerated_diffs = compare_rows(legacy_rows, split_rows, shared_key_columns)
    checks = {
        "row_count_match": len(legacy_rows) == len(split_rows) == args.limit,
        "columns_match": legacy_columns == split_columns,
        "key_fields_match": not diffs,
    }
    report = {
        "overall": "passed" if all(checks.values()) else "attention",
        "input": str(input_path),
        "limit": args.limit,
        "no_crawl": not args.crawl,
        "jobs": {
            mode: {
                "job_id": job["job_id"],
                "status": job["status"],
                "csv_output": job.get("csv_output", ""),
                "output": job.get("output", ""),
                "summary": job.get("summary", {}),
                "plan": job.get("plan", []),
            }
            for mode, job in jobs.items()
        },
        "checks": checks,
        "completion_compare": {
            column: {
                "graph_legacy": legacy_completion.get(column, 0),
                "graph_split": split_completion.get(column, 0),
            }
            for column in completion_columns
        },
        "key_field_diffs": diffs[:100],
        "tolerated_volatile_diffs": tolerated_diffs[:100],
    }
    write_report(report, OUTPUT_DIR / f"mode_compare_report_{stamp}.md")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["overall"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
