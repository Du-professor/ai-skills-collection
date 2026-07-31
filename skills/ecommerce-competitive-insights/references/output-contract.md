# 输出与命令契约

## 统一行为

所有脚本成功时退出码为0，并在stdout输出单行JSON摘要。输入或schema错误退出码为2；文件、权限或运行错误退出码为1。错误JSON至少包含 `status`、`error_type` 和 `message`，字段错误还包含 `errors`。

## 输出文件

### `normalized.csv`

确定性列顺序的商品快照。包含规范化ID、价格、货币、时间、来源行号和文件哈希。文本按UTF-8 with BOM输出，并防止CSV公式注入。

### `evidence.json`

记录输入文件哈希、商品与评论的来源文件、行号、净化后的URL、采集日期和记录ID。它是事实追溯的主账本。原始URL中的查询参数与片段不写入账本。

### `review-sample.json`

顶层对象包含 `meta` 和 `reviews`。`meta` 包括总量、样本量、覆盖率和抽样参数；`reviews` 包含脱敏后的评论、稳定哈希及空 `annotations` 数组。可能含个人信息的原始评论ID会被稳定匿名ID替代。

### `analysis.json`

包含输入摘要、商品矩阵、分币种价格指标、条件价格变化、评论主题聚合、机会排序、证据样本、警告及受约束推断。

### `competitive-report.html`

自包含UTF-8 HTML。只使用内联CSS和SVG，不加载脚本、字体、图片或远程资源。所有展示数值均取自 `analysis.json`。
