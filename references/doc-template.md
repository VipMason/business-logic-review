# Markdown Business Document Specification

Produce the Markdown deliverable named in [SKILL.md](../SKILL.md). Write in Simplified Chinese for engineers, testers, product staff, and presenters. Cover the in-scope flow and relevant branches. Preserve verified menu names, and label unverified ones in Chinese.

Use these Chinese section names for complete Markdown deliverables. The numbered prefixes shown here are optional. For a complete project, set `checks.fullDocument: true` in the paired flowchart data to enable reminders about the narrative and recap headings.

## 1. 范围、角色与核心对象

Specify start, end, surfaces, evidence scope, and environment or version. List role responsibilities, visible data, allowed operations, and handoff points. Identify entity ownership, linkage, cardinality, and creation point as relevant.

For a complete project review, add **项目端构成** in this section before the role table. State the evidence-supported frontend count and how it was determined. Use a table for application name, platform, audience, entry point, source directory or repository, and build/deployment evidence. Describe shared build targets, embedded pages, and external H5 links as applicable. Record independently evidenced deployments and unresolved activation separately from repository structure. Identify supporting APIs, adapters, and external services below the table.

When the system uses overloaded or easily confused terms/records across surfaces (e.g., 患者 vs 就诊人, 问诊单 vs 业务订单 vs 支付交易, 处方审核 vs 药房审核), add a concise **核心术语与单据辨析表** using this header:

| 业务术语 | 准确定义 | 代码 / 库表对应标识 | 易混淆概念 |
|---|---|---|---|

## 2. 端到端主流程与分支

### Required narrative before the numbered steps

For a complete project review, insert **项目全业务串讲** after the scope, roles, and entities and before the first numbered step. Before drafting, inventory each in-scope surface, role, business service, shared operating function, and external system from the available evidence. Reconcile that inventory against the narrative. Every discovered item should have an explanation of its purpose, responsible role, entry or trigger, key actions, result, and actual handoffs where evidenced. State what is known for entries whose activation, ownership, or handoff is still unverified. For an explicitly scoped walkthrough, cover from that workflow's entry to completion, with its branches and immediate dependencies.

Write connected Chinese prose that a new reader can follow or read aloud. Start with the project's purpose and how work enters it. Explain what each participant receives and does, when a process branches, how related records are identified, and where the result becomes visible. Explain independent services on their own terms and connect them to the main system through their real shared entry points, records, roles, or operating functions. Include configuration, fulfillment, reconciliation, and supporting operations where they affect the business. Use connected paragraphs by business area if the scope is broad. Keep tables and numbered steps for later reference. A single sample, a menu list, or a summary of the main workflow is insufficient for a project-level narrative.

Use verified business terms and visible actions. Keep step codes, field names, status integers, and detailed evidence in the sections that follow. Mention uncertainty where it affects the business, and distinguish a recorded source action from a verified receiving-side result. A supplied style example guides the narration only; derive business claims from this project's evidence. Before delivery, ensure that reading the narrative alone explains the role of each surface, how the business areas relate, and which links and production behaviors are still unverified. The short spoken recap remains at the end.

Follow actual business order. Use the same step IDs and titles as the flowchart, in a heading such as `### S01 标题` or a label such as `**S01 标题**`. Put role and surface notes in the step body. See the [flowchart specification](html-flowchart.md#json-data-contract) for ID and title validation. Place parallel paths and exceptions where they arise. For each step, record:

1. Actor, surface, menu, and action. For automation, identify the trigger.
2. Preconditions, decisions, and actions.
3. Created or updated entities, ownership, relationships, and before/after states.
4. Recipient, receiving page, visible result, and synchronous, asynchronous, or T+1 timing.
5. Inline **discrepancy**, **risk**, or **open question** where supported. Contrast UI, implementation, and approved rules side by side when they conflict. Explain the impact and what remains to verify.

Consider default values that do not inherit targets, fallback behavior that conflicts with deployment settings, unmatched results retained on one surface, and status labels that do not establish real synchronization. Include applicable risks only.

In Markdown, expand the HTML cards with before-and-after states, entry points, and handoff timing. Include **1–2 targeted Mermaid diagrams** for composite states or async/external-system handoffs unless the user asks for prose only. See the [modeling guide](modeling.md) for diagram selection and the [flowchart specification](html-flowchart.md#json-data-contract) for the matching `checks` flags.

State workspace/repository boundaries once in §1 and use concise inline tags (`未核实（仅代码静态分析）`) instead of repeating generic "backend code is absent" disclaimers on every step; prioritize concrete code facts (exact status codes, priority rules, validation thresholds, guard messages) over generic caveats. Cite exact `path:line` locators in the evidence index or inline citations for material rules, status conditions, and guards rather than broad wildcard globs (e.g., `pagesA/*`).

For evidence inside the project, use a Markdown link resolved relative to the document, such as `[订单状态校验（第 42 行）](../../src/order.js#L42)` when the viewer supports that line anchor. Otherwise link to the file and put the verified line or section in the label. When an HTML node cites only an evidence ID, use that same ID in the Markdown evidence index so readers can open its source there.

## 3. 规则与统计口径

Use the decision, metric, and evidence comparison tables in [checklists.md](checklists.md). Describe triggers, conditions, precedence, success, failures, and fallbacks. For statistics record the population, numerator, denominator, dates, filters, and deduplication. Include a qualifying case and a similar excluded case.

## 4. 相关模块与业务边界

Explain each relevant non-core module, its entry or handoff, whether it is required, how it relates to the main state, and which downstream effects it does not trigger.

## 5. 待确认问题

Use the following standardized Simplified Chinese table header verbatim in the deliverable:

| 编号 / 步骤 | 待确认问题 | UI 实测证据 | 代码实现证据 | 确认口径证据 | 业务影响 | 确认责任人 |
|---|---|---|---|---|---|---|

Reuse inline step IDs (`S01`, `S02`, ...). Keep conflicting evidence separate. Remove answered questions. State the reviewed scope if none remain.

## 6. 口述回顾

Use the exact heading **口述回顾** (with an optional section number). Close with one Chinese paragraph of no more than 100 Chinese characters, covering the start, key handoffs, and outcome.

See the [minimal paired example](../examples/预约退款业务梳理.md) and its [flowchart data](../examples/预约退款流程数据.json).
