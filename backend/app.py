from __future__ import annotations

import csv
import json
import os
import queue
import re
import shutil
import threading
import traceback
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.plugins import get_plugin, list_plugins
from backend.quality import (
    QUALITY_REQUIRED_COLUMNS,
    merge_retry_results,
    quality_report,
    retry_prep_report,
)
from backend.safety import SafetyPolicy, UsageTracker, normalize_for_safety
from xhs_note_agent import run

try:
    from backend.graphs.xhs_analysis_graph import preview_xhs_analysis_plan, run_xhs_analysis_graph
except Exception:  # LangGraph is optional at import time; the legacy path remains available.
    preview_xhs_analysis_plan = None
    run_xhs_analysis_graph = None


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
JOB_DIR = DATA_DIR / "jobs"
LOG_DIR = JOB_DIR / "logs"
ARTIFACT_DIR = JOB_DIR / "artifacts"
SAFETY_DIR = DATA_DIR / "safety"
JOB_STORE = JOB_DIR / "jobs.json"
OUTPUT_DIR = BASE_DIR / "outputs"
LOCAL_TZ = timezone(timedelta(hours=8))

for directory in [DATA_DIR, UPLOAD_DIR, JOB_DIR, LOG_DIR, ARTIFACT_DIR, SAFETY_DIR, OUTPUT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def local_stamp() -> str:
    return datetime.now(LOCAL_TZ).strftime("%Y年%m月%d日%H时%M分%S秒")


def short_local_time(value: datetime | None = None) -> str:
    current = value or datetime.now(LOCAL_TZ)
    return current.astimezone(LOCAL_TZ).strftime("%Y/%m/%d %H:%M")


def parse_name_time(value: str) -> str:
    millisecond_match = re.search(r"_(\d{13})(?:_|$)", value)
    if millisecond_match:
        try:
            moment = datetime.fromtimestamp(int(millisecond_match.group(1)) / 1000, LOCAL_TZ)
            return short_local_time(moment)
        except ValueError:
            pass
    stamp_match = re.search(r"(\d{8})_(\d{6})", value)
    if stamp_match:
        try:
            moment = datetime.strptime("".join(stamp_match.groups()), "%Y%m%d%H%M%S").replace(tzinfo=LOCAL_TZ)
            return short_local_time(moment)
        except ValueError:
            pass
    return ""


def clean_filename_part(value: str, fallback: str = "小红书笔记分析") -> str:
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(value or ""))
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"_+", "_", text).strip("._ ")
    return (text[:48] or fallback).strip("._ ")


def task_title_from_request(request: dict[str, Any]) -> str:
    if request.get("retry_base_csv"):
        description = str(request.get("description") or "").strip()
        if description and not re.fullmatch(r"retry job for [0-9a-f]{8,}", description):
            return description
        return "补抓缺失数据"
    mode = "离线表格分析" if request.get("no_crawl") else "小红书笔记采集"
    limit = int(request.get("limit") or 0)
    row_part = f"前{limit}条" if limit > 0 else "全部笔记"
    features: list[str] = []
    if request.get("download_covers") or request.get("embed_covers"):
        features.append("封面")
    if not request.get("no_crawl"):
        features.extend(["评论", "粉丝"])
    if request.get("crawl_pgy"):
        features.append("蒲公英报价")
    if request.get("use_llm"):
        features.append("创意建议")
    feature_part = "、".join(dict.fromkeys(features)) or "基础字段"
    return f"{mode}：{row_part}，补{feature_part}"


def output_path_for_request(request: dict[str, Any], suffix: str = "结果") -> Path:
    title = task_title_from_request(request)
    stem = f"{clean_filename_part(title)}_{clean_filename_part(suffix, fallback='结果')}_{local_stamp()}"
    return unique_path(OUTPUT_DIR / f"{stem}.xlsx")


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_第{index}次{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"cannot find available filename for {path.name}")


def display_result_name(filename: str) -> str:
    path = Path(filename)
    stem = path.stem
    ext = path.suffix.upper().lstrip(".")
    when = parse_name_time(stem.split("_merged_", 1)[1]) if "_merged_" in stem else parse_name_time(stem)
    suffix = f"（{when}）" if when else ""
    if "_merged_" in stem or "补抓合并" in stem:
        return f"补抓合并结果{suffix}.{ext}"
    if stem.startswith("retry_input_") or "补抓输入" in stem:
        return f"补抓输入表{suffix}.{ext}"
    if stem.startswith("retry_job_") or "补抓缺失数据" in stem:
        return f"补抓临时结果{suffix}.{ext}"
    if stem.startswith("frontend_") or stem.startswith("job_"):
        return f"小红书笔记分析结果{suffix}.{ext}"
    return filename


class AnalyzeRequest(BaseModel):
    input: str = Field(..., description="Excel input path")
    output: str = Field("outputs/xhs_note_analysis.xlsx", description="Excel output path")
    description: str = Field("", description="Natural language task description")
    limit: int = Field(0, ge=0, description="Process first N rows only; 0 means all")
    no_crawl: bool = False
    headless: bool = True
    profile: str | None = None
    browser_executable: str | None = None
    cdp_url: str | None = None
    login_first: bool = False
    crawl_delay: float = Field(1.5, ge=0)
    no_stop_on_rate_limit: bool = False
    rate_limit_cooldown: int = Field(0, ge=0)
    no_comment_api: bool = False
    download_covers: bool = False
    embed_covers: bool = False
    crawl_pgy: bool = False
    pgy_delay: float = Field(3.0, ge=0)
    pgy_timeout: int = Field(30000, ge=1000)
    pgy_safe_mode: bool = False
    pgy_max_retries: int = Field(1, ge=1, le=5)
    use_llm: bool = False
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_timeout: int = Field(60, ge=1)
    llm_temperature: float = Field(0.3, ge=0, le=2)
    retry_base_csv: str | None = None
    retry_merge_output: str | None = None
    execution_mode: str = Field(
        "graph_legacy",
        description="graph_legacy uses LangGraph orchestration with the proven crawler; graph_split uses experimental nodes; legacy bypasses LangGraph.",
    )


class BatchRequest(BaseModel):
    jobs: list[AnalyzeRequest]


@dataclass
class JobRecord:
    job_id: str
    status: str
    created_at: str
    updated_at: str
    request: dict[str, Any]
    title: str = ""
    output: str = ""
    csv_output: str = ""
    current_step: str = ""
    plan: list[str] = field(default_factory=list)
    source_rows: int = 0
    selected_rows: int = 0
    artifacts: dict[str, str] = field(default_factory=dict)
    safety: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    logs: list[str] = field(default_factory=list)


app = FastAPI(title="XHS Note Analysis Backend", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
_jobs: dict[str, JobRecord] = {}
_jobs_lock = threading.Lock()
_job_queue: queue.Queue[str] = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()
_usage_tracker = UsageTracker(SAFETY_DIR)


def public_job(job: JobRecord) -> dict[str, Any]:
    payload = asdict(job)
    title = job.title or task_title_from_request(job.request)
    payload["title"] = title
    payload["display_title"] = title
    payload["display_id"] = title
    if job.output:
        payload["output_display_name"] = display_result_name(Path(job.output).name)
    if job.csv_output:
        payload["csv_display_name"] = display_result_name(Path(job.csv_output).name)
    return payload


def save_jobs() -> None:
    with _jobs_lock:
        payload = [asdict(job) for job in _jobs.values()]
    tmp_path = JOB_STORE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(JOB_STORE)


def load_jobs() -> None:
    if not JOB_STORE.exists():
        return
    try:
        payload = json.loads(JOB_STORE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    with _jobs_lock:
        for item in payload:
            job = JobRecord(**item)
            if not job.title:
                job.title = task_title_from_request(job.request)
            if job.status in {"running", "queued"}:
                job.status = "queued"
                job.updated_at = utc_now_iso()
            _jobs[job.job_id] = job


def append_log(job_id: str, message: str) -> None:
    timestamped = f"{utc_now_iso()} {message}"
    with _jobs_lock:
        job = _jobs[job_id]
        job.logs.append(timestamped)
        job.updated_at = utc_now_iso()
    log_path = LOG_DIR / f"{job_id}.log"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(timestamped + "\n")
    save_jobs()


def update_job(job_id: str, **changes: Any) -> None:
    with _jobs_lock:
        job = _jobs[job_id]
        for key, value in changes.items():
            setattr(job, key, value)
        job.updated_at = utc_now_iso()
    save_jobs()


def jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def artifact_payload(node_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    keys_by_node = {
        "parse_intent": ["params"],
        "plan_steps": ["plan", "params"],
        "validate_input": ["input_path", "output_path"],
        "load_notes": ["source_rows", "selected_rows", "notes"],
        "crawl_xhs": ["crawled"],
        "run_legacy_agent": ["output", "csv_output"],
        "analyze_rules": ["results"],
        "crawl_pgy": ["results"],
        "llm_analyze": ["results"],
        "write_outputs": ["output", "csv_output"],
        "summarize": ["summary"],
        "preview": ["preview"],
    }
    selected = {key: payload.get(key) for key in keys_by_node.get(node_name, []) if key in payload}
    selected["current_step"] = payload.get("current_step", node_name)
    return jsonable(selected)


def persist_artifact(job_id: str, node_name: str, payload: dict[str, Any]) -> str:
    job_artifact_dir = ARTIFACT_DIR / job_id
    job_artifact_dir.mkdir(parents=True, exist_ok=True)
    target = job_artifact_dir / f"{node_name}.json"
    target.write_text(
        json.dumps(artifact_payload(node_name, payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(target.resolve())


def update_job_artifact(job_id: str, node_name: str, artifact_path: str) -> None:
    with _jobs_lock:
        job = _jobs[job_id]
        job.artifacts[node_name] = artifact_path
        job.updated_at = utc_now_iso()
    save_jobs()


def enqueue_job(job_id: str) -> None:
    _job_queue.put(job_id)


def build_args(req: AnalyzeRequest) -> SimpleNamespace:
    payload = req.model_dump()
    payload["input"] = str(Path(payload["input"]).expanduser().resolve())
    payload["output"] = str(Path(payload["output"]).expanduser().resolve())
    payload.pop("description", None)
    payload.pop("execution_mode", None)
    return SimpleNamespace(**payload)


def ensure_allowed_file(path: str) -> Path:
    target = Path(path).expanduser().resolve()
    if BASE_DIR not in target.parents and target != BASE_DIR:
        raise HTTPException(status_code=403, detail="file path is outside workspace")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return target


def row_value(row: dict[str, str], names: list[str]) -> str:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def summarize_csv(csv_path: Path) -> dict[str, Any]:
    if not csv_path.exists():
        return {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {"rows": 0}

    def count(names: list[str], predicate) -> int:
        total = 0
        for row in rows:
            if predicate(row_value(row, names)):
                total += 1
        return total

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


def csv_preview(csv_path: Path, limit: int = 50) -> dict[str, Any]:
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


def execute_job(job_id: str) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        req = AnalyzeRequest(**job.request)
    try:
        update_job(job_id, status="running", error="")
        append_log(job_id, f"start input={req.input}")
        if req.execution_mode == "legacy" or run_xhs_analysis_graph is None:
            reason = "requested legacy mode" if req.execution_mode == "legacy" else "langgraph unavailable"
            append_log(job_id, f"{reason}, using legacy runner")
            final_state = execute_legacy_job(job_id, req)
        else:
            final_state = execute_graph_job(job_id, req)
        update_job(
            job_id,
            status="succeeded",
            output=final_state.get("output", ""),
            csv_output=final_state.get("csv_output", ""),
            summary=final_state.get("summary", {}),
            current_step="finished",
            plan=final_state.get("plan", []),
            source_rows=final_state.get("source_rows", 0),
            selected_rows=final_state.get("selected_rows", 0),
        )
        if req.retry_base_csv and req.retry_merge_output and final_state.get("csv_output"):
            merge_report = merge_retry_results(
                Path(req.retry_base_csv),
                Path(final_state["csv_output"]),
                Path(req.retry_merge_output),
            )
            update_job(
                job_id,
                output=merge_report["merged_output"],
                csv_output=merge_report["merged_csv"],
                summary=merge_report["merged_quality"],
            )
            append_log(job_id, f"merged retry output={merge_report['merged_output']}")
        xhs_rows = int(final_state.get("selected_rows", 0) or 0) if not req.no_crawl else 0
        pgy_rows = int(final_state.get("selected_rows", 0) or 0) if req.crawl_pgy else 0
        if xhs_rows or pgy_rows:
            usage = _usage_tracker.record_job(xhs_rows=xhs_rows, pgy_rows=pgy_rows)
            append_log(
                job_id,
                f"usage recorded: xhs_rows={xhs_rows}, pgy_rows={pgy_rows}, hour={usage.get('current_hour_key')}",
            )
        append_log(job_id, f"done output={final_state.get('output', '')}")
    except Exception as exc:
        error = "".join(traceback.format_exception(exc))
        update_job(job_id, status="failed", error=error)
        append_log(job_id, f"failed: {exc}")


def execute_legacy_job(job_id: str, req: AnalyzeRequest) -> dict[str, Any]:
    args = build_args(req)
    update_job(job_id, current_step="legacy_run", plan=["legacy_run", "summarize", "preview"])
    run(args)
    output = str(Path(args.output).resolve())
    csv_output = str(Path(args.output).with_suffix(".csv").resolve())
    return {
        "output": output,
        "csv_output": csv_output,
        "summary": summarize_csv(Path(csv_output)),
        "preview": csv_preview(Path(csv_output), limit=50),
        "plan": ["legacy_run", "summarize", "preview"],
    }


def execute_graph_job(job_id: str, req: AnalyzeRequest) -> dict[str, Any]:
    params = req.model_dump()
    input_path = str(Path(params.pop("input")).expanduser().resolve())
    output_path = str(Path(params.pop("output")).expanduser().resolve())
    description = str(params.pop("description", ""))
    execution_mode = str(params.pop("execution_mode", req.execution_mode))
    initial_state = {
        "job_id": job_id,
        "execution_mode": execution_mode,
        "description": description,
        "input_path": input_path,
        "output_path": output_path,
        "params": params,
        "logs": [],
    }

    def on_event(node_name: str, payload: dict[str, Any]) -> None:
        changes: dict[str, Any] = {"current_step": node_name}
        if payload.get("plan"):
            changes["plan"] = payload["plan"]
        if payload.get("summary"):
            changes["summary"] = payload["summary"]
        if payload.get("output"):
            changes["output"] = payload["output"]
        if payload.get("csv_output"):
            changes["csv_output"] = payload["csv_output"]
        if "source_rows" in payload:
            changes["source_rows"] = payload["source_rows"]
        if "selected_rows" in payload:
            changes["selected_rows"] = payload["selected_rows"]
        update_job(job_id, **changes)
        artifact_path = persist_artifact(job_id, node_name, payload)
        update_job_artifact(job_id, node_name, artifact_path)
        node_logs = payload.get("logs") or []
        detail = node_logs[-1] if node_logs else ""
        append_log(job_id, f"graph:{node_name}" + (f" | {detail}" if detail else ""))

    return run_xhs_analysis_graph(
        initial_state,
        on_event=on_event,
        split=req.execution_mode == "graph_split",
    )


def worker_loop() -> None:
    while True:
        job_id = _job_queue.get()
        try:
            execute_job(job_id)
        finally:
            _job_queue.task_done()


def ensure_worker() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        thread = threading.Thread(target=worker_loop, daemon=True, name="xhs-job-worker")
        thread.start()
        _worker_started = True


def prepare_safe_request(req: AnalyzeRequest) -> tuple[AnalyzeRequest, dict[str, Any]]:
    preview = _usage_tracker.enrich_preview(normalize_for_safety(req.model_dump()))
    if not preview.allowed:
        raise HTTPException(status_code=400, detail=preview.public_dict())
    safe_req = AnalyzeRequest(**preview.normalized)
    if safe_req.use_llm and not (
        safe_req.llm_api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    ):
        raise HTTPException(
            status_code=400,
            detail="启用 LLM 需要先配置 LLM_API_KEY / OPENAI_API_KEY；不需要 LLM 时请关闭“启用 LLM”。",
        )
    return safe_req, preview.public_dict()


def cleanup_job_files(job_id: str) -> None:
    log_path = LOG_DIR / f"{job_id}.log"
    if log_path.exists():
        log_path.unlink()
    artifact_dir = (ARTIFACT_DIR / job_id).resolve()
    artifact_root = ARTIFACT_DIR.resolve()
    if artifact_dir.exists() and artifact_root in artifact_dir.parents:
        shutil.rmtree(artifact_dir)


def create_job_record(req: AnalyzeRequest) -> JobRecord:
    safe_req, safety = prepare_safe_request(req)
    job_id = uuid4().hex
    now = utc_now_iso()
    request = safe_req.model_dump(exclude={"llm_api_key"})
    output_name = Path(str(request.get("output") or "")).name
    should_make_readable_output = (
        not request.get("output")
        or request["output"] == "outputs/xhs_note_analysis.xlsx"
        or output_name.startswith(("frontend_", "job_"))
    )
    if should_make_readable_output:
        request["output"] = str(output_path_for_request(request).resolve())
    title = task_title_from_request(request)
    return JobRecord(
        job_id=job_id,
        status="queued",
        created_at=now,
        updated_at=now,
        request=request,
        title=title,
        safety=safety,
    )


def list_result_files() -> list[dict[str, Any]]:
    files = []
    for path in OUTPUT_DIR.glob("*"):
        if not path.is_file() or path.suffix.lower() not in {".xlsx", ".csv"}:
            continue
        stat = path.stat()
        files.append(
            {
                "name": path.name,
                "path": str(path.resolve()),
                "display_name": display_result_name(path.name),
                "size": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "type": path.suffix.lower().lstrip("."),
            }
        )
    return sorted(files, key=lambda item: item["modified_at"], reverse=True)


def quality_scan(limit_files: int = 50, preview_limit: int = 10) -> dict[str, Any]:
    result_files = [item for item in list_result_files() if item["type"] == "csv"][:limit_files]
    with _jobs_lock:
        job_index = {job.csv_output: job for job in _jobs.values() if job.csv_output}
    reports = []
    total_retry_needed = 0
    for item in result_files:
        csv_path = item["path"]
        report = quality_report(Path(csv_path), limit=preview_limit)
        total_retry_needed += int(report.get("retry_needed", 0) or 0)
        job = job_index.get(csv_path)
        is_retry_artifact = bool(
            (job and job.request.get("retry_base_csv"))
            or item["name"].startswith("retry_job_")
            or "_merged_" in item["name"]
        )
        reports.append(
            {
                "name": item["name"],
                "display_name": item.get("display_name") or display_result_name(item["name"]),
                "path": csv_path,
                "modified_at": item["modified_at"],
                "size": item["size"],
                "quality": report,
                "job_id": job.job_id if job else None,
                "job_title": (job.title or task_title_from_request(job.request)) if job else None,
                "source_input": job.request.get("input") if job else None,
                "is_retry_artifact": is_retry_artifact,
                "can_retry": bool(job and report.get("retry_needed", 0) and not is_retry_artifact),
            }
        )
    reports.sort(key=lambda item: (item["quality"].get("score", 100), -item["quality"].get("retry_needed", 0)))
    return {
        "files": reports,
        "count": len(reports),
        "total_retry_needed": total_retry_needed,
    }


@app.on_event("startup")
def startup() -> None:
    load_jobs()
    ensure_worker()
    with _jobs_lock:
        pending = [job.job_id for job in _jobs.values() if job.status == "queued"]
    for job_id in pending:
        enqueue_job(job_id)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "time": utc_now_iso(),
        "queue_size": _job_queue.qsize(),
        "graph_enabled": run_xhs_analysis_graph is not None,
        "plugins": len(list_plugins()),
        "llm_configured": bool(os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")),
    }


@app.get("/api/v1/safety/usage")
def safety_usage() -> dict[str, Any]:
    return _usage_tracker.snapshot()


@app.get("/api/v1/safety/policy")
def safety_policy() -> dict[str, Any]:
    return asdict(SafetyPolicy())


@app.get("/api/v1/plugins")
def plugins() -> list[dict[str, Any]]:
    return list_plugins()


@app.get("/api/v1/plugins/{plugin_id}")
def plugin_detail(plugin_id: str) -> dict[str, Any]:
    try:
        return get_plugin(plugin_id).public_dict()
    except KeyError:
        raise HTTPException(status_code=404, detail="plugin not found")


@app.post("/api/v1/safety/preview")
def safety_preview(req: AnalyzeRequest) -> dict[str, Any]:
    return _usage_tracker.enrich_preview(normalize_for_safety(req.model_dump())).public_dict()


@app.post("/api/v1/plan")
def preview_plan(req: AnalyzeRequest) -> dict[str, Any]:
    safety = _usage_tracker.enrich_preview(normalize_for_safety(req.model_dump()))
    params = dict(safety.normalized)
    input_path = str(Path(params.pop("input")).expanduser().resolve())
    output_path = str(Path(params.pop("output")).expanduser().resolve())
    description = str(params.pop("description", ""))
    execution_mode = str(params.pop("execution_mode", "graph_legacy"))
    if execution_mode == "legacy" or preview_xhs_analysis_plan is None:
        return {
            "execution_mode": "legacy",
            "graph_enabled": run_xhs_analysis_graph is not None,
            "input_path": input_path,
            "output_path": output_path,
            "params": params,
            "plan": ["legacy_run", "summarize", "preview"],
            "safety": safety.public_dict(),
        }
    state = preview_xhs_analysis_plan(
        {
            "job_id": "plan-preview",
            "execution_mode": execution_mode,
            "description": description,
            "input_path": input_path,
            "output_path": output_path,
            "params": params,
            "logs": [],
        }
    )
    return {
        "execution_mode": execution_mode,
        "graph_enabled": True,
        "input_path": input_path,
        "output_path": output_path,
        "params": state.get("params", {}),
        "plan": state.get("plan", []),
        "logs": state.get("logs", []),
        "safety": safety.public_dict(),
    }


@app.post("/api/v1/uploads")
def upload_file(file: UploadFile = File(...)) -> dict[str, Any]:
    suffix = Path(file.filename or "input.xlsx").suffix.lower()
    if suffix not in {".xlsx", ".xls", ".csv"}:
        raise HTTPException(status_code=400, detail="only .xlsx, .xls, .csv files are supported")
    original_stem = clean_filename_part(Path(file.filename or "原始表格").stem, fallback="原始表格")
    target = unique_path(UPLOAD_DIR / f"上传原始表_{original_stem}_{local_stamp()}{suffix}")
    with target.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {
        "filename": file.filename,
        "display_name": target.name,
        "path": str(target.resolve()),
        "size": target.stat().st_size,
    }


@app.get("/api/v1/jobs")
def list_jobs() -> list[dict[str, Any]]:
    with _jobs_lock:
        jobs = sorted(_jobs.values(), key=lambda job: job.created_at, reverse=True)
        return [public_job(job) for job in jobs]


@app.post("/api/v1/jobs")
def create_job(req: AnalyzeRequest) -> dict[str, Any]:
    record = create_job_record(req)
    with _jobs_lock:
        _jobs[record.job_id] = record
    save_jobs()
    append_log(record.job_id, "queued")
    if record.safety.get("adjustments"):
        append_log(record.job_id, "safety adjustments: " + "; ".join(record.safety["adjustments"]))
    if record.safety.get("warnings"):
        append_log(record.job_id, "safety warnings: " + "; ".join(record.safety["warnings"]))
    enqueue_job(record.job_id)
    return {"job_id": record.job_id, "status": "queued", "title": record.title, "safety": record.safety}


@app.post("/api/v1/jobs/batch")
def create_batch(req: BatchRequest) -> dict[str, Any]:
    records = [create_job_record(item) for item in req.jobs]
    job_ids = [record.job_id for record in records]
    with _jobs_lock:
        for record in records:
            _jobs[record.job_id] = record
    save_jobs()
    for job_id in job_ids:
        append_log(job_id, "queued")
        with _jobs_lock:
            safety = _jobs[job_id].safety
        if safety.get("adjustments"):
            append_log(job_id, "safety adjustments: " + "; ".join(safety["adjustments"]))
        if safety.get("warnings"):
            append_log(job_id, "safety warnings: " + "; ".join(safety["warnings"]))
        enqueue_job(job_id)
    return {
        "job_ids": job_ids,
        "titles": [record.title for record in records],
        "status": "queued",
        "count": len(job_ids),
    }


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        return public_job(job)


@app.delete("/api/v1/jobs")
def delete_finished_jobs() -> dict[str, Any]:
    with _jobs_lock:
        job_ids = [
            job_id
            for job_id, job in _jobs.items()
            if job.status not in {"queued", "running"}
        ]
        for job_id in job_ids:
            _jobs.pop(job_id, None)
    save_jobs()
    for job_id in job_ids:
        cleanup_job_files(job_id)
    return {"status": "deleted", "count": len(job_ids), "job_ids": job_ids}


@app.delete("/api/v1/jobs/{job_id}")
def delete_job(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        if job.status in {"queued", "running"}:
            raise HTTPException(status_code=409, detail="running or queued jobs cannot be deleted")
        _jobs.pop(job_id, None)
    save_jobs()
    cleanup_job_files(job_id)
    return {"status": "deleted", "job_id": job_id}


def enqueue_retry_job(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        request = dict(job.request)
        csv_output = job.csv_output
        source_title = job.title or task_title_from_request(job.request)
    if not csv_output:
        raise HTTPException(status_code=400, detail="job has no csv output yet")
    source_path = request.get("input")
    if not source_path:
        raise HTTPException(status_code=400, detail="job has no source input path")
    prep = retry_prep_report(Path(source_path), Path(csv_output), OUTPUT_DIR, output_stem=f"{source_title}_补抓输入表")
    if prep["retry_input_rows"] <= 0:
        return {"status": "no_retry_needed", "job_id": None, "prep": prep}
    retry_description = f"补抓缺失数据：{source_title}"
    retry_base_request = {
        **request,
        "input": prep["retry_input"],
        "output": str(output_path_for_request({**request, "description": retry_description, "retry_base_csv": csv_output}, suffix="临时结果").resolve()),
        "limit": 0,
        "description": retry_description,
        "retry_base_csv": csv_output,
        "retry_merge_output": str(unique_path(OUTPUT_DIR / f"{clean_filename_part(source_title)}_补抓合并结果_{local_stamp()}.xlsx").resolve()),
    }
    retry_req = AnalyzeRequest(
        **retry_base_request
    )
    record = create_job_record(retry_req)
    with _jobs_lock:
        _jobs[record.job_id] = record
    save_jobs()
    append_log(record.job_id, f"queued retry for {job_id}")
    append_log(record.job_id, f"retry input={prep['retry_input']}")
    enqueue_job(record.job_id)
    return {"status": "queued", "job_id": record.job_id, "prep": prep, "safety": record.safety}


@app.post("/api/v1/jobs/{job_id}/retry")
def create_retry_job(job_id: str) -> dict[str, Any]:
    return enqueue_retry_job(job_id)


@app.post("/api/v1/retry-scan")
def create_retry_jobs_from_scan(limit_files: int = 50, max_jobs: int = 20, preview_limit: int = 10) -> dict[str, Any]:
    scan = quality_scan(limit_files=limit_files, preview_limit=preview_limit)
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for item in scan["files"]:
        if not item.get("can_retry"):
            skipped.append({"name": item["name"], "job_id": item.get("job_id"), "reason": "not_retryable"})
            continue
        if len(created) >= max_jobs:
            skipped.append({"name": item["name"], "job_id": item.get("job_id"), "reason": "max_jobs_reached"})
            continue
        try:
            result = enqueue_retry_job(str(item["job_id"]))
        except HTTPException as exc:
            skipped.append({"name": item["name"], "job_id": item.get("job_id"), "reason": str(exc.detail)})
            continue
        created.append(
            {
                "name": item["name"],
                "source_job_id": item["job_id"],
                "retry_job_id": result.get("job_id"),
                "prep": result.get("prep"),
            }
        )
    return {
        "status": "queued" if created else "no_retry_needed",
        "created": created,
        "skipped": skipped,
        "scan_count": scan["count"],
        "retry_needed_total": scan["total_retry_needed"],
    }


@app.get("/api/v1/jobs/{job_id}/summary")
def get_job_summary(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        return {
            "job_id": job.job_id,
            "status": job.status,
            "summary": job.summary,
            "output": job.output,
            "csv_output": job.csv_output,
        }


@app.get("/api/v1/jobs/{job_id}/preview")
def get_job_preview(job_id: str, limit: int = 50) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        csv_output = job.csv_output
    if not csv_output:
        return {"columns": [], "rows": [], "total_previewed": 0}
    return csv_preview(Path(csv_output), limit=limit)


@app.get("/api/v1/jobs/{job_id}/quality")
def get_job_quality(job_id: str, limit: int = 50) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        csv_output = job.csv_output
    if not csv_output:
        return quality_report(Path(""), limit=limit)
    return quality_report(Path(csv_output), limit=limit)


@app.get("/api/v1/jobs/{job_id}/artifacts")
def get_job_artifacts(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        return {"job_id": job.job_id, "artifacts": job.artifacts}


@app.get("/api/v1/files")
def download_file(path: str) -> FileResponse:
    target = ensure_allowed_file(path)
    return FileResponse(target, filename=target.name)


@app.get("/api/v1/result-files")
def result_files() -> list[dict[str, Any]]:
    return list_result_files()


@app.get("/api/v1/quality-scan")
def scan_quality(limit_files: int = 50, preview_limit: int = 10) -> dict[str, Any]:
    return quality_scan(limit_files=limit_files, preview_limit=preview_limit)


@app.get("/api/v1/csv-preview")
def preview_csv(path: str, limit: int = 50) -> dict[str, Any]:
    target = ensure_allowed_file(path)
    if target.suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail="csv preview only supports .csv files")
    return csv_preview(target, limit=limit)


@app.get("/api/v1/quality")
def inspect_quality(path: str, limit: int = 50) -> dict[str, Any]:
    target = ensure_allowed_file(path)
    if target.suffix.lower() != ".csv":
        target = target.with_suffix(".csv")
    return quality_report(target, limit=limit)


@app.get("/api/v1/retry-prep")
def prepare_retry(path: str, source: str, limit: int = 50) -> dict[str, Any]:
    result_target = ensure_allowed_file(path)
    source_target = ensure_allowed_file(source)
    if result_target.suffix.lower() != ".csv":
        result_target = result_target.with_suffix(".csv")
    report = retry_prep_report(source_target, result_target, OUTPUT_DIR)
    report["preview_limit"] = limit
    return report


@app.post("/api/v1/run-sync")
def run_sync(req: AnalyzeRequest) -> dict[str, Any]:
    args = build_args(req)
    run(args)
    output = str(Path(args.output).resolve())
    csv_output = str(Path(args.output).with_suffix(".csv").resolve())
    summary = summarize_csv(Path(csv_output))
    return {
        "status": "succeeded",
        "output": output,
        "csv_output": csv_output,
        "summary": summary,
        "preview": csv_preview(Path(csv_output), limit=50),
    }
