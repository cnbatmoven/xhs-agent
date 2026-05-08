from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from .nodes import (
    analyze_rules_node,
    crawl_pgy_node,
    crawl_xhs_node,
    llm_analyze_node,
    parse_intent_node,
    load_notes_node,
    plan_steps_node,
    preview_node,
    run_legacy_agent_node,
    summarize_node,
    validate_input_node,
    write_outputs_node,
)
from .state import JobState


def preview_xhs_analysis_plan(initial_state: JobState) -> JobState:
    state = parse_intent_node(initial_state)
    state = plan_steps_node(state)
    return state


def build_xhs_analysis_graph():
    graph = StateGraph(JobState)
    graph.add_node("parse_intent", parse_intent_node)
    graph.add_node("plan_steps", plan_steps_node)
    graph.add_node("validate_input", validate_input_node)
    graph.add_node("load_notes", load_notes_node)
    graph.add_node("run_legacy_agent", run_legacy_agent_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("preview", preview_node)

    graph.add_edge(START, "parse_intent")
    graph.add_edge("parse_intent", "plan_steps")
    graph.add_edge("plan_steps", "validate_input")
    graph.add_edge("validate_input", "load_notes")
    graph.add_edge("load_notes", "run_legacy_agent")
    graph.add_edge("run_legacy_agent", "summarize")
    graph.add_edge("summarize", "preview")
    graph.add_edge("preview", END)
    return graph.compile()


def build_xhs_split_graph():
    graph = StateGraph(JobState)
    graph.add_node("parse_intent", parse_intent_node)
    graph.add_node("plan_steps", plan_steps_node)
    graph.add_node("validate_input", validate_input_node)
    graph.add_node("load_notes", load_notes_node)
    graph.add_node("crawl_xhs", crawl_xhs_node)
    graph.add_node("analyze_rules", analyze_rules_node)
    graph.add_node("crawl_pgy", crawl_pgy_node)
    graph.add_node("llm_analyze", llm_analyze_node)
    graph.add_node("write_outputs", write_outputs_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("preview", preview_node)

    graph.add_edge(START, "parse_intent")
    graph.add_edge("parse_intent", "plan_steps")
    graph.add_edge("plan_steps", "validate_input")
    graph.add_edge("validate_input", "load_notes")
    graph.add_edge("load_notes", "crawl_xhs")
    graph.add_edge("crawl_xhs", "analyze_rules")
    graph.add_edge("analyze_rules", "crawl_pgy")
    graph.add_edge("crawl_pgy", "llm_analyze")
    graph.add_edge("llm_analyze", "write_outputs")
    graph.add_edge("write_outputs", "summarize")
    graph.add_edge("summarize", "preview")
    graph.add_edge("preview", END)
    return graph.compile()


def run_xhs_analysis_graph(
    initial_state: JobState,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
    split: bool = False,
) -> JobState:
    app = build_xhs_split_graph() if split else build_xhs_analysis_graph()
    final_state: JobState = dict(initial_state)
    config = {"configurable": {"thread_id": initial_state["job_id"]}}
    for event in app.stream(initial_state, config=config):
        for node_name, payload in event.items():
            if isinstance(payload, dict):
                final_state.update(payload)
                if on_event:
                    on_event(node_name, payload)
    return final_state
