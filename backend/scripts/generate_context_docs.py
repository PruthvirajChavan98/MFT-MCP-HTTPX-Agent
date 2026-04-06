#!/usr/bin/env python3
"""Generate folder-level context docs and root handover context.

This script creates:
- `_context.md` for every leaf directory (excluding cache/venv/noise dirs)
- `_main_context.md` at repository root with session handover guidance

Why this exists:
- Keeps handover context deterministic and rebuildable
- Avoids one-off/manual documentation drift
- Supports constrained-context sessions by surfacing only relevant folders first
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

LEAF_CONTEXT_NAME = "_context.md"
MAIN_CONTEXT_NAME = "_main_context.md"

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    ".cache_nbfc_router",
    ".mypy_cache",
    "build",
    "dist",
    "__pycache__",
}
ALLOWED_DOT_DIRS = {".github"}
EXCLUDED_FILE_NAMES = {
    ".DS_Store",
    LEAF_CONTEXT_NAME,
    MAIN_CONTEXT_NAME,
}

LOCAL_IMPORT_PREFIXES = (
    "src.",
    "src",
    "agent_service.",
    "mcp_service.",
    "common.",
    "tests.",
)

ROLE_HINTS: dict[str, str] = {
    ".github/workflows": "CI workflow definitions and code-quality gate configuration.",
    "cloudflared": "Cloudflare tunnel configuration for edge ingress.",
    "data/geoip": "GeoIP data directory populated by updater jobs or setup scripts.",
    "infra/monitoring/grafana/dashboards": "Grafana dashboard JSON assets.",
    "infra/monitoring/grafana/provisioning/dashboards": "Grafana dashboard provisioning config.",
    "infra/monitoring/grafana/provisioning/datasources": "Grafana datasource provisioning config.",
    "infra/monitoring/prometheus": "Prometheus scrape and alert rule configuration.",
    "infra/nginx": "Nginx edge/TLS configuration.",
    "infra/sql": "PostgreSQL security/session schema and policy scripts.",
    "scripts": "Operational scripts for ingestion, local setup, and endpoint validation.",
    "src/agent_service/api/endpoints": "Public FastAPI endpoint handlers for agent-facing APIs.",
    "src/agent_service/core": "Core runtime orchestration, config, schemas, and shared service logic.",
    "src/agent_service/data": "Data-access configuration helpers.",
    "src/agent_service/eval_store": "Evaluation storage, embedding, and judge integration modules.",
    "src/agent_service/faqs": "FAQ parsing artifacts and ingest support assets.",
    "src/agent_service/features": "Feature flags/prototypes and answerability/follow-up behavior modules.",
    "src/agent_service/llm": "Model catalog and provider client orchestration.",
    "src/agent_service/features/routing": "NBFC router taxonomy, schemas, service, and worker runtime.",
    "src/agent_service/security": "Security middleware, runtime checks, metrics, and TOR/GeoIP controls.",
    "src/agent_service/tools": "Graph/tool adapters for knowledge and MCP integration.",
    "src/common": "Shared logging and connection management primitives.",
    "src/mcp_service": "MCP service APIs, session store, tool descriptions, and server runtime.",
    "tests": "Contract/unit coverage for API, streaming, router, MCP, and security behavior.",
}

PRIORITY_PREFIXES: list[tuple[str, str]] = [
    ("src/agent_service/api/endpoints", "high"),
    ("src/agent_service/core", "high"),
    ("src/agent_service/llm", "high"),
    ("src/agent_service/security", "high"),
    ("src/agent_service/tools", "high"),
    ("src/mcp_service", "high"),
    ("tests", "high"),
    ("src/", "medium"),
    ("scripts", "medium"),
    ("infra/", "medium"),
]

TODO_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b[:\s-]*(.*)", re.IGNORECASE)


@dataclass(frozen=True)
class FileSummary:
    rel_path: str
    name: str
    file_type: str
    summary: str
    key_symbols: list[str]
    local_imports: list[str]
    todo_markers: list[str]
    line_count: int


@dataclass(frozen=True)
class DirSnapshot:
    rel_dir: str
    child_dirs: list[str]
    files: list[str]


@dataclass(frozen=True)
class FolderContext:
    rel_dir: str
    role: str
    priority: str
    file_summaries: list[FileSummary]
    local_imports: list[str]
    todo_markers: list[str]


def _is_dir_allowed(name: str) -> bool:
    if name in EXCLUDED_DIR_NAMES:
        return False
    if name.startswith(".") and name not in ALLOWED_DOT_DIRS:
        return False
    return True


def _is_file_allowed(name: str) -> bool:
    if name in EXCLUDED_FILE_NAMES:
        return False
    if name.endswith((".pyc", ".pyo")):
        return False
    return True


def _as_posix_rel(path: Path, root: Path) -> str:
    rel = path.relative_to(root)
    if rel == Path("."):
        return "."
    return rel.as_posix()


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    except OSError:
        return None


def _first_non_empty_line(text: str) -> str:
    for raw in text.splitlines():
        line = raw.strip()
        if line:
            return line
    return ""


def _safe_md_cell(text: str) -> str:
    return text.replace("|", r"\|").replace("\n", " ").strip()


def _extract_todos(text: str, limit: int = 6) -> list[str]:
    markers: list[str] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        m = TODO_PATTERN.search(line)
        if not m:
            continue
        tag = m.group(1).upper()
        detail = m.group(2).strip()
        if detail:
            markers.append(f"L{idx}: {tag} {detail}")
        else:
            markers.append(f"L{idx}: {tag}")
        if len(markers) >= limit:
            break
    return markers


def _summarize_markdown(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    first = _first_non_empty_line(text)
    if first:
        return first[:140]
    return "Markdown document."


def _summarize_yaml(text: str) -> str:
    keys: list[str] = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t", "-")):
            continue
        m = re.match(r"([A-Za-z0-9_.-]+)\s*:", line.strip())
        if m:
            keys.append(m.group(1))
        if len(keys) >= 6:
            break
    if keys:
        return f"YAML config with top-level keys: {', '.join(keys)}."
    return "YAML configuration file."


def _summarize_json(text: str, file_size: int) -> str:
    if file_size > 1_500_000:
        return "Large JSON asset (skipped deep parse)."
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return "JSON-like file (parse failed)."
    if isinstance(parsed, dict):
        keys = list(parsed.keys())[:8]
        if keys:
            return f"JSON object with keys: {', '.join(map(str, keys))}."
        return "JSON object."
    if isinstance(parsed, list):
        return f"JSON array with {len(parsed)} items."
    return f"JSON scalar value of type `{type(parsed).__name__}`."


def _summarize_shell(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and not stripped.startswith("#!"):
            return stripped.lstrip("#").strip()
    return "Shell automation script."


def _summarize_sql(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        head = stripped.split()[0].upper()
        return f"SQL script starting with `{head}`."
    return "SQL script."


def _is_local_import(name: str) -> bool:
    return name.startswith(LOCAL_IMPORT_PREFIXES)


def _summarize_python(path: Path, text: str) -> tuple[str, list[str], list[str]]:
    try:
        module = ast.parse(text, filename=path.name)
    except SyntaxError:
        return "Python module (AST parse failed).", [], []

    doc = (ast.get_docstring(module) or "").strip()
    summary = _first_non_empty_line(doc) if doc else "Python module."

    key_symbols: list[str] = []
    local_imports: set[str] = set()

    for node in module.body:
        if isinstance(node, ast.ClassDef):
            key_symbols.append(f"class {node.name}")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            key_symbols.append(f"{prefix} {node.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if _is_local_import(name):
                    local_imports.add(name)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if node.level > 0:
                dots = "." * node.level
                name = f"{dots}{module_name}" if module_name else dots
                local_imports.add(name)
            elif _is_local_import(module_name):
                local_imports.add(module_name)

    return summary, key_symbols[:10], sorted(local_imports)


def _generic_summary(path: Path) -> str:
    stem = path.stem.replace("_", " ").replace("-", " ").strip()
    if stem:
        return f"{stem.title()} file."
    return "Project file."


def _file_type_for_suffix(path: Path) -> str:
    suffix = path.suffix.lower()
    mapping = {
        ".py": "python",
        ".md": "markdown",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".json": "json",
        ".sh": "shell",
        ".sql": "sql",
        ".toml": "toml",
        ".txt": "text",
        ".cypher": "cypher",
        ".conf": "config",
        ".ipynb": "notebook",
        ".pdf": "pdf",
    }
    return mapping.get(suffix, suffix.lstrip(".") or "file")


def _summarize_file(path: Path, root: Path) -> FileSummary:
    rel_path = _as_posix_rel(path, root)
    file_type = _file_type_for_suffix(path)
    text = _read_text(path)
    line_count = 0
    summary = _generic_summary(path)
    symbols: list[str] = []
    local_imports: list[str] = []
    todo_markers: list[str] = []

    if text is not None:
        line_count = len(text.splitlines())
        todo_markers = _extract_todos(text)
        suffix = path.suffix.lower()
        if suffix == ".py":
            summary, symbols, local_imports = _summarize_python(path, text)
        elif suffix == ".md":
            summary = _summarize_markdown(text)
        elif suffix in {".yml", ".yaml"}:
            summary = _summarize_yaml(text)
        elif suffix == ".json":
            try:
                file_size = path.stat().st_size
            except OSError:
                file_size = 0
            summary = _summarize_json(text, file_size)
        elif suffix == ".sh":
            summary = _summarize_shell(text)
        elif suffix in {".sql", ".cypher"}:
            summary = _summarize_sql(text)
        else:
            first = _first_non_empty_line(text)
            if first:
                summary = first[:160]

    return FileSummary(
        rel_path=rel_path,
        name=path.name,
        file_type=file_type,
        summary=summary,
        key_symbols=symbols,
        local_imports=local_imports,
        todo_markers=todo_markers,
        line_count=line_count,
    )


def _collect_tree(root: Path) -> dict[str, DirSnapshot]:
    snapshots: dict[str, DirSnapshot] = {}

    for current_root, dirs, files in os.walk(root, topdown=True):
        current_path = Path(current_root)
        rel_dir = _as_posix_rel(current_path, root)

        dirs[:] = sorted(d for d in dirs if _is_dir_allowed(d))
        kept_files = sorted(f for f in files if _is_file_allowed(f))

        child_dirs = []
        for name in dirs:
            child = current_path / name
            child_dirs.append(_as_posix_rel(child, root))

        rel_files = []
        for name in kept_files:
            rel_files.append(_as_posix_rel(current_path / name, root))

        snapshots[rel_dir] = DirSnapshot(
            rel_dir=rel_dir,
            child_dirs=child_dirs,
            files=rel_files,
        )

    return snapshots


def _role_for_folder(rel_dir: str) -> str:
    if rel_dir in ROLE_HINTS:
        return ROLE_HINTS[rel_dir]
    for prefix, role in ROLE_HINTS.items():
        if rel_dir.startswith(prefix + "/"):
            return role
    return "Leaf project folder."


def _priority_for_folder(rel_dir: str) -> str:
    for prefix, priority in PRIORITY_PREFIXES:
        if rel_dir.startswith(prefix):
            return priority
    return "low"


def _build_folder_context(root: Path, snapshot: DirSnapshot) -> FolderContext:
    file_paths = [root / file_rel for file_rel in snapshot.files]
    file_summaries = [_summarize_file(path, root) for path in file_paths]

    imports: set[str] = set()
    todo_markers: list[str] = []

    for file_summary in file_summaries:
        imports.update(file_summary.local_imports)
        for marker in file_summary.todo_markers:
            todo_markers.append(f"{file_summary.name}: {marker}")

    return FolderContext(
        rel_dir=snapshot.rel_dir,
        role=_role_for_folder(snapshot.rel_dir),
        priority=_priority_for_folder(snapshot.rel_dir),
        file_summaries=sorted(file_summaries, key=lambda item: item.name),
        local_imports=sorted(imports),
        todo_markers=todo_markers[:12],
    )


def _render_leaf_context(ctx: FolderContext) -> str:
    lines: list[str] = []
    lines.append(f"# Context: `{ctx.rel_dir}`")
    lines.append("")
    lines.append("## Folder Snapshot")
    lines.append(f"- Path: `{ctx.rel_dir}`")
    lines.append(f"- Role: {ctx.role}")
    lines.append(f"- Priority: `{ctx.priority}`")
    lines.append("- Generated by: `scripts/generate_context_docs.py`")
    lines.append("- Regenerate: `make context-docs`")
    lines.append("")
    lines.append("## File Inventory")
    lines.append("| File | Type | Purpose | Key Symbols |")
    lines.append("| --- | --- | --- | --- |")

    if ctx.file_summaries:
        for file_summary in ctx.file_summaries:
            symbols = ", ".join(file_summary.key_symbols[:5]) if file_summary.key_symbols else "-"
            purpose = _safe_md_cell(file_summary.summary)
            lines.append(
                "| "
                + f"`{file_summary.name}`"
                + " | "
                + f"`{file_summary.file_type}`"
                + " | "
                + purpose
                + " | "
                + _safe_md_cell(symbols)
                + " |"
            )
    else:
        lines.append("| _No files currently tracked in this leaf folder_ | - | - | - |")

    lines.append("")
    lines.append("## Internal Dependencies")
    if ctx.local_imports:
        for name in ctx.local_imports:
            lines.append(f"- `{name}`")
    else:
        lines.append("- No local Python imports detected in this folder.")

    lines.append("")
    lines.append("## TODO / Risk Markers")
    if ctx.todo_markers:
        for marker in ctx.todo_markers:
            lines.append(f"- {marker}")
    else:
        lines.append("- No TODO/FIXME/HACK markers detected.")

    lines.append("")
    lines.append("## Session Handover Notes")
    lines.append("1. Work completed in this folder:")
    lines.append("2. Interfaces changed (APIs/schemas/config):")
    lines.append("3. Tests run and evidence:")
    lines.append("4. Open risks or blockers:")
    lines.append("5. Next folder to process:")
    lines.append("")
    return "\n".join(lines)


def _render_main_context(
    leaf_contexts: list[FolderContext],
    non_leaf_with_files: list[DirSnapshot],
) -> str:
    total_files = sum(len(ctx.file_summaries) for ctx in leaf_contexts)
    lines: list[str] = []
    lines.append("# Main Context Handover")
    lines.append("")
    lines.append("## Snapshot")
    lines.append("- Generated by: `scripts/generate_context_docs.py`")
    lines.append(f"- Leaf folders tracked: `{len(leaf_contexts)}`")
    lines.append(f"- Files indexed in leaf folders: `{total_files}`")
    lines.append("- Generation command: `make context-docs`")
    lines.append("")
    lines.append("## Context-Constrained Session Strategy")
    lines.append("1. Read this file first to choose scope.")
    lines.append("2. Open only the relevant leaf `_context.md` files for touched folders.")
    lines.append("3. Open raw source files only inside those touched leaf folders.")
    lines.append("4. After each folder is completed, rerun `make context-docs`.")
    lines.append("5. Append a concise delta summary to your master context artifact.")
    lines.append("")
    lines.append("## Master Context Build Plan")
    lines.append("1. Process one leaf folder at a time (see index below).")
    lines.append(
        "2. For each folder, capture: changed files, interface impact, test proof, open risks."
    )
    lines.append("3. Re-run `make context-docs` immediately after folder completion.")
    lines.append("4. Fold each folder delta into a running `MASTER_CONTEXT.md` summary.")
    lines.append(
        "5. Keep `MASTER_CONTEXT.md` under a strict token budget by storing links, not code."
    )
    lines.append("")
    lines.append("## Leaf Folder Index")
    lines.append("| Folder | Priority | Role | Files | Context |")
    lines.append("| --- | --- | --- | --- | --- |")
    for ctx in leaf_contexts:
        context_path = f"{ctx.rel_dir}/{LEAF_CONTEXT_NAME}"
        lines.append(
            "| "
            + f"`{ctx.rel_dir}`"
            + " | "
            + f"`{ctx.priority}`"
            + " | "
            + _safe_md_cell(ctx.role)
            + " | "
            + f"`{len(ctx.file_summaries)}`"
            + " | "
            + f"`{context_path}`"
            + " |"
        )

    lines.append("")
    lines.append("## Non-Leaf Files (Covered Here)")
    lines.append(
        "These directories have both files and child folders, so they do not receive leaf `_context.md` files."
    )
    lines.append("| Directory | Files |")
    lines.append("| --- | --- |")
    if non_leaf_with_files:
        for snap in non_leaf_with_files:
            file_names = ", ".join(f"`{Path(f).name}`" for f in snap.files)
            lines.append(f"| `{snap.rel_dir}` | {file_names} |")
    else:
        lines.append("| _None_ | _None_ |")

    lines.append("")
    lines.append("## Session Handover Template")
    lines.append("1. Scope for next session:")
    lines.append("2. Folder(s) completed this session:")
    lines.append("3. Interfaces changed:")
    lines.append("4. Tests/lint/type checks run:")
    lines.append("5. Risks, debt, and immediate next step:")
    lines.append("")
    return "\n".join(lines)


def _write_if_changed(path: Path, content: str, check: bool) -> bool:
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if current == content:
        return False
    if not check:
        path.write_text(content, encoding="utf-8")
    return True


def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate `_context.md` files for leaf folders and `_main_context.md` at repo root."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root directory (defaults to script parent parent).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write files; fail if generated output differs from current files.",
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    root = args.root.resolve()
    if not root.exists():
        print(f"error: root path does not exist: {root}", file=sys.stderr)
        return 2

    snapshots = _collect_tree(root)
    leaf_snapshots = sorted(
        (snap for snap in snapshots.values() if snap.rel_dir != "." and len(snap.child_dirs) == 0),
        key=lambda item: item.rel_dir,
    )
    folder_contexts = [_build_folder_context(root, snap) for snap in leaf_snapshots]

    non_leaf_with_files = sorted(
        (
            snap
            for snap in snapshots.values()
            if snap.rel_dir != "." and snap.child_dirs and snap.files
        ),
        key=lambda item: item.rel_dir,
    )

    changed_files = 0

    for ctx in folder_contexts:
        output_path = root / ctx.rel_dir / LEAF_CONTEXT_NAME
        content = _render_leaf_context(ctx)
        if _write_if_changed(output_path, content, args.check):
            changed_files += 1

    main_context_path = root / MAIN_CONTEXT_NAME
    main_context_content = _render_main_context(folder_contexts, non_leaf_with_files)
    if _write_if_changed(main_context_path, main_context_content, args.check):
        changed_files += 1

    mode = "CHECK" if args.check else "WRITE"
    print(
        f"[{mode}] leaf_folders={len(folder_contexts)} changed_files={changed_files} "
        f"main_context={main_context_path.name}"
    )

    if args.check and changed_files > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
