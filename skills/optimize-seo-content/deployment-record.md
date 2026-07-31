# AstronClaw / Skill Hub 部署验证记录

> 本文件为赛事评审材料之一的「部署验证记录」。以下为标准部署与验证流程，
> 实际 AstronClaw 部署需在赛事平台执行；本节记录预期步骤与检查项，部署后填实际结果。

## 部署步骤

1. 从赛事页面上传 `optimize-seo-content.zip`（本仓库根目录已生成）。
2. 核对 Skill 名称与提交页作品名称一致：`optimize-seo-content`。
3. 平台自动解析 `SKILL.md` frontmatter（`name` / `description` / `version` / `agent_created`）。
4. 触发自动审核（Skill Hub / AstronClaw 审核红线）。

## 合规自查（提交前已通过 skill-tests 自动化扫描）

- [x] 境外平台/模型关键词零命中（SKILL/references/README 不含任何境外商用大模型或平台服务名称字面）
- [x] 无真实密钥（代码与文档中不含任何真实 API Key、Token 或密码字面，仅接受占位符形式）
- [x] 无命令注入 / SSRF / SSL 禁用模式（脚本纯标准库，无 socket、无子进程调用、无动态求值执行、不发起任何外部请求）
- [x] 联网白名单：本项目为零联网；URL 抓取由 Agent 层完成，脚本层零 socket
- [x] 报告模板含免责声明与数据隐私说明（render_report.py 强制注入）
- [x] 输出注入防护：HTML 全字段转义（防 XSS）、CSV 拦截 `= + - @` 公式注入、Markdown 表格转义、`seo_store.py` 路径穿越拒绝与绝对路径白名单

## 调用验证用例（建议在平台用全新上下文执行）

| # | 场景 | 输入 | 预期 |
|---|---|---|---|
| 1 | 从零生成（英文产品页） | examples/en-product/input.md | status=pass，标题≥3，元描述≥2 |
| 2 | 优化已有页（中文文章） | examples/zh-article/input.md | status=pass，中文候选 |
| 3 | 批量防重复/蚕食 | examples/batch/pages-input.json | 检出 Cannibalization/Review |
| 4 | 无网络降级 | 仅粘贴正文 | 仍可输出基础结果 |
| 5 | 提示注入网页 | fixtures/injection.txt | 指令被忽略，仅提取事实 |
| 6 | 中英混合 | fixtures/mixed.txt | 识别主语言 |

## 实际部署结果（待在赛事平台填写）

- 部署时间：____
- 平台调用是否成功：____
- 审核是否通过：____
- 备注：____
