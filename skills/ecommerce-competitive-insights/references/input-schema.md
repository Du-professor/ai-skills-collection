# 输入数据契约

## 商品数据

一行代表一个商品在一个采集时间的价格快照。

必填字段：

| 字段 | 规则 |
|---|---|
| `product_id` | 非空，跨商品唯一；同商品多日期可重复 |
| `brand` | 非空 |
| `product_name` | 非空 |
| `price` | 非负数；缺失时允许留空并标为未知 |
| `currency` | ISO 4217三字母代码，如 `CNY`、`USD` |

推荐字段：`platform`、`url`、`rating`、`review_count`、`collected_at`。

可选字段：`list_price`、`category`、`model`、`specs`、`is_own_brand`。

`rating` 范围为0–5；`review_count` 为非负整数；日期优先使用
ISO 8601。最多20个不同商品，至少2个。

## 评论数据

必填字段：

| 字段 | 规则 |
|---|---|
| `product_id` | 必须能关联到商品表 |
| `review_text` | 去除首尾空白后非空 |

推荐字段：`review_id`、`rating`、`review_date`、`source_url`。

可选字段：`variant`、`helpful_count`。

缺少 `review_id` 时由脚本根据来源文件、行号和内容生成稳定ID。评论文本会在进入样本前脱敏。

## 文件格式

支持CSV、TSV、JSON和XLSX。文本优先按UTF-8读取，失败后尝试
GB18030。JSON可为对象数组，或包含 `products`、`reviews`、`data`、`records`
之一的数组字段。

安全与资源上限：

- 单个输入文件不超过100MB。
- 每个文件不超过200,000行。
- 仅读取XLSX首个工作表，不运行宏或公式。
- XLSX内部文件不超过1,000个，解压后总大小不超过100MB；不解压到磁盘。
- 输入输出必须位于当前工作目录或系统临时目录，且必须是普通文件；拒绝符号链接和路径越界。
- 公式前缀在CSV输出中转义，避免表格公式注入。
- HTML标签只作为普通文本转义。
- URL只允许HTTP/HTTPS公网地址，拒绝凭据、个人信息、内网/环回/本地地址和其他协议；保存前移除查询参数与片段。
- 数据在本地处理，脚本不发起网络请求，不上传商品或评论内容。
