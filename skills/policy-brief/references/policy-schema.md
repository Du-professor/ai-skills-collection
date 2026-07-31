# 跨会话政策记忆结构（Policy Store Schema）

`scripts/policy_store.py` 在用户本机维护一个 JSON 档案，用于跨会话追踪"已解读过哪些政策、用户关注哪些领域"，从而支持**连续对比**与**自动针对关注方向**。结构如下：

```json
{
  "version": 1,
  "policies": [
    {
      "title": "政策标题",
      "domain": "fiscal_tax",
      "date": "2025-01-01",
      "hash": "a1b2c3d4",
      "interpreted_at": "2026-07-30T10:00:00",
      "modes": ["summary", "extract"]
    }
  ],
  "focus_counts": {
    "fiscal_tax": 2,
    "talent_employment": 1
  },
  "recommended_focus": "fiscal_tax"
}
```

## 字段说明

- `version`：固定为 `1`。
- `policies`：已解读政策列表。`hash` 为对原文内容的短哈希（用于去重，避免同一文件重复记录）；`domain` 取自 POLICY_DOMAINS；`modes` 记录本次用到的模式。
- `focus_counts`：各领域被解读次数的计数，用于推导关注方向。
- `recommended_focus`：计数最高的领域 key；用于下次交互时自动建议优先关注的方向。多领域并列时取其一即可。

## 约束

- 档案默认路径：`~/.workbuddy/policy-brief/profile.json`（可通过 `--store-path` 覆盖）。
- **路径穿越防护**：拒绝包含 `..` 的绝对/相对越界路径；覆盖写仅允许在用户主目录、APPDATA、临时目录范围内。
- **降级**：若目录/文件不可写，返回 `{"degraded": true, "policies": [], "focus_counts": {}, "recommended_focus": null}`，不中断主流程。
- 不存储原文正文，仅存元信息，降低隐私风险。
