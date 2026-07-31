# ecommerce-competitive-insights

面向品牌市场团队的电商竞品价格与评论洞察 Skill。一次支持2–20个商品，可从上传数据离线生成规范化商品表、证据账本、分析JSON和自包含HTML战报。

## 快速开始

要求Python 3.9+，核心流程仅使用标准库。

```text
python scripts/normalize_competitors.py examples/products.csv --reviews examples/reviews.csv --out normalized.csv --evidence evidence.json
python scripts/build_review_sample.py normalized.csv --reviews examples/reviews.csv --out review-sample.json
```

按照 `references/review-taxonomy.md` 填写样本中的 `annotations`，保存为
`review-labels.json`，然后运行：

```text
python scripts/aggregate_insights.py normalized.csv --labels review-labels.json --out analysis.json
python scripts/render_competitive_report.py --analysis analysis.json --evidence evidence.json --out competitive-report.html
```

仅商品数据时，省略评论相关步骤，并执行：

```text
python scripts/aggregate_insights.py normalized.csv --out analysis.json
```

## 设计特点

- 上传数据可完全离线运行，公开URL仅作为可选增强。
- 核心脚本不联网、不上传数据，只处理当前工作目录或系统临时目录中的普通文件。
- 价格、比例、排名和覆盖率由脚本确定性计算。
- 评论采用受控主题标注，标签必须引用存在的评论ID和原文证据。
- 混合货币分组处理，不静默换汇。
- 单次价格快照不表述为趋势。
- 邮箱、手机号、身份证号和订单号在评论样本中脱敏。
- URL仅接受公网HTTP/HTTPS地址，移除查询参数和片段，并拒绝凭据、个人信息及内网地址。
- 输入输出拒绝符号链接和路径越界；XLSX设置内部文件数与解压大小上限。
- HTML不依赖JavaScript、CDN、外部字体或图片。

## 已知限制

- 不提供自动爬虫，不绕过平台访问限制。
- MVP不进行自动汇率换算。
- XLSX仅读取首个工作表，公式只读取缓存值。
- 机会指数只用于本次数据内排序，不代表市场规模或销量。
