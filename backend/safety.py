from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SafetyPolicy:
    min_xhs_delay: float = 6.0
    min_pgy_delay: float = 12.0
    max_recommended_xhs_limit: int = 50
    max_recommended_split_crawl_limit: int = 5
    max_recommended_pgy_limit: int = 10
    hourly_warning_xhs_rows: int = 120
    hourly_warning_pgy_rows: int = 20
    daily_warning_xhs_rows: int = 500
    daily_warning_pgy_rows: int = 60
    hourly_hard_xhs_rows: int = 240
    hourly_hard_pgy_rows: int = 20
    daily_hard_xhs_rows: int = 1000
    daily_hard_pgy_rows: int = 60
    enforce_xhs_hard_limit: bool = False
    enforce_pgy_hard_limit: bool = True


@dataclass
class SafetyPreview:
    risk_level: str
    normalized: dict[str, Any]
    adjustments: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    estimated_crawl_rows: int = 0
    uses_xhs: bool = False
    uses_pgy: bool = False
    uses_llm: bool = False
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return not self.errors

    def public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["allowed"] = self.allowed
        return payload


def _limit(payload: dict[str, Any]) -> int:
    try:
        return max(0, int(payload.get("limit") or 0))
    except (TypeError, ValueError):
        return 0


def _set_min_float(
    payload: dict[str, Any],
    key: str,
    minimum: float,
    adjustments: list[str],
    label: str,
) -> None:
    current = float(payload.get(key) or 0)
    if current < minimum:
        payload[key] = minimum
        adjustments.append(f"{label} raised from {current:g}s to {minimum:g}s")


def normalize_for_safety(raw_payload: dict[str, Any], policy: SafetyPolicy | None = None) -> SafetyPreview:
    policy = policy or SafetyPolicy()
    payload = dict(raw_payload)
    adjustments: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []

    no_crawl = bool(payload.get("no_crawl"))
    crawl_pgy = bool(payload.get("crawl_pgy"))
    use_llm = bool(payload.get("use_llm"))
    execution_mode = str(payload.get("execution_mode") or "graph_legacy")
    limit = _limit(payload)
    uses_xhs = not no_crawl
    uses_pgy = crawl_pgy
    uses_llm = use_llm
    estimated_rows = limit

    if uses_xhs:
        _set_min_float(payload, "crawl_delay", policy.min_xhs_delay, adjustments, "XHS crawl delay")
        if limit > policy.max_recommended_xhs_limit:
            warnings.append(
                f"XHS crawl limit {limit} is above the recommended {policy.max_recommended_xhs_limit} rows per task"
            )
        if execution_mode == "graph_split" and (limit == 0 or limit > policy.max_recommended_split_crawl_limit):
            warnings.append(
                f"graph_split real crawl is experimental; recommended limit is {policy.max_recommended_split_crawl_limit} rows first"
            )

    if uses_pgy:
        if not payload.get("cdp_url"):
            errors.append("Pugongying crawl requires cdp_url so it can reuse your logged-in browser")
        if not payload.get("pgy_safe_mode"):
            payload["pgy_safe_mode"] = True
            adjustments.append("Pugongying safe mode enabled")
        _set_min_float(payload, "pgy_delay", policy.min_pgy_delay, adjustments, "Pugongying delay")
        if limit == 0:
            warnings.append(
                f"Pugongying crawl with no limit may be risky; recommended limit is {policy.max_recommended_pgy_limit}"
            )
        elif limit > policy.max_recommended_pgy_limit:
            warnings.append(
                f"Pugongying crawl limit {limit} is above the recommended {policy.max_recommended_pgy_limit} rows per task"
            )

    risk_level = "low"
    if uses_xhs or uses_llm:
        risk_level = "medium"
    if uses_pgy:
        risk_level = "high"

    return SafetyPreview(
        risk_level=risk_level,
        normalized=payload,
        adjustments=adjustments,
        warnings=warnings,
        errors=errors,
        estimated_crawl_rows=estimated_rows,
        uses_xhs=uses_xhs,
        uses_pgy=uses_pgy,
        uses_llm=uses_llm,
    )


class UsageTracker:
    def __init__(self, data_dir: Path, policy: SafetyPolicy | None = None):
        self.data_dir = data_dir
        self.policy = policy or SafetyPolicy()
        self._lock = threading.Lock()
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def today_path(self) -> Path:
        return self.data_dir / f"usage_{datetime.now().strftime('%Y%m%d')}.json"

    def _hour_key(self) -> str:
        return datetime.now().strftime("%H")

    def _default_payload(self) -> dict[str, Any]:
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "totals": {"xhs_rows": 0, "pgy_rows": 0, "jobs": 0},
            "hours": {},
            "last_access": {"xhs": "", "pgy": ""},
        }

    def load(self) -> dict[str, Any]:
        path = self.today_path()
        if not path.exists():
            return self._default_payload()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return self._default_payload()
        default = self._default_payload()
        default.update(data)
        default.setdefault("totals", {"xhs_rows": 0, "pgy_rows": 0, "jobs": 0})
        default.setdefault("hours", {})
        default.setdefault("last_access", {"xhs": "", "pgy": ""})
        return default

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            data = self.load()
        return self._with_current_hour(data)

    def record_job(self, *, xhs_rows: int = 0, pgy_rows: int = 0) -> dict[str, Any]:
        now = datetime.now().isoformat(timespec="seconds")
        with self._lock:
            data = self.load()
            hour = self._hour_key()
            hours = data.setdefault("hours", {})
            current = hours.setdefault(hour, {"xhs_rows": 0, "pgy_rows": 0, "jobs": 0})
            current["xhs_rows"] = int(current.get("xhs_rows", 0)) + int(xhs_rows or 0)
            current["pgy_rows"] = int(current.get("pgy_rows", 0)) + int(pgy_rows or 0)
            current["jobs"] = int(current.get("jobs", 0)) + 1
            totals = data.setdefault("totals", {"xhs_rows": 0, "pgy_rows": 0, "jobs": 0})
            totals["xhs_rows"] = int(totals.get("xhs_rows", 0)) + int(xhs_rows or 0)
            totals["pgy_rows"] = int(totals.get("pgy_rows", 0)) + int(pgy_rows or 0)
            totals["jobs"] = int(totals.get("jobs", 0)) + 1
            last_access = data.setdefault("last_access", {"xhs": "", "pgy": ""})
            if xhs_rows:
                last_access["xhs"] = now
            if pgy_rows:
                last_access["pgy"] = now
            path = self.today_path()
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
        return self._with_current_hour(data)

    def estimate_warnings(self, preview: SafetyPreview) -> list[str]:
        usage = self.snapshot()
        rows = int(preview.estimated_crawl_rows or 0)
        hour = usage.get("current_hour", {})
        totals = usage.get("totals", {})
        warnings: list[str] = []
        if preview.uses_xhs:
            hourly = int(hour.get("xhs_rows", 0)) + rows
            daily = int(totals.get("xhs_rows", 0)) + rows
            if hourly > self.policy.hourly_warning_xhs_rows:
                warnings.append(f"Estimated XHS rows this hour would reach {hourly}")
            if daily > self.policy.daily_warning_xhs_rows:
                warnings.append(f"Estimated XHS rows today would reach {daily}")
        if preview.uses_pgy:
            hourly = int(hour.get("pgy_rows", 0)) + rows
            daily = int(totals.get("pgy_rows", 0)) + rows
            if hourly > self.policy.hourly_warning_pgy_rows:
                warnings.append(f"Estimated Pugongying rows this hour would reach {hourly}")
            if daily > self.policy.daily_warning_pgy_rows:
                warnings.append(f"Estimated Pugongying rows today would reach {daily}")
        return warnings

    def estimate_errors(self, preview: SafetyPreview) -> list[str]:
        usage = self.snapshot()
        rows = int(preview.estimated_crawl_rows or 0)
        hour = usage.get("current_hour", {})
        totals = usage.get("totals", {})
        errors: list[str] = []
        if preview.uses_xhs and self.policy.enforce_xhs_hard_limit:
            hourly = int(hour.get("xhs_rows", 0)) + rows
            daily = int(totals.get("xhs_rows", 0)) + rows
            if hourly > self.policy.hourly_hard_xhs_rows:
                errors.append(f"XHS hourly hard limit exceeded: {hourly}/{self.policy.hourly_hard_xhs_rows}")
            if daily > self.policy.daily_hard_xhs_rows:
                errors.append(f"XHS daily hard limit exceeded: {daily}/{self.policy.daily_hard_xhs_rows}")
        if preview.uses_pgy and self.policy.enforce_pgy_hard_limit:
            hourly = int(hour.get("pgy_rows", 0)) + rows
            daily = int(totals.get("pgy_rows", 0)) + rows
            if hourly > self.policy.hourly_hard_pgy_rows:
                errors.append(f"Pugongying hourly hard limit exceeded: {hourly}/{self.policy.hourly_hard_pgy_rows}")
            if daily > self.policy.daily_hard_pgy_rows:
                errors.append(f"Pugongying daily hard limit exceeded: {daily}/{self.policy.daily_hard_pgy_rows}")
        return errors

    def enrich_preview(self, preview: SafetyPreview) -> SafetyPreview:
        preview.usage = self.snapshot()
        preview.warnings.extend(self.estimate_warnings(preview))
        preview.errors.extend(self.estimate_errors(preview))
        return preview

    def _with_current_hour(self, data: dict[str, Any]) -> dict[str, Any]:
        hour = self._hour_key()
        data = dict(data)
        data["current_hour_key"] = hour
        data["current_hour"] = data.get("hours", {}).get(hour, {"xhs_rows": 0, "pgy_rows": 0, "jobs": 0})
        data["path"] = str(self.today_path())
        return data
