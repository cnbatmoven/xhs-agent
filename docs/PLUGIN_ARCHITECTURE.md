# Plugin Architecture

This backend now has a thin plugin layer under `backend/plugins`.

The current goal is conservative: keep the proven XHS and Pugongying crawler usable while making each capability discoverable and replaceable by LangGraph nodes.

## Runtime Modes

- `legacy`: bypass LangGraph and call the original `xhs_note_agent.run`.
- `graph_legacy`: use LangGraph for orchestration, but still call the proven legacy runner for crawling and writing.
- `graph_split`: use LangGraph split nodes. Each split node calls a registered plugin handler.

For production jobs, keep `graph_legacy` as the default until `graph_split` has passed enough real crawl comparisons.

## Registered Plugins

Plugins are registered in `backend/plugins/xhs_builtin.py` and exposed through:

- `GET /api/v1/plugins`
- `GET /api/v1/plugins/{plugin_id}`

Current built-ins:

- `xhs.load_notes`: load note rows from the source workbook.
- `xhs.crawl_notes`: crawl XHS note content, cover, author, comments, and metrics.
- `xhs.rule_analysis`: classify content and generate rule-based suggestions.
- `pgy.pricing`: enrich creator rows with Pugongying price and CPE data.
- `llm.openai_compatible`: enrich rows with an OpenAI-compatible LLM API.
- `xhs.write_outputs`: write Excel and CSV outputs.

## Plugin Contract

A plugin handler is a callable:

```python
def handler(payload: dict[str, Any]) -> dict[str, Any]:
    ...
```

It should:

- Accept only structured values in `payload`.
- Return a dictionary with the outputs declared in `PluginSpec.outputs`.
- Avoid modifying unrelated files or global state.
- Raise normal exceptions for hard failures so the job runner can mark the job failed.
- Return `{"skipped": True}` when a node is intentionally skipped, such as disabled LLM or Pugongying.

## Adding A New Source

1. Create a new file under `backend/plugins`, for example `douyin_builtin.py`.
2. Implement handlers for loader, crawler, analyzer, and writer as needed.
3. Register each capability with `PluginSpec`.
4. Import and call the register function in `backend/plugins/__init__.py`.
5. Add LangGraph nodes or route existing generic nodes to the new plugin IDs.
6. Run:

```powershell
$py='C:\Users\15634\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -m py_compile backend\app.py backend\plugins\*.py backend\graphs\*.py
```

## Safety Notes

- High-risk plugins, such as `pgy.pricing`, should default to slow safe mode in UI workflows.
- Crawlers should respect `crawl_delay`, retry limits, and CDP reuse.
- Keep `legacy` and `graph_legacy` available until the replacement plugin has passed real crawl comparison.
- Use `tools/compare_execution_modes.py` after changing crawler behavior.
- Use `tools/retry_failed_records.py` to patch incomplete rows instead of rerunning a full batch.
