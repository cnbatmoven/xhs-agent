from __future__ import annotations

from typing import Any, TypedDict


class JobState(TypedDict, total=False):
    job_id: str
    execution_mode: str
    description: str
    input_path: str
    output_path: str
    params: dict[str, Any]
    plan: list[str]
    current_step: str
    output: str
    csv_output: str
    source_rows: int
    selected_rows: int
    summary: dict[str, Any]
    preview: dict[str, Any]
    error: str
    logs: list[str]
    notes: list[Any]
    crawled: list[dict[str, Any]]
    results: list[Any]
