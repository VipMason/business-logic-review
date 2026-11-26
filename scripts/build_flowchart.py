#!/usr/bin/env python3
"""Build, verify, and self-test offline Simplified Chinese HTML flowcharts."""

from __future__ import annotations

import argparse
import copy
import html
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ALLOWED_TONES = {"blue", "teal", "amber", "red"}
ALLOWED_LEGEND_KEYS = {"blue", "teal", "amber", "red"}
ALLOWED_CHECK_KEYS = {"compositeState", "asyncExternal", "failureBranch", "proseOnly", "fullDocument"}
REQUIRED_NODE_FIELDS = ("id", "title", "role", "place", "action", "logic", "result", "tone")
PLACEHOLDER_RE = re.compile(r"\{\{[A-Z0-9_]+\}\}")
DATA_SCRIPT_RE = re.compile(
    r'(<script\s+id="flowchart-data"\s+type="application/json">\s*)(.*?)(\s*</script>)',
    re.DOTALL,
)
TITLE_RE = re.compile(r"<title>.*?</title>", re.DOTALL)
STEP_SUFFIX = r"[0-9]+[A-Za-z0-9]*(?:[-_][0-9]+[A-Za-z0-9]*)*"
STEP_PREFIX_RE = re.compile(rf"([A-Za-z]+){STEP_SUFFIX}\Z")
STEP_TOKEN_RE = re.compile(rf"(?<![A-Za-z0-9_-])([A-Za-z]+{STEP_SUFFIX})(?![A-Za-z0-9_-])")
META_AUDIT_RE = re.compile(r"(?:分实体核验|核验完成状态|确认闭环|逐项核验)")
FAILURE_CUE_RE = re.compile(r"(?:异常|失败|驳回|拒绝|超时|失效|退款|冲突|阻断|挂账|未匹配|未回执|退回)")
ASYNC_EXTERNAL_RE = re.compile(r"(?:异步|回调|T\+1|定时任务|消息队列|MQ|webhook|HIS|支付网关|第三方回执)", re.IGNORECASE)
COMPOSITE_STATE_RE = re.compile(r"(?:状态机|状态流转|复合状态|status\s*[=:]|状态\s*[0-9\-]+)", re.IGNORECASE)
NEGATED_CLAUSE_RE = re.compile(r"(?:不涉及|不包含|未涉及|无需|不走|并非|没有|非)[^。；;！!\n，,]{0,40}")
WILDCARD_GLOB_RE = re.compile(r"`[^`\s]*/\*`")
EXACT_LINE_LOC_RE = re.compile(r"\.[A-Za-z0-9]{1,6}:\d+")
MERMAID_UNQUOTED_PAREN_RE = re.compile(r'\[(?!")[^\]\n]*[()（）][^\]\n]*\]')
RECAP_HEADING_RE = re.compile(r"(?m)^#{1,6}[ \t]+(?:[0-9]+[.、][ \t]*)?(?:口述回顾|口头复述)(?:[ \t]+#+)?[ \t]*$")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
MD_STEP_HEADING_RE = re.compile(
    rf"(?m)^[ ]{{0,3}}(?P<marker>#{{1,6}}[ \t]+|\*\*)(?P<id>[A-Za-z]+{STEP_SUFFIX})"
    r"(?:[ \t:：.、\-]+)(?P<title>[^\r\n]+)"
)
STOP_CJK_CHARS = set("的与和或及在并了为按对")


def _strip_negated_clauses(text: str) -> str:
    """Remove Chinese negated clauses before advisory keyword matching."""
    return NEGATED_CLAUSE_RE.sub("", text)


FENCE_OPEN_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")
FENCE_CLOSE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*$")
TITLE_TYPO_TRANS = str.maketrans({
    "（": "(",
    "）": ")",
    "：": ":",
    "／": "/",
    "，": ",",
    "；": ";",
    "、": ",",
    "－": "-",
    "—": "-",
    "　": " ",
})
TITLE_WHITESPACE_RE = re.compile(r"\s+")


def _parse_markdown_fences(md_text: str) -> tuple[str, list[str]]:
    """Split Markdown into text outside fenced code blocks and top-level mermaid blocks."""
    outside_lines: list[str] = []
    mermaid_blocks: list[str] = []
    fence_char: str | None = None
    fence_len = 0
    fence_lang = ""
    block_lines: list[str] = []

    for line in md_text.splitlines():
        if fence_char is None:
            m = FENCE_OPEN_RE.match(line)
            if m:
                marker, info = m.group(1), m.group(2)
                if marker[0] == "`" and "`" in info:
                    outside_lines.append(line)
                    continue
                fence_char = marker[0]
                fence_len = len(marker)
                tokens = info.strip().split()
                fence_lang = tokens[0].lower() if tokens else ""
                block_lines = []
            else:
                outside_lines.append(line)
        else:
            mc = FENCE_CLOSE_RE.match(line)
            if mc and mc.group(1)[0] == fence_char and len(mc.group(1)) >= fence_len:
                if fence_lang == "mermaid":
                    mermaid_blocks.append("\n".join(block_lines))
                fence_char = None
                fence_len = 0
                fence_lang = ""
                block_lines = []
            else:
                block_lines.append(line)

    if fence_char is not None and fence_lang == "mermaid":
        mermaid_blocks.append("\n".join(block_lines))

    return "\n".join(outside_lines), mermaid_blocks


def _mermaid_diagram_type(block: str) -> str:
    """Return 'state', 'sequence', 'flowchart', or 'other' from the first active Mermaid directive."""
    lines = block.splitlines()
    idx = 0
    while idx < len(lines) and (not lines[idx].strip() or lines[idx].strip().startswith("%%")):
        idx += 1
    if idx < len(lines) and lines[idx].strip() == "---":
        idx += 1
        while idx < len(lines) and lines[idx].strip() != "---":
            idx += 1
        if idx < len(lines):
            idx += 1
    while idx < len(lines):
        stripped = lines[idx].strip()
        if not stripped or stripped.startswith("%%"):
            idx += 1
            continue
        if re.match(r"^stateDiagram(?:-v2)?\b", stripped, re.IGNORECASE):
            return "state"
        if re.match(r"^sequenceDiagram\b", stripped, re.IGNORECASE):
            return "sequence"
        if re.match(r"^(?:flowchart|graph)\b", stripped, re.IGNORECASE):
            return "flowchart"
        return "other"
    return "other"


def _normalize_step_title(text: str) -> str:
    """Normalize a step title for exact equality (typography/whitespace/case only; preserve business words & parentheses)."""
    cleaned = text.translate(TITLE_TYPO_TRANS)
    cleaned = TITLE_WHITESPACE_RE.sub("", cleaned)
    return cleaned.lower()


def _meaningful_tokens(text: str) -> set[str]:
    """Extract meaningful CJK characters and alphanumeric words for title alignment."""
    tokens = {ch for ch in CJK_RE.findall(text) if ch not in STOP_CJK_CHARS}
    tokens.update(w.lower() for w in re.findall(r"[A-Za-z0-9]{2,}", text))
    return tokens

EXTERNAL_DEPENDENCY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("external <script src=...>", re.compile(r"<script[^>]+src=", re.IGNORECASE)),
    ("external http(s) <link>", re.compile(r"""<link[^>]+href\s*=\s*["']https?:""", re.IGNORECASE)),
    ("external http(s) <img>", re.compile(r"""<img[^>]+src\s*=\s*["']https?:""", re.IGNORECASE)),
    ("CSS @import rule", re.compile(r"@import\s+", re.IGNORECASE)),
    ("external CSS url(http...)", re.compile(r"""url\(\s*["']?https?:""", re.IGNORECASE)),
    ("runtime fetch() call", re.compile(r"\bfetch\s*\(")),
    ("runtime XMLHttpRequest usage", re.compile(r"\bXMLHttpRequest\b")),
)


def _walk_strings(value: Any, path: str = "$") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, str):
        found.append((path, value))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            found.extend(_walk_strings(item, f"{path}[{idx}]"))
    elif isinstance(value, dict):
        for k, v in value.items():
            found.extend(_walk_strings(v, f"{path}.{k}"))
    return found


def validate_data(data: Any) -> tuple[list[str], dict[str, int]]:
    """Validate flowchart JSON schema and return (node_ids, tone_counts)."""
    errors: list[str] = []
    if not isinstance(data, dict):
        raise ValueError("Root JSON value must be an object.")

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("Field 'title' must be a non-empty string.")

    for opt_field in ("subtitle", "statusNote", "footer"):
        if opt_field in data and data[opt_field] is not None and not isinstance(data[opt_field], str):
            errors.append(f"Optional field '{opt_field}' must be a string when provided.")

    if "legend" in data and data["legend"] is not None:
        legend = data["legend"]
        if not isinstance(legend, dict):
            errors.append("Optional field 'legend' must be an object.")
        else:
            bad_keys = set(legend.keys()) - ALLOWED_LEGEND_KEYS
            if bad_keys:
                errors.append(f"Invalid 'legend' keys: {sorted(bad_keys)}. Allowed: {sorted(ALLOWED_LEGEND_KEYS)}.")
            for k, v in legend.items():
                if not isinstance(v, str) or not v.strip():
                    errors.append(f"'legend.{k}' must be a non-empty string.")

    if "checks" in data and data["checks"] is not None:
        checks = data["checks"]
        if not isinstance(checks, dict):
            errors.append("Optional field 'checks' must be an object.")
        else:
            bad_keys = set(checks.keys()) - ALLOWED_CHECK_KEYS
            if bad_keys:
                errors.append(f"Invalid 'checks' keys: {sorted(bad_keys)}. Allowed: {sorted(ALLOWED_CHECK_KEYS)}.")
            for k, v in checks.items():
                if not isinstance(v, bool):
                    errors.append(f"'checks.{k}' must be a boolean.")

    views = data.get("views")
    if not isinstance(views, list) or not views:
        errors.append("Field 'views' must be a non-empty list.")
        views = []

    next_by_id = data.get("nextById")
    if not isinstance(next_by_id, dict):
        errors.append("Field 'nextById' must be an object mapping node IDs to handoff descriptions.")
        next_by_id = {}

    stage_ids: set[str] = set()
    node_ids: list[str] = []
    seen_node_ids: set[str] = set()
    tone_counts: dict[str, int] = {t: 0 for t in ALLOWED_TONES}

    for v_idx, view in enumerate(views):
        v_loc = f"views[{v_idx}]"
        if not isinstance(view, dict):
            errors.append(f"{v_loc} must be an object.")
            continue
        vid = view.get("id")
        vtitle = view.get("title")
        if not isinstance(vid, str) or not vid.strip():
            errors.append(f"{v_loc}.id must be a non-empty string.")
        elif vid in stage_ids:
            errors.append(f"Duplicate stage id: '{vid}'.")
        else:
            stage_ids.add(vid)
        if not isinstance(vtitle, str) or not vtitle.strip():
            errors.append(f"{v_loc}.title must be a non-empty string.")

        columns = view.get("columns")
        if not isinstance(columns, list) or not columns:
            errors.append(f"{v_loc}.columns must be a non-empty list.")
            continue

        for c_idx, col in enumerate(columns):
            c_loc = f"{v_loc}.columns[{c_idx}]"
            if not isinstance(col, dict):
                errors.append(f"{c_loc} must be an object.")
                continue
            if not isinstance(col.get("title"), str) or not col["title"].strip():
                errors.append(f"{c_loc}.title must be a non-empty string.")

            lanes = col.get("lanes")
            if not isinstance(lanes, list) or not lanes:
                errors.append(f"{c_loc}.lanes must be a non-empty list.")
                continue

            for l_idx, lane in enumerate(lanes):
                l_loc = f"{c_loc}.lanes[{l_idx}]"
                if not isinstance(lane, dict):
                    errors.append(f"{l_loc} must be an object.")
                    continue
                if not isinstance(lane.get("name"), str) or not lane["name"].strip():
                    errors.append(f"{l_loc}.name must be a non-empty string.")

                nodes = lane.get("nodes")
                if not isinstance(nodes, list) or not nodes:
                    errors.append(f"{l_loc}.nodes must be a non-empty list.")
                    continue

                for n_idx, node in enumerate(nodes):
                    n_loc = f"{l_loc}.nodes[{n_idx}]"
                    if not isinstance(node, dict):
                        errors.append(f"{n_loc} must be an object.")
                        continue

                    for field in REQUIRED_NODE_FIELDS:
                        val = node.get(field)
                        if not isinstance(val, str) or not val.strip():
                            errors.append(f"{n_loc}.{field} must be a non-empty string.")

                    nid = node.get("id")
                    if isinstance(nid, str) and nid.strip():
                        if not STEP_PREFIX_RE.fullmatch(nid):
                            errors.append(f"{n_loc}.id must be a step ID such as S01, S01a, or S02-1.")
                        elif nid in seen_node_ids:
                            errors.append(f"Duplicate node id: '{nid}'.")
                        else:
                            seen_node_ids.add(nid)
                            node_ids.append(nid)

                    tone = node.get("tone")
                    if isinstance(tone, str) and tone.strip():
                        if tone not in ALLOWED_TONES:
                            errors.append(f"{n_loc}.tone '{tone}' is invalid. Allowed: {sorted(ALLOWED_TONES)}.")
                        else:
                            tone_counts[tone] += 1

    if not node_ids:
        errors.append("Flowchart must contain at least one node.")

    node_prefixes: set[str] = set()
    for nid in node_ids:
        pm = STEP_PREFIX_RE.match(nid)
        if pm:
            node_prefixes.add(pm.group(1))

    for nid in node_ids:
        handoff = next_by_id.get(nid)
        if not isinstance(handoff, str) or not handoff.strip():
            errors.append(f"Missing or empty nextById entry for node '{nid}'.")
        elif node_prefixes:
            for m in STEP_TOKEN_RE.finditer(handoff):
                tok = m.group(1)
                tok_pm = STEP_PREFIX_RE.match(tok)
                if tok_pm and tok_pm.group(1) in node_prefixes and tok not in seen_node_ids:
                    errors.append(f"Broken step reference '{tok}' in nextById['{nid}'].")

    orphan_keys = sorted(set(next_by_id.keys()) - seen_node_ids)
    if orphan_keys:
        errors.append(f"Orphan nextById keys with no matching node: {orphan_keys}.")

    for path, text in _walk_strings(data):
        match = PLACEHOLDER_RE.search(text)
        if match:
            errors.append(f"Unreplaced placeholder '{match.group(0)}' found at {path}.")

    if errors:
        raise ValueError("\n".join(f"- {err}" for err in errors))

    return node_ids, tone_counts


def escape_json_for_html(data: Any) -> str:
    """Serialize JSON safely for embedding inside a <script> tag."""
    dumped = json.dumps(data, ensure_ascii=False, indent=2)
    return dumped.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _resolve_checks(
    data: dict[str, Any],
    *,
    prose_only: bool = False,
    has_composite_state: bool = False,
    has_async_handoff: bool = False,
    has_failure_branch: bool = False,
) -> dict[str, bool | None]:
    raw_checks = data.get("checks") if isinstance(data.get("checks"), dict) else {}
    return {
        "compositeState": True if has_composite_state else raw_checks.get("compositeState"),
        "asyncExternal": True if has_async_handoff else raw_checks.get("asyncExternal"),
        "failureBranch": True if has_failure_branch else raw_checks.get("failureBranch"),
        "proseOnly": True if prose_only else raw_checks.get("proseOnly"),
        "fullDocument": raw_checks.get("fullDocument"),
    }


def collect_layout_checks(
    data: dict[str, Any],
    node_ids: list[str],
    tone_counts: dict[str, int],
    resolved_checks: dict[str, bool | None],
) -> tuple[list[str], list[str]]:
    """Collect deterministic layout warnings and non-blocking heuristic hints."""
    warnings: list[str] = []
    hints: list[str] = []
    views = data.get("views", [])
    next_by_id = data.get("nextById", {})
    single_node_stages: list[str] = []
    stage_first_nodes: set[str] = set()
    all_nodes: list[dict[str, Any]] = []

    for view in views:
        v_id = view.get("id", "?")
        stage_node_count = 0
        for c_idx, col in enumerate(view.get("columns", [])):
            col_title = col.get("title", "?")
            seen_lanes: set[str] = set()
            dups: list[str] = []
            for lane in col.get("lanes", []):
                nodes = lane.get("nodes", [])
                stage_node_count += len(nodes)
                if c_idx == 0 and nodes and isinstance(nodes[0].get("id"), str):
                    stage_first_nodes.add(nodes[0]["id"])
                for n in nodes:
                    all_nodes.append(n)
                lname = str(lane.get("name", "")).strip()
                if lname in seen_lanes and lname not in dups:
                    dups.append(lname)
                seen_lanes.add(lname)
            if dups:
                warnings.append(
                    f"Stage '{v_id}' column '{col_title}' has duplicate lane names {dups}; "
                    "merge consecutive same-role steps into one lane so vertical arrows render."
                )
        if stage_node_count == 1:
            single_node_stages.append(str(v_id))

    if len(views) >= 3 and single_node_stages:
        hints.append(
            f"Single-node orphan stages detected {single_node_stages}; keep sequential steps within the same "
            "branch as adjacent columns in one stage (typically 2-5 columns) and only split independent parallel branches."
        )

    if resolved_checks.get("failureBranch") is None and tone_counts.get("red", 0) == 0:
        has_failure_handoff = any(
            FAILURE_CUE_RE.search(_strip_negated_clauses(str(v))) for v in next_by_id.values()
        )
        failure_node_hits = sum(
            1 for n in all_nodes
            if FAILURE_CUE_RE.search(_strip_negated_clauses(f"{n.get('logic', '')} {n.get('result', '')}"))
        )
        if has_failure_handoff or failure_node_hits >= 2:
            hints.append(
                "Flow text mentions failure/rejection/timeout cues without 'red' nodes; if failure branches exist, "
                "color them 'red' and declare checks.failureBranch=true (or false if none exist)."
            )

    meta_audit_ids = [
        n["id"] for n in all_nodes
        if META_AUDIT_RE.search(str(n.get("title", "")))
    ]
    if meta_audit_ids:
        hints.append(
            f"Synthetic meta-audit node title detected on {meta_audit_ids}; consider representing only real business "
            "actions, triggers, decisions, or failure branches."
        )

    if all_nodes:
        last_node = all_nodes[-1]
        if (
            last_node.get("tone") == "red"
            and not FAILURE_CUE_RE.search(f"{last_node.get('title', '')} {last_node.get('logic', '')}")
        ):
            hints.append(
                f"Final node '{last_node.get('id')}' is colored 'red' without failure/exception cues; "
                "reserve 'red' for concrete failure branches rather than unverified backend behavior."
            )

    if len(node_ids) >= 3:
        referenced: set[str] = set()
        id_set = set(node_ids)
        for src_id, handoff in next_by_id.items():
            for tok in STEP_TOKEN_RE.findall(str(handoff)):
                if tok != src_id and tok in id_set:
                    referenced.add(tok)
        unlinked = [nid for nid in node_ids if nid not in stage_first_nodes and nid not in referenced]
        if unlinked:
            hints.append(
                f"Unlinked nodes not referenced in nextById {unlinked}; mention target step IDs in nextById "
                "so card route pills and jump buttons stay connected."
            )

    return warnings, hints


def collect_markdown_checks(
    outside_md: str,
    mermaid_blocks: list[str],
    data: dict[str, Any],
    resolved_checks: dict[str, bool | None],
    has_state_diagram: bool,
    has_sequence_diagram: bool,
) -> tuple[list[str], list[str]]:
    """Collect deterministic Markdown warnings and non-blocking heuristic hints."""
    warnings: list[str] = []
    hints: list[str] = []

    if not resolved_checks.get("proseOnly"):
        combined_stripped = _strip_negated_clauses(
            outside_md + "\n" + "\n".join(text for _, text in _walk_strings(data))
        )
        if resolved_checks.get("compositeState") is None and not has_state_diagram:
            if COMPOSITE_STATE_RE.search(combined_stripped):
                hints.append(
                    "Detected composite-state cues without a Mermaid stateDiagram/stateDiagram-v2; "
                    "declare checks.compositeState=true and add one if applicable (or false if not)."
                )
        if resolved_checks.get("asyncExternal") is None and not has_sequence_diagram:
            if ASYNC_EXTERNAL_RE.search(combined_stripped):
                hints.append(
                    "Detected async/external handoff cues without a Mermaid sequenceDiagram; "
                    "declare checks.asyncExternal=true and add one if applicable (or false if not)."
                )

    globs = WILDCARD_GLOB_RE.findall(outside_md)
    exact_locs = EXACT_LINE_LOC_RE.findall(outside_md)
    if len(globs) >= 2 and len(exact_locs) < 3:
        hints.append(
            f"Markdown relies on wildcard path globs ({len(globs)} found) with only {len(exact_locs)} exact "
            "file:line locators; cite exact path:line locations for material rules and guards when code is in scope."
        )

    bad_mermaid = 0
    for block in mermaid_blocks:
        if MERMAID_UNQUOTED_PAREN_RE.search(block):
            bad_mermaid += 1
    if bad_mermaid:
        warnings.append(
            f"Found unquoted parentheses inside Mermaid bracket labels in {bad_mermaid} diagram block(s); "
            'quote labels like A1["文本（补充）"] to avoid Mermaid parse errors.'
        )

    recap_match = RECAP_HEADING_RE.search(outside_md)
    if resolved_checks.get("fullDocument"):
        if not re.search(r"(?m)^#{1,6}[ \t]+项目全业务串讲(?:[ \t]+#+)?[ \t]*$", outside_md):
            hints.append("Complete project Markdown should include the heading '项目全业务串讲'.")
        if not re.search(r"(?m)^#{1,6}[ \t]+(?:[0-9]+[.、][ \t]*)?口述回顾(?:[ \t]+#+)?[ \t]*$", outside_md):
            hints.append("Complete project Markdown should include the heading '口述回顾'.")
    if recap_match:
        tail = outside_md[recap_match.end():].lstrip("\r\n")
        para_lines: list[str] = []
        for line in tail.splitlines():
            stripped = line.strip()
            if not stripped:
                if para_lines:
                    break
                continue
            if stripped.startswith("#"):
                break
            para_lines.append(stripped)
        cjk_count = len(CJK_RE.findall(" ".join(para_lines)))
        if cjk_count > 100:
            warnings.append(
                f"Spoken recap section has {cjk_count} Chinese characters (target <= 100)."
            )

    return warnings, hints


def verify_html_file(
    html_path: Path,
    markdown_path: Path | None = None,
    *,
    prose_only: bool = False,
    has_composite_state: bool = False,
    has_async_handoff: bool = False,
    has_failure_branch: bool = False,
) -> tuple[int, list[str], dict[str, int], list[str], list[str]]:
    """Verify generated HTML flowchart (and optional Markdown alignment)."""
    content = html_path.read_text(encoding="utf-8")
    errors: list[str] = []
    md_warnings: list[str] = []
    md_hints: list[str] = []

    placeholders = sorted(set(PLACEHOLDER_RE.findall(content)))
    if placeholders:
        errors.append(f"Unreplaced template placeholders in HTML: {placeholders}")

    data_blocks = list(DATA_SCRIPT_RE.finditer(content))
    if len(data_blocks) != 1:
        errors.append('Expected exactly one <script id="flowchart-data" type="application/json"> data block.')
        raise ValueError("\n".join(f"- {err}" for err in errors))
    match = data_blocks[0]
    raw_data = match.group(2)
    if "<" in raw_data:
        errors.append(r"Unescaped '<' in #flowchart-data. Use \u003c for literal '<' in JSON.")
    shell = content[:match.start(2)] + content[match.end(2):]
    for label, pattern in EXTERNAL_DEPENDENCY_PATTERNS:
        if pattern.search(shell):
            errors.append(f"Disallowed offline dependency detected: {label}")

    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in #flowchart-data: {exc}")
        raise ValueError("\n".join(f"- {err}" for err in errors)) from exc

    try:
        node_ids, tone_counts = validate_data(data)
    except ValueError as exc:
        errors.append(f"Schema validation failed:\n{exc}")
        node_ids = []
        tone_counts = {}

    resolved = _resolve_checks(
        data if isinstance(data, dict) else {},
        prose_only=prose_only,
        has_composite_state=has_composite_state,
        has_async_handoff=has_async_handoff,
        has_failure_branch=has_failure_branch,
    )

    has_declared_checks = (
        (isinstance(data, dict) and isinstance(data.get("checks"), dict) and len(data["checks"]) > 0)
        or prose_only
        or has_composite_state
        or has_async_handoff
        or has_failure_branch
    )

    if node_ids and resolved.get("failureBranch") is True and tone_counts.get("red", 0) == 0:
        errors.append(
            "Declared checks.failureBranch=true, but flowchart contains zero 'red' failure/exception nodes."
        )

    if markdown_path is None and node_ids and not resolved.get("proseOnly"):
        if resolved.get("compositeState") is True or resolved.get("asyncExternal") is True:
            errors.append(
                "Declared checks.compositeState/asyncExternal=true requires --markdown to verify required "
                "Mermaid diagram type(s) (or set checks.proseOnly=true / --prose-only)."
            )
    if markdown_path is None and resolved.get("fullDocument"):
        md_hints.append("Pass --markdown to check the complete project document headings.")

    if markdown_path is not None and node_ids:
        md_text = markdown_path.read_text(encoding="utf-8")
        outside_md, mermaid_blocks = _parse_markdown_fences(md_text)

        missing_in_md = [
            nid for nid in node_ids
            if not re.search(rf"(?<![A-Za-z0-9_]){re.escape(nid)}(?![A-Za-z0-9_])", outside_md)
        ]
        if missing_in_md:
            errors.append(f"Node IDs missing from Markdown ({markdown_path.name}): {missing_in_md}")

        html_titles: dict[str, str] = {}
        for view in data.get("views", []):
            for col in view.get("columns", []):
                for lane in col.get("lanes", []):
                    for node in lane.get("nodes", []):
                        if isinstance(node.get("id"), str) and isinstance(node.get("title"), str):
                            html_titles[node["id"]] = node["title"]

        node_prefixes: set[str] = set()
        for nid in node_ids:
            pm = STEP_PREFIX_RE.match(nid)
            if pm:
                node_prefixes.add(pm.group(1))
        seen_node_ids = set(node_ids)

        md_titles: dict[str, str] = {}
        md_unique_order: list[str] = []
        dup_md_ids: set[str] = set()
        for hm in MD_STEP_HEADING_RE.finditer(outside_md):
            hid = hm.group("id")
            h_pm = STEP_PREFIX_RE.match(hid)
            if node_prefixes and (not h_pm or h_pm.group(1) not in node_prefixes):
                continue
            if hid in md_titles:
                dup_md_ids.add(hid)
            else:
                title = hm.group("title")
                if hm.group("marker") == "**":
                    title = title.split("**", 1)[0]
                else:
                    title = re.sub(r"[ \t]+#+[ \t]*$", "", title)
                    title = re.sub(r"\*\*([^*\r\n]+)\*\*", r"\1", title)
                md_titles[hid] = title
                md_unique_order.append(hid)

        if dup_md_ids:
            errors.append(f"Duplicate step heading IDs in Markdown ({markdown_path.name}): {sorted(dup_md_ids)}")

        missing_in_html = [hid for hid in md_unique_order if hid not in seen_node_ids]
        if missing_in_html:
            errors.append(f"Markdown step heading IDs missing from HTML: {missing_in_html}")

        if has_declared_checks:
            missing_headings = [nid for nid in node_ids if nid not in md_titles]
            if missing_headings:
                errors.append(
                    "Declared checks deliverable requires a unique Markdown step heading for every HTML node; "
                    f"missing headings: {missing_headings}"
                )

        md_unique_set = set(md_unique_order)
        html_order = [nid for nid in node_ids if nid in md_unique_set]
        md_order = [hid for hid in md_unique_order if hid in seen_node_ids]
        if len(md_order) >= 2 and html_order != md_order:
            errors.append(
                f"Step ID order mismatch between HTML {html_order} and Markdown headings {md_order}."
            )

        for nid, html_title in html_titles.items():
            if nid in md_titles:
                if has_declared_checks:
                    nh = _normalize_step_title(html_title)
                    nm = _normalize_step_title(md_titles[nid])
                    matched = bool(nh and nm and nh == nm)
                    if not matched:
                        errors.append(
                            f"Step '{nid}' title mismatch between HTML ('{html_title}') "
                            f"and Markdown ('{md_titles[nid].strip()}') (new deliverables with checks require exact normalized title equality)."
                        )
                else:
                    t_html = _meaningful_tokens(html_title)
                    t_md = _meaningful_tokens(md_titles[nid])
                    if t_html and t_md and t_html.isdisjoint(t_md):
                        errors.append(
                            f"Step '{nid}' title mismatch between HTML ('{html_title}') "
                            f"and Markdown ('{md_titles[nid].strip()}')."
                        )

        has_state_diagram = any(_mermaid_diagram_type(b) == "state" for b in mermaid_blocks)
        has_sequence_diagram = any(_mermaid_diagram_type(b) == "sequence" for b in mermaid_blocks)

        if not resolved.get("proseOnly"):
            if resolved.get("compositeState") is True and not has_state_diagram:
                errors.append(
                    "Declared checks.compositeState=true, but Markdown lacks a Mermaid stateDiagram / stateDiagram-v2 "
                    "block (a plain flowchart does not satisfy this check)."
                )
            if resolved.get("asyncExternal") is True and not has_sequence_diagram:
                errors.append(
                    "Declared checks.asyncExternal=true, but Markdown lacks a Mermaid sequenceDiagram block "
                    "(a plain flowchart does not satisfy this check)."
                )

        md_warnings, md_hints = collect_markdown_checks(
            outside_md, mermaid_blocks, data, resolved, has_state_diagram, has_sequence_diagram
        )

    if errors:
        raise ValueError("\n".join(f"- {err}" for err in errors))

    stage_count = len(data["views"])
    layout_warnings, layout_hints = collect_layout_checks(data, node_ids, tone_counts, resolved)
    return stage_count, node_ids, tone_counts, layout_warnings + md_warnings, layout_hints + md_hints


def build_html_from_data(data: dict[str, Any], template_html: str) -> str:
    """Validate and render HTML from JSON data and template text."""
    validate_data(data)
    if not DATA_SCRIPT_RE.search(template_html):
        raise ValueError("Template is missing #flowchart-data script block.")
    base_title = data["title"].strip()
    page_title = base_title if base_title.endswith("流程图") else f"{base_title} - 逻辑流程图"
    safe_title = f"<title>{html.escape(page_title)}</title>"
    rendered = TITLE_RE.sub(lambda _: safe_title, template_html, count=1)
    safe_json = escape_json_for_html(data)
    return DATA_SCRIPT_RE.sub(lambda m: f"{m.group(1)}{safe_json}{m.group(3)}", rendered, count=1)


def cmd_build(args: argparse.Namespace) -> int:
    template_path = Path(args.template)
    if not template_path.is_file():
        print(f"ERROR: Template not found: {template_path}", file=sys.stderr)
        return 1

    if args.input == "-":
        raw_json = sys.stdin.read()
    else:
        input_path = Path(args.input)
        if not input_path.is_file():
            print(f"ERROR: Input JSON not found: {input_path}", file=sys.stderr)
            return 1
        raw_json = input_path.read_text(encoding="utf-8")

    try:
        data = json.loads(raw_json)
        template_html = template_path.read_text(encoding="utf-8")
        rendered = build_html_from_data(data, template_html)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: Invalid flowchart input:\n{exc}", file=sys.stderr)
        return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")

    md_path = Path(args.markdown) if args.markdown else None
    if md_path is not None and not md_path.is_file():
        print(f"ERROR: Markdown file not found: {md_path}", file=sys.stderr)
        return 1

    try:
        stages, node_ids, tones, warnings, hints = verify_html_file(
            output_path,
            md_path,
            prose_only=getattr(args, "prose_only", False),
            has_composite_state=getattr(args, "has_composite_state", False),
            has_async_handoff=getattr(args, "has_async_handoff", False),
            has_failure_branch=getattr(args, "has_failure_branch", False),
        )
    except ValueError as exc:
        print(f"ERROR: Generated HTML failed verification:\n{exc}", file=sys.stderr)
        return 1

    for w in warnings:
        print(f"WARN: {w}", file=sys.stderr)
    for h in hints:
        print(f"HINT: {h}", file=sys.stderr)
    md_note = f", aligned with {md_path.name}" if md_path else ""
    print(f"OK: Built {output_path} ({stages} stages, {len(node_ids)} nodes, tones={tones}{md_note}).")
    if args.strict_warnings and warnings:
        print(f"ERROR: Failing due to --strict-warnings ({len(warnings)} warning(s)).", file=sys.stderr)
        return 1
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    html_path = Path(args.html)
    if not html_path.is_file():
        print(f"ERROR: HTML file not found: {html_path}", file=sys.stderr)
        return 1

    md_path = Path(args.markdown) if args.markdown else None
    if md_path is not None and not md_path.is_file():
        print(f"ERROR: Markdown file not found: {md_path}", file=sys.stderr)
        return 1

    try:
        stages, node_ids, tones, warnings, hints = verify_html_file(
            html_path,
            md_path,
            prose_only=getattr(args, "prose_only", False),
            has_composite_state=getattr(args, "has_composite_state", False),
            has_async_handoff=getattr(args, "has_async_handoff", False),
            has_failure_branch=getattr(args, "has_failure_branch", False),
        )
    except ValueError as exc:
        print(f"ERROR: Verification failed for {html_path}:\n{exc}", file=sys.stderr)
        return 1

    for w in warnings:
        print(f"WARN: {w}", file=sys.stderr)
    for h in hints:
        print(f"HINT: {h}", file=sys.stderr)
    md_note = f", aligned with {md_path.name}" if md_path else ""
    print(f"OK: Verified {html_path} ({stages} stages, {len(node_ids)} nodes, tones={tones}{md_note}).")
    if args.strict_warnings and warnings:
        print(f"ERROR: Failing due to --strict-warnings ({len(warnings)} warning(s)).", file=sys.stderr)
        return 1
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    """Run built-in positive and negative tests in an isolated temp directory."""
    template_path = Path(args.template)
    if not template_path.is_file():
        print(f"ERROR: Template not found: {template_path}", file=sys.stderr)
        return 1

    stages, node_ids, _, tpl_warnings, tpl_hints = verify_html_file(template_path)
    assert stages == 1 and len(node_ids) == 3 and not tpl_warnings and not tpl_hints, (
        f"Unexpected template baseline: stages={stages}, nodes={node_ids}, w={tpl_warnings}, h={tpl_hints}"
    )

    sample = {
        "title": "示例业务逻辑流程图",
        "subtitle": "自检测试样例",
        "statusNote": "第一行\n第二行",
        "footer": "测试范围",
        "views": [
            {
                "id": "stage-1",
                "title": "阶段一",
                "columns": [
                    {
                        "title": "发起",
                        "lanes": [{
                            "name": "用户",
                            "nodes": [
                                {"id": "S01", "title": "提交", "role": "用户", "place": "首页", "action": "提交</script>", "logic": "校验", "result": "受理", "tone": "teal"},
                                {"id": "S02", "title": "审核", "role": "审核", "place": "后台", "action": "审核", "logic": "判定", "result": "分流", "tone": "amber"},
                            ],
                        }],
                    },
                    {
                        "title": "异常",
                        "lanes": [{
                            "name": "审核",
                            "nodes": [
                                {"id": "S03", "title": "驳回异常", "role": "审核", "place": "后台", "action": "驳回", "logic": "拒绝", "result": "终止", "tone": "red"},
                            ],
                        }],
                    },
                ],
            }
        ],
        "nextById": {
            "S01": "进入 S02 审核。",
            "S02": "不通过进入 S03；退回修改回 S01。",
            "S03": "终态。",
        },
    }

    tpl_text = template_path.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        html_out = tmp_dir / "out.html"
        md_out = tmp_dir / "out.md"
        html_out.write_text(build_html_from_data(sample, tpl_text), encoding="utf-8")
        md_out.write_text(
            "S01 S02 S03\n`a.vue:1` `b.vue:2` `c.vue:3`\n"
            "```mermaid\nflowchart LR\n  S01[\"提交\"] --> S02[\"审核\"]\n```\n"
            "## 口述回顾\n\n用户提交后经后台审核并处理异常。\n",
            encoding="utf-8",
        )
        assert "<title>示例业务逻辑流程图</title>" in html_out.read_text(encoding="utf-8")
        assert r"\u003c/script\u003e" in html_out.read_text(encoding="utf-8")
        _, _, _, w, h = verify_html_file(html_out, md_out)
        assert not w and not h, f"Expected zero warnings/hints, got w={w}, h={h}"

        example_dir = Path(__file__).resolve().parents[1] / "examples"
        example_md = example_dir / "预约退款业务梳理.md"
        example = json.loads((example_dir / "预约退款流程数据.json").read_text(encoding="utf-8"))
        example["views"][0]["columns"][0]["lanes"][0]["nodes"][0]["logic"] += (
            " 文档示例提及 fetch()、XMLHttpRequest、@import url(https://example.com/style.css)。"
        )
        example_html = tmp_dir / "paired-example.html"
        rendered_example = build_html_from_data(example, tpl_text)
        example_html.write_text(rendered_example, encoding="utf-8")
        _, example_ids, _, example_w, example_h = verify_html_file(example_html, example_md)
        assert example_ids == ["S01", "S02", "S02-1"] and not example_w and not example_h

        bad_substep = copy.deepcopy(example)
        bad_substep["nextById"]["S02"] = "去 S02-9。"
        try:
            validate_data(bad_substep)
            raise AssertionError("Expected an absent substep to be rejected")
        except ValueError as exc:
            assert "Broken step reference 'S02-9'" in str(exc)

        no_headings_md = tmp_dir / "no-business-headings.md"
        no_headings_md.write_text(
            example_md.read_text(encoding="utf-8").replace("### 项目全业务串讲", "### 串讲").replace(
                "## 6. 口述回顾", "## 6. 摘要"
            ),
            encoding="utf-8",
        )
        _, _, _, missing_w, missing_h = verify_html_file(example_html, no_headings_md)
        assert not missing_w and len(missing_h) == 2 and all(
            any(name in hint for hint in missing_h) for name in ("项目全业务串讲", "口述回顾")
        )

        bad_shell = tmp_dir / "bad-shell.html"
        bad_shell.write_text(
            rendered_example.replace("</head>", "<script>fetch('/example');</script></head>"),
            encoding="utf-8",
        )
        try:
            verify_html_file(bad_shell, example_md)
            raise AssertionError("Expected a runtime fetch in the template shell to be rejected")
        except ValueError as exc:
            assert "runtime fetch()" in str(exc)

        # 1. Negation false-positive regression: "不涉及 HIS 或异步回调，也不涉及状态机" -> 0 warnings, 0 hints
        neg_md = tmp_dir / "negated.md"
        neg_md.write_text(
            "S01 S02 S03\n本流程不涉及 HIS 或异步回调，也不涉及状态机。\n`a.vue:1` `b.vue:2` `c.vue:3`\n",
            encoding="utf-8",
        )
        _, _, _, nw, nh = verify_html_file(html_out, neg_md)
        assert not nw and not nh, f"Negated text triggered false warning/hint: w={nw}, h={nh}"

        # 2. Dummy flowchart rejection when checks declare asyncExternal / compositeState
        dummy_flowchart_md = tmp_dir / "dummy_fc.md"
        dummy_flowchart_md.write_text(
            "S01 S02 S03\n`a.vue:1` `b.vue:2` `c.vue:3`\n"
            "```mermaid\nflowchart LR\n  S01[\"提交\"] --> S02[\"审核\"]\n```\n",
            encoding="utf-8",
        )
        for bad_checks, err_substr in (
            ({"asyncExternal": True}, "sequenceDiagram"),
            ({"compositeState": True}, "stateDiagram"),
        ):
            dc = copy.deepcopy(sample)
            dc["checks"] = bad_checks
            dc_html = tmp_dir / "dc.html"
            dc_html.write_text(build_html_from_data(dc, tpl_text), encoding="utf-8")
            try:
                verify_html_file(dc_html, dummy_flowchart_md)
                raise AssertionError(f"Expected error for {bad_checks}")
            except ValueError as exc:
                assert err_substr in str(exc), f"Unexpected error: {exc}"

        # 3. Declared compositeState + asyncExternal pass ONLY with stateDiagram-v2 AND sequenceDiagram
        rich_md = tmp_dir / "rich.md"
        rich_md.write_text(
            "### S01 提交\n### S02 审核\n### S03 驳回异常\n`a.vue:1` `b.vue:2` `c.vue:3`\n"
            "```mermaid\nstateDiagram-v2\n  [*] --> S01\n```\n"
            "```mermaid\nsequenceDiagram\n  A->>B: 回调\n```\n",
            encoding="utf-8",
        )
        rc_data = copy.deepcopy(sample)
        rc_data["checks"] = {"compositeState": True, "asyncExternal": True, "failureBranch": True}
        rc_html = tmp_dir / "rc.html"
        rc_html.write_text(build_html_from_data(rc_data, tpl_text), encoding="utf-8")
        _, _, _, rw, rh = verify_html_file(rc_html, rich_md)
        assert not rw and not rh, f"Expected clean pass with both diagrams, got w={rw}, h={rh}"

        # Round 2 regression A: checks present + S01 only in body prose (no heading) -> ERROR
        prose_only_s01_md = tmp_dir / "prose_s01.md"
        prose_only_s01_md.write_text(
            "在正文中提到 S01 提交。\n### S02 审核\n### S03 驳回异常\n",
            encoding="utf-8",
        )
        chk_simple = copy.deepcopy(sample)
        chk_simple["checks"] = {"failureBranch": True}
        chk_html = tmp_dir / "chk_simple.html"
        chk_html.write_text(build_html_from_data(chk_simple, tpl_text), encoding="utf-8")
        try:
            verify_html_file(chk_html, prose_only_s01_md)
            raise AssertionError("Expected ERROR when S01 lacks Markdown step heading")
        except ValueError as exc:
            assert "missing headings" in str(exc), f"Unexpected error: {exc}"

        # Round 2 & Round 3 regressions: exact normalized title equality under checks (2 negative + 1 positive)
        weak_overlap_md = tmp_dir / "weak_overlap.md"
        weak_overlap_md.write_text(
            "### S01 提交\n### S02 审核\n### S03 驳回随访\n",
            encoding="utf-8",
        )
        try:
            verify_html_file(chk_html, weak_overlap_md)
            raise AssertionError("Expected ERROR on partial-overlap title mismatch ('驳回异常' vs '驳回随访')")
        except ValueError as exc:
            assert "title mismatch" in str(exc), f"Unexpected error: {exc}"

        def _set_titles(payload: dict, mapping: dict[str, str]) -> None:
            for view in payload["views"]:
                for col in view["columns"]:
                    for lane in col["lanes"]:
                        for node in lane["nodes"]:
                            if node["id"] in mapping:
                                node["title"] = mapping[node["id"]]

        t3_data = copy.deepcopy(chk_simple)
        _set_titles(t3_data, {"S01": "提交业务申请", "S02": "审核处方"})
        t3_html = tmp_dir / "t3_strict_titles.html"
        t3_html.write_text(build_html_from_data(t3_data, tpl_text), encoding="utf-8")

        # Round 3 Negative 1: >=4-char prefix/substring extension must be rejected
        t3_neg_suffix_md = tmp_dir / "t3_neg_suffix.md"
        t3_neg_suffix_md.write_text(
            "### S01 提交业务申请后自动退款\n### S02 审核处方\n### S03 驳回异常\n",
            encoding="utf-8",
        )
        try:
            verify_html_file(t3_html, t3_neg_suffix_md)
            raise AssertionError("Expected ERROR on substring title mismatch ('提交业务申请' vs '提交业务申请后自动退款')")
        except ValueError as exc:
            assert "title mismatch" in str(exc), f"Unexpected error: {exc}"

        # Round 3 Negative 2: parenthetical business divergence must be rejected
        t3_neg_paren_md = tmp_dir / "t3_neg_paren.md"
        t3_neg_paren_md.write_text(
            "### S01 提交业务申请\n### S02 审核处方（不通过自动退款）\n### S03 驳回异常\n",
            encoding="utf-8",
        )
        try:
            verify_html_file(t3_html, t3_neg_paren_md)
            raise AssertionError("Expected ERROR on parenthetical title divergence ('审核处方' vs '审核处方（不通过自动退款）')")
        except ValueError as exc:
            assert "title mismatch" in str(exc), f"Unexpected error: {exc}"

        # Round 3 Positive 1: full/half-width typography & whitespace equivalents pass cleanly
        t3_pos_data = copy.deepcopy(t3_data)
        _set_titles(t3_pos_data, {"S02": "审核处方（大额 / 人工）"})
        t3_pos_html = tmp_dir / "t3_pos_typo.html"
        t3_pos_html.write_text(build_html_from_data(t3_pos_data, tpl_text), encoding="utf-8")
        t3_pos_md = tmp_dir / "t3_pos_typo.md"
        t3_pos_md.write_text(
            "### S01 提交业务申请\n### S02 审核处方 (大额/人工)\n### S03 驳回异常\n",
            encoding="utf-8",
        )
        _, _, _, t3_w, t3_h = verify_html_file(t3_pos_html, t3_pos_md)
        assert not t3_w and not t3_h, f"Typography/whitespace-equivalent titles should pass cleanly, got w={t3_w}, h={t3_h}"

        # Round 2 regression C: fake heading & fake mermaid inside fenced code block or comment are ignored
        spoof_md = tmp_dir / "spoof.md"
        spoof_md.write_text(
            "````markdown\n### S01 提交\n```mermaid\nsequenceDiagram\n  A->>B: fake\n```\n````\n"
            "### S02 审核\n### S03 驳回异常\n"
            "```mermaid\n%% sequenceDiagram fake comment\nflowchart LR\n  A[\"sequenceDiagram\"] --> B[\"ok\"]\n```\n",
            encoding="utf-8",
        )
        try:
            verify_html_file(rc_html, spoof_md)
            raise AssertionError("Expected ERROR: spoofed headings/mermaid in code blocks or comments must be ignored")
        except ValueError as exc:
            msg = str(exc)
            assert "missing headings" in msg and "sequenceDiagram" in msg and "stateDiagram" in msg, f"Unexpected: {msg}"

        # 4. Declared failureBranch=true with 0 red nodes fails; failureBranch=false suppresses hint
        fb_true = copy.deepcopy(sample)
        fb_true["views"][0]["columns"][1]["lanes"][0]["nodes"][0]["tone"] = "amber"
        fb_true["checks"] = {"failureBranch": True}
        fb_html = tmp_dir / "fb.html"
        fb_html.write_text(build_html_from_data(fb_true, tpl_text), encoding="utf-8")
        try:
            verify_html_file(fb_html)
            raise AssertionError("Expected failure when checks.failureBranch=true and 0 red nodes")
        except ValueError as exc:
            assert "failureBranch=true" in str(exc), f"Unexpected error: {exc}"

        fb_false = copy.deepcopy(fb_true)
        fb_false["checks"] = {"failureBranch": False}
        fb_false_html = tmp_dir / "fb_false.html"
        fb_false_html.write_text(build_html_from_data(fb_false, tpl_text), encoding="utf-8")
        _, _, _, fbw, fbh = verify_html_file(fb_false_html)
        assert not fbh, f"checks.failureBranch=false should suppress failure hint, got {fbh}"

        # 5. proseOnly=true suppresses declared diagram requirements cleanly (with or without --markdown)
        po_data = copy.deepcopy(sample)
        po_data["checks"] = {"compositeState": True, "asyncExternal": True, "proseOnly": True}
        po_html = tmp_dir / "po.html"
        po_html.write_text(build_html_from_data(po_data, tpl_text), encoding="utf-8")
        po_md = tmp_dir / "po.md"
        po_md.write_text("### S01 提交\n### S02 审核\n### S03 驳回异常\n", encoding="utf-8")
        _, _, _, pow_, poh = verify_html_file(po_html, po_md)
        assert not pow_ and not poh, f"proseOnly should allow prose-only markdown, got w={pow_}, h={poh}"
        _, _, _, po_nomd_w, po_nomd_h = verify_html_file(po_html)
        assert not po_nomd_w and not po_nomd_h, f"proseOnly without --markdown should pass, got w={po_nomd_w}, h={po_nomd_h}"

        # Negative schema & security checks
        bad_broken = copy.deepcopy(sample)
        bad_broken["nextById"]["S01"] = "跳转到不存在的 S99。"
        for bad_case, label in (
            (bad_broken, "broken ref S99"),
            ({**sample, "nextById": {"S01": "S02", "S02": "S03"}}, "missing nextById"),
        ):
            try:
                validate_data(bad_case)
                raise AssertionError(f"Expected failure for {label}")
            except ValueError:
                pass

        bad_dup = copy.deepcopy(sample)
        bad_dup["views"][0]["columns"][0]["lanes"][0]["nodes"][1]["id"] = "S01"
        bad_tone = copy.deepcopy(sample)
        bad_tone["views"][0]["columns"][0]["lanes"][0]["nodes"][0]["tone"] = "purple"
        for bad_case, label in ((bad_dup, "duplicate ID"), (bad_tone, "invalid tone")):
            try:
                validate_data(bad_case)
                raise AssertionError(f"Expected failure for {label}")
            except ValueError:
                pass

        bad_ph = tmp_dir / "ph.html"
        bad_ph.write_text(html_out.read_text(encoding="utf-8").replace("测试范围", "{{LEAK}}"), encoding="utf-8")
        bad_ext = tmp_dir / "ext.html"
        bad_ext.write_text(html_out.read_text(encoding="utf-8").replace("</head>", '<script src="https://x/a.js"></script></head>'), encoding="utf-8")
        for bad_file, label in ((bad_ph, "placeholder"), (bad_ext, "external script")):
            try:
                verify_html_file(bad_file)
                raise AssertionError(f"Expected verify failure for {label}")
            except ValueError:
                pass

        bad_title_md = tmp_dir / "mismatch.md"
        bad_title_md.write_text(
            "### S01 提交申请\n### S02 审核\n### S03 结束问诊与随访\n",
            encoding="utf-8",
        )
        try:
            verify_html_file(html_out, bad_title_md)
            raise AssertionError("Expected verify failure for step title mismatch")
        except ValueError as exc:
            assert "title mismatch" in str(exc), f"Unexpected error: {exc}"

        # Bidirectional Markdown alignment errors: missing in HTML, duplicate heading, out-of-order headings
        extra_md = tmp_dir / "extra.md"
        extra_md.write_text("### S01 提交\n### S02 审核\n### S03 驳回异常\n### S04 额外步骤\n", encoding="utf-8")
        dup_md = tmp_dir / "dup.md"
        dup_md.write_text("### S01 提交\n### S02 审核\n### S02 重复\n### S03 驳回异常\n", encoding="utf-8")
        order_md = tmp_dir / "order.md"
        order_md.write_text("### S01 提交\n### S03 驳回异常\n### S02 审核\n", encoding="utf-8")
        for bad_md, err_substr in (
            (extra_md, "missing from HTML"),
            (dup_md, "Duplicate step heading IDs"),
            (order_md, "order mismatch"),
        ):
            try:
                verify_html_file(html_out, bad_md)
                raise AssertionError(f"Expected verify failure for {err_substr}")
            except ValueError as exc:
                assert err_substr in str(exc), f"Unexpected error for {err_substr}: {exc}"

        # 6. checks.compositeState=true without --markdown (and not proseOnly) strictly fails
        try:
            verify_html_file(rc_html)
            raise AssertionError("Expected ERROR when checks.compositeState=true and --markdown omitted")
        except ValueError as exc:
            assert "requires --markdown" in str(exc), f"Unexpected error: {exc}"

        # 7-node plain linear happy-path workflow with NO failure/async/composite-state cues must yield ZERO warnings
        plain_nodes = [
            {
                "id": f"S0{i}",
                "title": f"常规步骤{i}",
                "role": "操作员",
                "place": f"页面{i}",
                "action": f"完成第{i}步录入",
                "logic": "常规顺序校验",
                "result": "进入下一步",
                "tone": "teal",
            }
            for i in range(1, 8)
        ]
        plain_sample = {
            "title": "常规线性流程",
            "subtitle": "无复杂状态或异常分支",
            "statusNote": "",
            "footer": "测试范围",
            "views": [
                {"id": "p1", "title": "阶段一", "columns": [{"title": "c1", "lanes": [{"name": "操作员", "nodes": plain_nodes[:4]}]}]},
                {"id": "p2", "title": "阶段二", "columns": [{"title": "c2", "lanes": [{"name": "操作员", "nodes": plain_nodes[4:]}]}]},
            ],
            "nextById": {f"S0{i}": (f"进入 S0{i + 1}。" if i < 7 else "流程完成。") for i in range(1, 8)},
        }
        plain_html = tmp_dir / "plain.html"
        plain_md = tmp_dir / "plain.md"
        plain_html.write_text(build_html_from_data(plain_sample, tpl_text), encoding="utf-8")
        plain_md.write_text(" ".join(f"S0{i}" for i in range(1, 8)) + "\n`a.vue:1` `b.vue:2` `c.vue:3`\n", encoding="utf-8")
        _, _, _, plain_w, plain_h = verify_html_file(plain_html, plain_md)
        assert not plain_w and not plain_h, f"Expected zero warnings/hints for plain 7-node workflow, got w={plain_w}, h={plain_h}"

        # Heuristic hints (orphan stages, unlinked node, meta-audit title, red final without cue, wildcard globs)
        # MUST NOT block --strict-warnings
        heuristic_md = tmp_dir / "heuristic.md"
        heuristic_md.write_text(
            "### S01 提交\n### S02 审核\n### S04 提交\n### S05 质控逐项核验\n### S06 提交\n### S03 人工介入处置\n"
            "`pagesA/*` `pagesB/*`\n涉及异步回调与 status=0 状态流转。\n",
            encoding="utf-8",
        )
        n_base = sample["views"][0]["columns"][0]["lanes"][0]["nodes"]
        heuristic_sample = copy.deepcopy(sample)
        heuristic_sample["views"] = [
            {"id": "v1", "title": "1", "columns": [{"title": "c1", "lanes": [{"name": "L", "nodes": [n_base[0], n_base[1]]}]}]},
            {"id": "v2", "title": "2", "columns": [{"title": "c2", "lanes": [{"name": "L", "nodes": [{**n_base[0], "id": "S04"}]}]}]},
            {"id": "v3", "title": "3", "columns": [{"title": "c3", "lanes": [{"name": "L", "nodes": [{**n_base[0], "id": "S05", "title": "质控逐项核验"}, {**n_base[0], "id": "S06"}]}]}]},
            {"id": "v4", "title": "4", "columns": [{"title": "c4", "lanes": [{"name": "L", "nodes": [{**n_base[0], "id": "S03", "title": "人工介入处置", "logic": "人工查看", "tone": "red"}]}]}]},
        ]
        heuristic_sample["nextById"] = {
            "S01": "只写文本不引用下游",
            "S02": "继续 S04。",
            "S03": "终态。",
            "S04": "继续 S05。",
            "S05": "继续 S06。",
            "S06": "进入 S03。",
        }
        heuristic_html = tmp_dir / "heuristic.html"
        heuristic_html.write_text(build_html_from_data(heuristic_sample, tpl_text), encoding="utf-8")
        _, _, _, h_warns, h_hints = verify_html_file(heuristic_html, heuristic_md)
        assert not h_warns, f"Heuristics must be non-blocking hints, got warnings={h_warns}"
        assert len(h_hints) >= 5, f"Expected >=5 heuristic hints, got {h_hints}"
        rc_heur = cmd_verify(argparse.Namespace(
            html=str(heuristic_html), markdown=str(heuristic_md), strict_warnings=True,
            prose_only=False, has_composite_state=False, has_async_handoff=False, has_failure_branch=False,
        ))
        assert rc_heur == 0, f"Heuristic hints alone must exit 0 under --strict-warnings, got {rc_heur}"

        # Deterministic structural/format WARN: duplicate column lane, unquoted Mermaid parens, recap > 100 chars
        # MUST fail --strict-warnings
        det_warn_md = tmp_dir / "det_warn.md"
        det_warn_md.write_text(
            "### S01 提交\n### S02 审核\n### S03 驳回异常\n"
            "```mermaid\nflowchart LR\n  A1[提交(草稿)] --> B1[\"审核\"]\n```\n"
            "## 口述回顾\n\n" + ("中" * 105) + "\n",
            encoding="utf-8",
        )
        det_warn_sample = copy.deepcopy(sample)
        det_warn_sample["views"][0]["columns"][0]["lanes"] = [
            {"name": "用户", "nodes": [n_base[0]]},
            {"name": "用户", "nodes": [n_base[1]]},
        ]
        det_warn_html = tmp_dir / "det_warn.html"
        det_warn_html.write_text(build_html_from_data(det_warn_sample, tpl_text), encoding="utf-8")
        _, _, _, det_warns, _ = verify_html_file(det_warn_html, det_warn_md)
        assert len(det_warns) == 3, f"Expected 3 deterministic warnings, got {det_warns}"
        rc_det = cmd_verify(argparse.Namespace(
            html=str(det_warn_html), markdown=str(det_warn_md), strict_warnings=True,
            prose_only=False, has_composite_state=False, has_async_handoff=False, has_failure_branch=False,
        ))
        assert rc_det == 1, f"Expected strict_warnings exit code 1 on deterministic warnings, got {rc_det}"

    print("OK: selftest passed (template, build, checks contract, diagram types, negation filter, hints vs warnings).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    default_template = Path(__file__).resolve().parent.parent / "assets" / "flowchart-template.html"
    parser = argparse.ArgumentParser(description="Build, verify, and self-test offline Simplified Chinese HTML flowcharts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_check_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--strict-warnings", action="store_true", help="Exit non-zero if any WARN is emitted (never fails on HINT).")
        p.add_argument("--prose-only", action="store_true", help="Suppress Mermaid checks when prose-only was requested.")
        p.add_argument("--has-composite-state", action="store_true", help="Strictly require Mermaid stateDiagram/stateDiagram-v2.")
        p.add_argument("--has-async-handoff", "--has-async-external", dest="has_async_handoff", action="store_true", help="Strictly require Mermaid sequenceDiagram.")
        p.add_argument("--has-failure-branch", action="store_true", help="Strictly require at least one 'red' failure node.")

    p_build = subparsers.add_parser("build", help="Inject validated JSON data into the HTML template.")
    p_build.add_argument("--input", required=True, help="Path to JSON file, or '-' to read from stdin.")
    p_build.add_argument("--output", required=True, help="Destination HTML file path.")
    p_build.add_argument("--template", default=str(default_template), help="Path to HTML template.")
    p_build.add_argument("--markdown", help="Optional Markdown business doc to verify step ID alignment.")
    add_check_flags(p_build)
    p_build.set_defaults(func=cmd_build)

    p_verify = subparsers.add_parser("verify", help="Verify an HTML flowchart and optional Markdown alignment.")
    p_verify.add_argument("--html", required=True, help="Path to HTML flowchart file.")
    p_verify.add_argument("--markdown", help="Optional Markdown business doc to verify step ID alignment.")
    add_check_flags(p_verify)
    p_verify.set_defaults(func=cmd_verify)

    p_self = subparsers.add_parser("selftest", help="Run built-in verification self-tests.")
    p_self.add_argument("--template", default=str(default_template), help="Path to HTML template.")
    p_self.set_defaults(func=cmd_selftest)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
