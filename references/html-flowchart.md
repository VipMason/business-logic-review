# Interactive HTML Flowchart

Deliver the HTML artifact as an offline, single-file **stage-and-lane interactive flowchart board（阶段泳道式交互流程看板）** built from [assets/flowchart-template.html](../assets/flowchart-template.html) and [scripts/build_flowchart.py](../scripts/build_flowchart.py).

## Workflow

1. Author a UTF-8 JSON file (pipe via `--input -` or use a temporary file if you only want the `.md` and `.html` deliverable pair inside `docs/业务梳理/`).
2. Run the build script to inject the JSON into the template, set `<title>`, escape `<` / `>` / `&` safely, and automatically verify schema, offline purity, step-ID coverage, and step-title semantic alignment against Markdown headings:

```bash
python scripts/build_flowchart.py build \
  --input path/to/flowchart.json \
  --output "{project-root}/docs/业务梳理/{topic}逻辑流程图.html" \
  --markdown "{project-root}/docs/业务梳理/{topic}业务梳理.md"
```

3. **Fallback when Python is unavailable:** Copy `assets/flowchart-template.html` directly and replace only `<title>` and the JSON inside `<script id="flowchart-data" type="application/json">`. Preserve all markup, CSS, and interaction logic; escape `<` as `\u003c` inside JSON strings and keep `textContent`-only rendering.

## JSON data contract

All business text must be in **Simplified Chinese**, retaining verified product terms, menu labels, and identifiers.

```json
{
  "title": "业务主题名称",
  "subtitle": "一句话说明流程范围、参与端与主要核对结论",
  "statusNote": "摘要提示当前已核实范围、关键口径风险或待确认事项（可为空字符串）",
  "footer": "证据范围：环境 / 版本 / 核对日期",
  "legend": {
    "blue": "管理配置 / 系统处理",
    "teal": "一线执行 / 用户操作",
    "amber": "规则判定 / 条件分流",
    "red": "异常分支 / 失败阻断"
  },
  "checks": {
    "compositeState": true,
    "asyncExternal": true,
    "failureBranch": true,
    "proseOnly": false
  },
  "views": [
    {
      "id": "stage-1",
      "title": "阶段一：...",
      "columns": [
        {
          "title": "1. 列标题",
          "lanes": [
            {
              "name": "系统端 / 角色泳道",
              "nodes": [
                {
                  "id": "S01",
                  "title": "节点标题",
                  "role": "执行角色",
                  "place": "页面或入口位置",
                  "action": "具体操作或触发方式",
                  "logic": "前置条件、判断规则与落库逻辑",
                  "result": "可观测结果与状态变化",
                  "tone": "teal"
                }
              ]
            }
          ]
        }
      ]
    }
  ],
  "nextById": {
    "S01": "说明流向及接收方；引用下游步骤编号（如 S02）将自动生成跳转按钮。"
  }
}
```

- `legend` is optional; omit it to use the default Chinese legend labels shown above.
- `checks` is optional (or pass CLI flags `--has-composite-state`, `--has-async-handoff` / `--has-async-external`, `--has-failure-branch`, `--prose-only`): explicitly declaring booleans activates strict new-deliverable verification—every HTML node must have a matching Markdown step heading in order with **exact normalized title equality** (normalizing only whitespace, ASCII case, and full/half-width typography equivalents such as `（）` / `()` / `：` / `:` / `／` / `/`, while preserving all business words, parentheses, and suffixes; put role or surface qualifiers in step body or separate fields rather than one-sided heading qualifiers), `compositeState: true` or `asyncExternal: true` strictly requires `--markdown` with a real top-level `stateDiagram` / `stateDiagram-v2` or `sequenceDiagram` block (fenced examples and comments are ignored), `failureBranch: true` strictly requires at least one `red` node, and `proseOnly: true` disables Mermaid checks. Legacy deliverables without `checks` remain backward-compatible; undeclared keyword matches (after filtering negated phrases like "不涉及异步") emit only non-blocking `HINT:` messages.
- Every stage `id` and every node `id` must be unique. Use stable IDs (`S01`, `S02`, ...) matching the Markdown deliverable.
- `tone` must be one of `blue` (admin/system), `teal` (user/execution), `amber` (decision/branch), or `red` (failure/exception). Reserve `red` exclusively for concrete failure, rejection, timeout, unmatched, or divergence branches (e.g., 支付失效/退款、审方驳回、HIS 拒单); never color a normal happy-path or terminal step `red` merely because backend behavior is unverified (record unverified details in `logic` and `statusNote` instead).
- Every node must represent a real business action, automated trigger, decision, or failure branch—never add synthetic meta-audit nodes (such as "分实体核验完成状态").
- Every node `id` must have a non-empty entry in `nextById` (no missing or orphan keys). For terminal nodes, state who confirms completion or where the final outcome is observed.
- **Parallel branches vs. stage cohesion:** Adjacent columns in one stage draw left-to-right `→` arrows. Keep sequential steps *within* the same branch (e.g., `开方 → 审方 → 发药`) as adjacent columns inside one stage (typically 2–5 columns per stage); only split *mutually independent parallel* branches into separate `views` (stages) so layout arrows match true execution order without creating single-node orphan stages.
- **Same-role consecutive steps:** Combine consecutive steps for the same role/surface within a column into one lane's `nodes` list instead of creating duplicate same-name lanes, so vertical `↓` connectors render cleanly.
- **Title, `statusNote`, and `logic` hygiene:** Set `title` to the clean business topic (duplicate `流程图` suffix is avoided automatically); use `\n` line breaks for multi-point `statusNote` summaries; keep per-node `logic` citations short (e.g., `（依据：P1）`) instead of repeating identical boilerplate across every card.
- Because the board organizes steps by stage, column, and lane, pair complex conditional loops or multi-state transitions with Mermaid diagrams in the Markdown document (see [modeling.md](modeling.md)).

## Built-in template capabilities

- Fixed Simplified Chinese UI chrome (search box, print/PDF export, detail labels, empty state, and fallback text) is built in—never re-introduce `{{...}}` placeholders.
- Each card and detail header displays `id` visibly, renders compact route pills (`→` forward, `↺` loopback), and clicking a node highlights direct upstream sources and downstream targets across the canvas while offering bidirectional jump chips in the detail pane.
- Clickable legend pills filter by node `tone`, stage quick-jump pills (`#stageNav`) scroll directly across multi-stage workflows, and full-text search filters across all fields without dangling arrows (`Escape` clears both search and tone filter).
- Print view (`@media print`) hides interactive controls, preserves node colors, and appends a complete stage-by-stage detail table (`#printDetails`).

## Delivery checks

- [ ] Run `python scripts/build_flowchart.py verify --html "<html-path>" --markdown "<md-path>" --strict-warnings` for full deliverable pairs and confirm exit code `0`. Declare `checks` in JSON (or pass `--has-composite-state` / `--has-async-handoff` / `--has-async-external` / `--has-failure-branch` / `--prose-only`) so exact diagram types and failure nodes are verified deterministically:
  - `ERROR` (always exit `1`): schema/offline/broken-ref errors, declared `checks` contract violations (`stateDiagram`/`sequenceDiagram`/`red` node), and bidirectional Markdown alignment errors (missing IDs in Markdown or HTML, duplicate step headings, out-of-order step IDs, step title conflicts).
  - `WARN` (exit `1` under `--strict-warnings`): deterministic structural/format defects only (duplicate same-column lane names, unquoted Mermaid bracket parentheses, spoken recap > 100 CJK chars).
  - `HINT` (never blocks `--strict-warnings`): heuristic layout/title/glob advisories and undeclared business-condition hints.
- [ ] All business content is Simplified Chinese (except evidenced product terms/identifiers).
- [ ] Main flow, exceptions, step IDs, and uncertainties agree with the Markdown deliverable.
