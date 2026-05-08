from __future__ import annotations

from .registry import get_plugin, list_plugins, run_plugin
from .xhs_builtin import register_builtin_plugins


register_builtin_plugins()

__all__ = ["get_plugin", "list_plugins", "run_plugin"]
