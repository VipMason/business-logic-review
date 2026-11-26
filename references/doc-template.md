# Markdown Business Document Specification

Produce the Markdown deliverable named in [SKILL.md](../SKILL.md). Write in Simplified Chinese for engineers, testers, product staff, and presenters. Cover the in-scope flow and relevant branches. Preserve verified menu names, and label unverified ones in Chinese.

## 1. Scope, roles, and entities

Specify start, end, surfaces, evidence scope, and environment or version. List role responsibilities, visible data, allowed operations, and handoff points. Identify entity ownership, linkage, cardinality, and creation point as relevant.

When the system uses overloaded or easily confused terms/records across surfaces (e.g., 患者 vs 就诊人, 问诊单 vs 业务订单 vs 支付交易, 处方审核 vs 药房审核), add a concise **核心术语与单据辨析表** using this header:

| 业务术语 | 准确定义 | 代码 / 库表对应标识 | 易混淆概念 |
|---|---|---|---|

## 2. Numbered end-to-end flow

Follow actual business order and use stable step identifiers (`S01`, `S02`, ...) in headings or step labels (`### S01 标题` or `**S01 标题**`) so they match the HTML deliverable (`build_flowchart.py verify --markdown` checks step-ID coverage, order, and titles—and when `checks` is declared on new deliverables, enforces a unique matching-order heading with exact normalized title equality to HTML `node.title`; place role/surface notes or parenthetical business qualifiers consistently in both files, or keep role notes in the step body/separate metadata fields rather than one-sided heading suffixes). Place parallel paths and exceptions where they arise. For each step, record:

1. Actor, surface, menu, and action. For automation, identify the trigger.
2. Preconditions, decisions, and actions.
3. Created or updated entities, ownership, relationships, and before/after states.
4. Recipient, receiving page, visible result, and synchronous, asynchronous, or T+1 timing.
5. Inline **discrepancy**, **risk**, or **open question** where supported. Contrast UI, implementation, and approved rules side by side when they conflict. Explain the impact and what remains to verify.

Consider default values that do not inherit targets, fallback behavior that conflicts with deployment settings, unmatched results retained on one surface, and status labels that do not establish real synchronization. Include applicable risks only.

Do not simply paste terse HTML card copy into Markdown: expand before/after states, entry points, and handoff timing. When the workflow involves composite/multi-entity states or async/external-system handoffs (such as payment callbacks, HIS sync, or T+1 reporting), include **1–2 targeted Mermaid diagrams** (`stateDiagram-v2` and/or `sequenceDiagram`, per [modeling.md](modeling.md)) unless the user explicitly requested prose only. Declare matching `checks` flags (`compositeState`, `asyncExternal`, `failureBranch`, `proseOnly`) in the flowchart JSON (or pass CLI flags) so `build_flowchart.py verify` enforces exact diagram types and prose-only exceptions deterministically.

State workspace/repository boundaries once in §1 and use concise inline tags (`未核实（仅代码静态分析）`) instead of repeating generic "backend code is absent" disclaimers on every step; prioritize concrete code facts (exact status codes, priority rules, validation thresholds, guard messages) over generic caveats. Cite exact `path:line` locators in the evidence index or inline citations for material rules, status conditions, and guards rather than broad wildcard globs (e.g., `pagesA/*`).

For evidence inside the project, use a Markdown link resolved relative to the document, such as `[订单状态校验（第 42 行）](../../src/order.js#L42)` when the viewer supports that line anchor. Otherwise link to the file and put the verified line or section in the label. When an HTML node cites only an evidence ID, use that same ID in the Markdown evidence index so readers can open its source there.

## 3. Rules and metric definitions

Use the decision, metric, and evidence comparison tables in [checklists.md](checklists.md). Describe triggers, conditions, precedence, success, failures, and fallbacks. For statistics record the population, numerator, denominator, dates, filters, and deduplication. Include a qualifying case and a similar excluded case.

## 4. Adjacent modules

Explain each relevant non-core module, its entry or handoff, whether it is required, how it relates to the main state, and which downstream effects it does not trigger.

## 5. Open questions

Use the following standardized Simplified Chinese table header verbatim in the deliverable:

| 编号 / 步骤 | 待确认问题 | UI 实测证据 | 代码实现证据 | 确认口径证据 | 业务影响 | 确认责任人 |
|---|---|---|---|---|---|---|

Reuse inline step IDs (`S01`, `S02`, ...). Keep conflicting evidence separate. Remove answered questions. State the reviewed scope if none remain.

## 6. Spoken recap

Close with one Chinese paragraph of no more than 100 Chinese characters, covering the start, key handoffs, and outcome.
