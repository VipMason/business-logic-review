# Business Logic Review

面向 Codex 的业务逻辑梳理技能。用页面观察、代码实现和已确认规则核对业务流程、跨端交接、权限边界、状态和统计口径。支持存量梳理、差异排查、流程串讲、规则评审和变更影响评估。

完整梳理通常输出简体中文 Markdown 和可离线打开的交互流程图，默认写入目标项目的 `docs/业务梳理/`。

## 安装与使用

需要支持本地技能的 Codex、Git，以及 Python 3.10 或更新版本。构建脚本使用 Python 标准库，流程图使用原生 HTML、CSS 和 JavaScript。没有数据库、环境变量、 API 密钥或外部运行服务需要配置。

在 PowerShell 中把仓库克隆到 Codex 技能目录。如果该目录已有同名技能，先核对现有版本再更新。

```powershell
git clone https://github.com/VipMason/business-logic-review.git "$env:USERPROFILE/.codex/skills/business-logic-review"
Set-Location "$env:USERPROFILE/.codex/skills/business-logic-review"
python scripts/build_flowchart.py selftest
```

在目标项目的 Codex 聊天里调用 `$business-logic-review`，并指定要梳理的业务。例如：

> 使用 $business-logic-review 梳理预约、支付和取消流程，标出前端、后端及支付系统之间的交接。

## 构建与校验

通常由技能生成流程数据并执行这些命令。手动操作时，将示例文件名换成实际路径。JSON 输入遵循[流程图格式](references/html-flowchart.md)，可以放在临时目录。

```powershell
python scripts/build_flowchart.py build --input flow.json --output flow.html --markdown review.md --strict-warnings
python scripts/build_flowchart.py verify --html flow.html --markdown review.md --strict-warnings
```

构建后，在浏览器中打开 HTML 文件即可使用。无需启动服务。

## 证据与隐私

仓库内示例为通用示例。技能按任务在本地读取证据，构建脚本将输入的流程数据嵌入 HTML 并写到指定路径。分享 Markdown 或 HTML 前，检查证据、截图和链接是否含有凭证、可识别的记录或内部地址。自定义 HTML 模板包含可执行的浏览器代码，只使用受信任的模板。

从 [SKILL.md](SKILL.md) 查看工作流程，从[文档规范](references/doc-template.md)和[流程图规范](references/html-flowchart.md)查看交付格式。
