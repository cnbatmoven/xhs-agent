from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


PluginHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class PluginSpec:
    plugin_id: str
    name: str
    kind: str
    node: str
    description: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    risk_level: str = "low"
    enabled: bool = True
    handler: PluginHandler | None = None

    def public_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "kind": self.kind,
            "node": self.node,
            "description": self.description,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "risk_level": self.risk_level,
            "enabled": self.enabled,
        }


_REGISTRY: dict[str, PluginSpec] = {}


def register_plugin(spec: PluginSpec) -> PluginSpec:
    if spec.plugin_id in _REGISTRY:
        raise ValueError(f"duplicate plugin id: {spec.plugin_id}")
    _REGISTRY[spec.plugin_id] = spec
    return spec


def get_plugin(plugin_id: str) -> PluginSpec:
    try:
        return _REGISTRY[plugin_id]
    except KeyError as exc:
        raise KeyError(f"plugin not found: {plugin_id}") from exc


def list_plugins() -> list[dict[str, Any]]:
    return [spec.public_dict() for spec in sorted(_REGISTRY.values(), key=lambda item: item.plugin_id)]


def run_plugin(plugin_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    spec = get_plugin(plugin_id)
    if not spec.enabled:
        raise RuntimeError(f"plugin disabled: {plugin_id}")
    if spec.handler is None:
        raise RuntimeError(f"plugin has no handler: {plugin_id}")
    return spec.handler(payload)
