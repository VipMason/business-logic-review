# Verification Checklist

Select only sections triggered by the request. Mark material checks verified, not applicable, or open, and retain evidence locators.

## A. Roles, scope, and permissions

Trigger: accounts or surfaces offer different data or actions.

- [ ] Record login role, organization, and business scope.
- [ ] Check menu visibility separately from list scope, detail scope, and create, edit, submit, approve, or close permissions.
- [ ] Check whether status, ownership, or assignee changes permissions.
- [ ] Compare one allowed and one denied case for material permissions.

## B. Workflow and state

Trigger: a full workflow or uncertainty about when a record or status appears.

- [ ] Identify the start event and observable completion.
- [ ] Separate creation, linkage, updates, drafts, and committed records.
- [ ] Trace relevant return, rejection, cancellation, timeout, and retry paths.
- [ ] Check repeat submission, partial batch success, and which results survive failure.
- [ ] Separate record-level and aggregate status.

## C. Automatic rules and manual entry points

Trigger: an outcome can be produced manually or automatically, or automation appears inactive.

- [ ] Verify entry points, trigger, order, conditions, and overlap handling.
- [ ] Identify deduplication granularity, historical backfill, and repeat-trigger side effects.
- [ ] Determine whether manual and automatic paths create the same object and downstream work.
- [ ] Separate recording a resolution from correcting the source record.
- [ ] Check one matching case, one nonmatching case, and a manual case if available.

## D. Matching, assignment, and defaults

Trigger: unclear candidate matching, assignment, quantity, or deadline.

- [ ] Verify candidate scope, state, exclusions, match priority, and fallback.
- [ ] Compare zero, one, multiple, and insufficient candidates.
- [ ] Check result location, original state, manual linkage, and resubmission after failure.
- [ ] Separate upstream values, form defaults, saved values, and effective values.
- [ ] Check parent limits and aggregate validation across child records.

## E. Cross-surface handoffs and timing

Trigger: a record, result, status, or task should become visible elsewhere.

- [ ] Verify source and target entities and their linkage.
- [ ] Separate source success, downstream completion, and receiving-page visibility.
- [ ] Identify synchronous, asynchronous, scheduled, or manual processing.
- [ ] For asynchronous work, verify refresh, failure reporting, and retry outcomes.
- [ ] For T+1, check calendar or business days, cutoff, time zone, and holidays.
- [ ] Track the same record across both surfaces, with observation times and filters.

## F. Metrics

Trigger: an unclear definition, count mismatch, or missing reported entity.

- [ ] Verify base population, unit, inclusion, exclusions, numerator, denominator, and zero-denominator behavior.
- [ ] Verify deduplication, record selection, and whether business cycles are isolated.
- [ ] Align dates, boundaries, time zone, organization, role, region, status, and refresh time.
- [ ] Trace one qualifying example into the denominator and, if applicable, the numerator.
- [ ] Trace one similar excluded example to the exact exclusion condition.
- [ ] Align definitions before explaining differences between pages.
- [ ] Check for multi-table JOIN fan-out duplication, missing soft-delete or voided-status filters, and NULL handling in denominators or filters.
- [ ] Check whether historical backfill, late-arriving updates, or status reversals alter previously reported periods.

## G. Code-only static inspection

Trigger: only source code, schema, or configuration is available, with no live UI or formal PRD.

- [ ] When the workspace root is not a Git repository, inspect Git branch/commit inside each sub-repository (e.g., frontend, backend, and mini-program subfolders).
- [ ] Trace entry points (routes, controllers, RPCs, scheduled jobs, event listeners) along actual call chains.
- [ ] Inspect concrete page/component/service source files for exact status codes, display priority rules, validation thresholds, and error/guard prompts—do not stop at route tables (`pages.json`) or API wrapper names (`http.js`).
- [ ] Inspect auth guards, role/tenant/org filters, and row-level ownership checks separately from UI menu config.
- [ ] Map domain state enums, transition guards, and DB transactions, unique constraints, and cascade/soft-delete behavior.
- [ ] Trace async queues, cron schedules, retries, idempotency keys, and external callbacks to confirm downstream completion.
- [ ] Inspect reporting queries, aggregations, window cutoffs, and deduplication keys directly in code/SQL.
- [ ] Cite exact `file:line` locators for every material rule, guard, and status condition (avoid wildcard globs as primary evidence), and label missing UI and rule legs explicitly as `未核实（仅代码静态分析）` rather than blocking on live access.

## H. Business-logic boundary, race, and authorization review

Trigger: flows involving money, quotas/slots, approval gates, multi-step state machines, or multi-tenant/cross-role record IDs.

Use defensive source review and existing test evidence. Record missing safeguards and recommended fixes without attempting bypasses or sending requests against deployed systems.

- [ ] **State guards:** Confirm that downstream and terminal handlers enforce required prior states (e.g., approval, payment, or a mandatory prerequisite record).
- [ ] **Concurrency and race conditions:** Check double submission, payment callback vs. timeout cancellation, and refund vs. fulfillment/settlement races, plus backend locking or idempotency keys.
- [ ] **Object-level authorization:** Confirm that server-side reads and writes are scoped to the authenticated role and the authorized tenant, owner, or assigned record.
- [ ] **Numeric and boundary extremes:** Check zero/negative values, quota/limit ceilings, multi-item proration/rounding drift, and exact boundary values (e.g., exact age or cutoff timestamps).
- [ ] **Callback and retry idempotency:** Review deduplication and transaction rules for duplicate deliveries and manual retries.

## Findings templates

Use these Simplified Chinese table headers directly in deliverables:

- **决策表：**（按 `准入约束 / 派生计算 / 动作触发 / 冲突优先级` 四类归拢，避免遗漏隐藏计算规则）
  `规则编号 | 触发条件 | 判定条件 | 优先级 / 冲突处理 | 命中结果 | 失败或兜底 | 证据与待确认项`
- **统计口径表：**
  `指标名称 | 基础人群 / 对象 | 统计单位 | 时间范围与截点 | 分母口径 | 分子口径 | 去重规则 | 命中与排除样本`
- **三方证据对照表：**

| 核对项 | UI 实测证据 | 代码实现证据 | 确认口径证据 | 结论或差异 | 待确认项与责任人 |
|---|---|---|---|---|---|

- **变更影响与兼容性：**
  - [ ] 列出受影响的上游入口、下游消费方、跨端页面及外部系统契约。
  - [ ] 明确上线时刻在途单据适用旧规则还是新规则。
  - [ ] 明确已完结单据是否需要补洗/重算，以及报表断层如何标注。
  - [ ] 列出改动前必须锁定的关键表征测试场景（Given / When / Then），防止破坏既有隐式行为。

Use Given / When / Then for key scenarios. See [modeling and methods](modeling.md) for diagramming and formal method references.
