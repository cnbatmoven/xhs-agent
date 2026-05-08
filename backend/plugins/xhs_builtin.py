from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from xhs_note_agent import (
    LlmAnalyzer,
    PgyCrawler,
    XhsCrawler,
    analyze,
    apply_llm_analysis,
    load_source_notes,
    write_outputs,
)

from .registry import PluginSpec, register_plugin


def load_xhs_notes(payload: dict[str, Any]) -> dict[str, Any]:
    notes = load_source_notes(Path(payload["input_path"]))
    limit = int(payload.get("limit") or 0)
    selected_notes = notes[:limit] if limit else notes
    return {
        "notes": selected_notes,
        "source_rows": len(notes),
        "selected_rows": len(selected_notes),
    }


def crawl_xhs_notes(payload: dict[str, Any]) -> dict[str, Any]:
    notes = payload.get("notes", [])
    params = payload.get("params", {})
    output_path = Path(payload["output_path"])
    if params.get("no_crawl"):
        crawled = [{"status": "offline"} for _ in notes]
    else:
        crawler = XhsCrawler(
            headless=bool(params.get("headless")),
            profile=Path(params["profile"]).resolve() if params.get("profile") else None,
            download_covers=bool(params.get("download_covers")),
            cover_dir=output_path.parent / "covers",
            browser_executable=Path(params["browser_executable"]).resolve()
            if params.get("browser_executable")
            else None,
            cdp_url=params.get("cdp_url"),
            login_first=bool(params.get("login_first")),
            crawl_delay=float(params.get("crawl_delay") or 1.5),
            stop_on_rate_limit=not bool(params.get("no_stop_on_rate_limit")),
            rate_limit_cooldown=int(params.get("rate_limit_cooldown") or 0),
            comment_api=not bool(params.get("no_comment_api")),
        )
        crawled = crawler.crawl_many(notes)
    return {"crawled": crawled}


def analyze_xhs_rules(payload: dict[str, Any]) -> dict[str, Any]:
    notes = payload.get("notes", [])
    crawled = payload.get("crawled", [])
    results = [analyze(note, data) for note, data in zip(notes, crawled)]
    return {"results": results}


def crawl_pgy_pricing(payload: dict[str, Any]) -> dict[str, Any]:
    params = payload.get("params", {})
    results = payload.get("results", [])
    if not params.get("crawl_pgy"):
        return {"results": results, "skipped": True}
    if not params.get("cdp_url"):
        raise SystemExit("--crawl-pgy requires --cdp-url so it can reuse your logged-in browser.")
    results = PgyCrawler(
        cdp_url=str(params.get("cdp_url")),
        timeout_ms=int(params.get("pgy_timeout") or 30000),
        delay=float(params.get("pgy_delay") or 3.0),
        safe_mode=bool(params.get("pgy_safe_mode")),
        max_retries=int(params.get("pgy_max_retries") or 1),
    ).enrich(results)
    return {"results": results, "skipped": False}


def analyze_with_llm(payload: dict[str, Any]) -> dict[str, Any]:
    params = payload.get("params", {})
    results = payload.get("results", [])
    if not params.get("use_llm"):
        return {"results": results, "skipped": True}
    analyzer = LlmAnalyzer.from_args(SimpleNamespace(**params))
    results = apply_llm_analysis(results, analyzer)
    return {"results": results, "skipped": False}


def write_xhs_outputs(payload: dict[str, Any]) -> dict[str, Any]:
    output_path = Path(payload["output_path"])
    params = payload.get("params", {})
    write_outputs(payload.get("results", []), output_path, embed_covers=bool(params.get("embed_covers")))
    return {
        "output": str(output_path.resolve()),
        "csv_output": str(output_path.with_suffix(".csv").resolve()),
    }


def register_builtin_plugins() -> None:
    specs = [
        PluginSpec(
            plugin_id="xhs.load_notes",
            name="XHS Excel note loader",
            kind="loader",
            node="load_notes",
            description="Load note rows from the source workbook sheet.",
            inputs=["input_path", "limit"],
            outputs=["notes", "source_rows", "selected_rows"],
            risk_level="low",
            handler=load_xhs_notes,
        ),
        PluginSpec(
            plugin_id="xhs.crawl_notes",
            name="XHS note crawler",
            kind="crawler",
            node="crawl_xhs",
            description="Crawl XHS note content, cover, author, comments, and metrics.",
            inputs=["notes", "params", "output_path"],
            outputs=["crawled"],
            risk_level="medium",
            handler=crawl_xhs_notes,
        ),
        PluginSpec(
            plugin_id="xhs.rule_analysis",
            name="XHS rule analysis",
            kind="analyzer",
            node="analyze_rules",
            description="Classify content type and generate rule-based creative and audience suggestions.",
            inputs=["notes", "crawled"],
            outputs=["results"],
            risk_level="low",
            handler=analyze_xhs_rules,
        ),
        PluginSpec(
            plugin_id="pgy.pricing",
            name="Pugongying pricing crawler",
            kind="crawler",
            node="crawl_pgy",
            description="Enrich creator rows with Pugongying image/video prices and CPE.",
            inputs=["results", "params"],
            outputs=["results"],
            risk_level="high",
            handler=crawl_pgy_pricing,
        ),
        PluginSpec(
            plugin_id="llm.openai_compatible",
            name="OpenAI-compatible LLM analyzer",
            kind="analyzer",
            node="llm_analyze",
            description="Use an OpenAI-compatible chat completions API for richer analysis.",
            inputs=["results", "params"],
            outputs=["results"],
            risk_level="medium",
            handler=analyze_with_llm,
        ),
        PluginSpec(
            plugin_id="xhs.write_outputs",
            name="XHS Excel/CSV writer",
            kind="writer",
            node="write_outputs",
            description="Write analysis results to Excel and CSV.",
            inputs=["results", "output_path", "params"],
            outputs=["output", "csv_output"],
            risk_level="low",
            handler=write_xhs_outputs,
        ),
    ]
    for spec in specs:
        register_plugin(spec)
