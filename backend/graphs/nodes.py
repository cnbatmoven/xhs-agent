from __future__ import annotations

import csv
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from xhs_note_agent import run

from backend.plugins import run_plugin
from .state import JobState


def _log(state: JobState, message: str) -> list[str]:
    return [*state.get("logs", []), message]


def _bool_from_desc(description: str, words: list[str]) -> bool:
    lowered = description.lower()
    return any(word.lower() in lowered for word in words)


def _extract_limit(description: str, fallback: int) -> int:
    patterns = [
        r"前\s*(\d+)\s*条",
        r"limit\s*(\d+)",
        r"top\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, description, flags=re.I)
        if match:
            return int(match.group(1))
    return fallback


def summarize_csv_file(csv_path: Path) -> dict[str, Any]:
    if not csv_path.exists():
        return {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {"rows": 0}

    def value(row: dict[str, str], names: list[str]) -> str:
        for name in names:
            if row.get(name):
                return str(row[name])
        return ""

    def count(names: list[str], predicate) -> int:
        return sum(1 for row in rows if predicate(value(row, names)))

    return {
        "rows": len(rows),
        "status_ok": count(["采集状态"], lambda v: v == "ok"),
        "status_missing": count(["采集状态"], lambda v: v == "missing"),
        "status_failed": count(["采集状态"], lambda v: v == "failed"),
        "llm_ok": count(["LLM状态"], lambda v: v == "ok"),
        "has_copywriting": count(["文案"], lambda v: bool(v.strip())),
        "has_fans_count": count(["粉丝量"], lambda v: bool(v.strip())),
        "has_top_comments": count(["评论区前20条"], lambda v: bool(v.strip())),
        "has_pgy_image_price": count(["蒲公英图文报价"], lambda v: bool(v.strip())),
        "has_pgy_video_price": count(["蒲公英视频报价"], lambda v: bool(v.strip())),
        "has_image_cpe": count(["图文CPE"], lambda v: bool(v.strip())),
        "has_video_cpe": count(["视频CPE"], lambda v: bool(v.strip())),
    }


def csv_preview_file(csv_path: Path, limit: int = 50) -> dict[str, Any]:
    if not csv_path.exists():
        return {"columns": [], "rows": [], "total_previewed": 0}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        rows = []
        for idx, row in enumerate(reader):
            if idx >= limit:
                break
            rows.append({key: row.get(key, "") for key in columns})
    return {"columns": columns, "rows": rows, "total_previewed": len(rows)}


def parse_intent_node(state: JobState) -> JobState:
    description = state.get("description", "")
    params = dict(state.get("params", {}))
    params["limit"] = _extract_limit(description, int(params.get("limit") or 0))
    if _bool_from_desc(description, ["慢速", "慢一点", "安全", "风控"]):
        params["crawl_delay"] = max(float(params.get("crawl_delay") or 0), 10)
    if _bool_from_desc(description, ["蒲公英", "报价", "cpe"]):
        params["crawl_pgy"] = True
        params["pgy_safe_mode"] = True
        params["pgy_delay"] = max(float(params.get("pgy_delay") or 0), 12)
    if _bool_from_desc(description, ["llm", "deepseek", "创意建议", "人群", "策略", "丰富分析"]):
        params["use_llm"] = True
    if _bool_from_desc(description, ["离线", "不抓", "不重新抓"]):
        params["no_crawl"] = True
    return {
        **state,
        "params": params,
        "current_step": "parse_intent",
        "logs": _log(state, "parse_intent: generated execution parameters"),
    }


def plan_steps_node(state: JobState) -> JobState:
    params = state.get("params", {})
    plan = ["validate_input", "load_notes"]
    split_mode = state.get("execution_mode") == "graph_split"
    if split_mode:
        plan.append("crawl_xhs")
        plan.append("analyze_rules")
    elif params.get("no_crawl"):
        plan.append("offline_analysis")
    else:
        plan.append("crawl_xhs")
    if params.get("crawl_pgy"):
        plan.append("crawl_pgy")
    if params.get("use_llm"):
        plan.append("llm_analyze")
    plan.extend(["write_outputs", "summarize", "preview"])
    return {
        **state,
        "plan": plan,
        "current_step": "plan_steps",
        "logs": _log(state, f"plan_steps: {' -> '.join(plan)}"),
    }


def validate_input_node(state: JobState) -> JobState:
    input_path = Path(state["input_path"])
    if not input_path.exists():
        raise FileNotFoundError(f"input file not found: {input_path}")
    output_path = Path(state["output_path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return {
        **state,
        "current_step": "validate_input",
        "logs": _log(state, f"validate_input: {input_path}"),
    }


def load_notes_node(state: JobState) -> JobState:
    limit = int(state.get("params", {}).get("limit") or 0)
    result = run_plugin("xhs.load_notes", {"input_path": state["input_path"], "limit": limit})
    return {
        **state,
        "notes": result["notes"],
        "source_rows": result["source_rows"],
        "selected_rows": result["selected_rows"],
        "current_step": "load_notes",
        "logs": _log(state, f"load_notes: {result['selected_rows']}/{result['source_rows']} rows selected"),
    }


def crawl_xhs_node(state: JobState) -> JobState:
    result = run_plugin(
        "xhs.crawl_notes",
        {
            "notes": state.get("notes", []),
            "params": state.get("params", {}),
            "output_path": state["output_path"],
        },
    )
    crawled = result["crawled"]
    return {
        **state,
        "crawled": crawled,
        "current_step": "crawl_xhs",
        "logs": _log(state, f"crawl_xhs: {len(crawled)} records"),
    }


def analyze_rules_node(state: JobState) -> JobState:
    result = run_plugin(
        "xhs.rule_analysis",
        {
            "notes": state.get("notes", []),
            "crawled": state.get("crawled", []),
        },
    )
    results = result["results"]
    return {
        **state,
        "results": results,
        "current_step": "analyze_rules",
        "logs": _log(state, f"analyze_rules: {len(results)} results"),
    }


def crawl_pgy_node(state: JobState) -> JobState:
    result = run_plugin(
        "pgy.pricing",
        {
            "results": state.get("results", []),
            "params": state.get("params", {}),
        },
    )
    results = result["results"]
    if result.get("skipped"):
        return {
            **state,
            "results": results,
            "current_step": "crawl_pgy",
            "logs": _log(state, "crawl_pgy: skipped"),
        }
    return {
        **state,
        "results": results,
        "current_step": "crawl_pgy",
        "logs": _log(state, f"crawl_pgy: {len(results)} results"),
    }


def llm_analyze_node(state: JobState) -> JobState:
    result = run_plugin(
        "llm.openai_compatible",
        {
            "results": state.get("results", []),
            "params": state.get("params", {}),
        },
    )
    results = result["results"]
    if result.get("skipped"):
        return {
            **state,
            "results": results,
            "current_step": "llm_analyze",
            "logs": _log(state, "llm_analyze: skipped"),
        }
    return {
        **state,
        "results": results,
        "current_step": "llm_analyze",
        "logs": _log(state, f"llm_analyze: {len(results)} results"),
    }


def write_outputs_node(state: JobState) -> JobState:
    result = run_plugin(
        "xhs.write_outputs",
        {
            "results": state.get("results", []),
            "output_path": state["output_path"],
            "params": state.get("params", {}),
        },
    )
    return {
        **state,
        "output": result["output"],
        "csv_output": result["csv_output"],
        "current_step": "write_outputs",
        "logs": _log(state, f"write_outputs: {result['output']}"),
    }


def run_legacy_agent_node(state: JobState) -> JobState:
    params = dict(state.get("params", {}))
    params["input"] = state["input_path"]
    params["output"] = state["output_path"]
    params.pop("description", None)
    args = SimpleNamespace(**params)
    run(args)
    csv_output = str(Path(state["output_path"]).with_suffix(".csv").resolve())
    return {
        **state,
        "output": str(Path(state["output_path"]).resolve()),
        "csv_output": csv_output,
        "current_step": "run_legacy_agent",
        "logs": _log(state, "run_legacy_agent: completed xhs/pgy pipeline"),
    }


def summarize_node(state: JobState) -> JobState:
    summary = summarize_csv_file(Path(state.get("csv_output", "")))
    return {
        **state,
        "summary": summary,
        "current_step": "summarize",
        "logs": _log(state, f"summarize: {summary.get('rows', 0)} rows"),
    }


def preview_node(state: JobState) -> JobState:
    preview = csv_preview_file(Path(state.get("csv_output", "")), limit=50)
    return {
        **state,
        "preview": preview,
        "current_step": "preview",
        "logs": _log(state, f"preview: {preview.get('total_previewed', 0)} rows"),
    }
