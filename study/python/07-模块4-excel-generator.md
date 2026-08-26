# 模块 4：Excel 生成器

涉及文件：
- `backend/services/excel_generator.py` — 140 行，把项目数据渲染成 3 Sheet 的 xlsx 字节串（无类，纯函数集合）
- `tests/test_excel_generator.py` — 155 行，11 个测试，无磁盘 IO

成员清单：

| 成员 | 行号 | 作用 |
|------|------|------|
| Sheet 名常量 | L13-L15 | 三个 Sheet 标签名 |
| `PROJECT_COLUMNS` | L17-L26 | Sheet 1 的 8 列表头 |
| `PROJECT_URL_PREFIX` | L28 | 站点地址前缀 |
| `_format_posted` | L31-L47 | Unix 秒 → UTC 文本 |
| `_format_skills` | L50-L58 | `jobs[]` → 逗号串 |
| `_project_url` | L61-L70 | `seo_url` → 绝对 URL |
| `_projects_frame` | L73-L93 | Sheet 1 的 DataFrame |
| `_skills_frame` | L96-L105 | Sheet 2 的 DataFrame |
| `_budget_frame` | L108-L115 | Sheet 3 的 DataFrame |
| `generate_excel` | L118-L140 | 唯一对外入口 |

---

## 上下游数据

### 上游：模块 3 的 `enrich_projects` 输出

模块 4 **不碰网络**。往上追两层：

| 层 | 位置 | 干了什么 |
|----|------|---------|
| 网络层 | `api_client.fetch_projects()` | `GET /projects/0.1/projects/active/`，带 `job_details=true`、`full_description=true`、`compact=true`、`offset`、`limit` |
| 网络层 | `api_client.fetch_currencies()` | `GET /projects/0.1/currencies/` → `{"USD": 1.0, "EUR": 1.1}`，缓存 24h |
| 加工层 | `data_processor.enrich_projects(projects, rates)` | 把两者凑一起，补 3 个 USD 字段 |

`job_details=true` 是硬依赖：不带它返回的项目里**没有 `jobs[]`**，Sheet 1 的 Skills 列和整个 Sheet 2 都会是空的。

入参单个项目的形状（★ 是模块 4 会读的字段）：

```json
{
  "id": 12345678,
  "title": "Scrape product data from e-commerce sites",   // ★ → Title
  "type": "fixed",                                        // ★ → Type
  "seo_url": "python/scrape-product-data",                // ★ → URL（相对路径！）
  "time_submitted": 1699999999,                           // ★ → Posted（Unix 秒）
  "currency":  { "code": "EUR", "exchange_rate": 1.1 },
  "budget":    { "minimum": 50.0, "maximum": 150.0 },
  "bid_stats": { "bid_avg": 100.0, "bid_count": 12 },     // ★ bid_count → Bid Count
  "jobs": [                                               // ★ → Skills / Sheet 2
    { "id": 13, "name": "Python" },
    { "id": 20, "name": "Scrapy" }
  ],
  "budget_min_usd": 55.0,
  "budget_max_usd": 165.0,                                // ★ → Budget (USD) / Sheet 3
  "bid_avg_usd": 110.0                                    // ★ → Avg Bid
}
```

关键一点：`budget.minimum` / `budget.maximum` 这种**原始金额模块 4 一个都不读**，只认 `_usd` 后缀字段。换算在模块 3 已经做完，Excel 层不需要知道汇率是什么东西——这就是分层的收益。

### 本模块洗成什么样

```
Sheet "Projects"            每个项目一行
  Title | Skills | Budget (USD) | Avg Bid | Bid Count | Type | Posted | URL
  Scrape... | Python, Scrapy | 165.0 | 110.0 | 12 | fixed | 2023-11-14 22:13 | https://www.freelancer.com/projects/python/scrape-product-data

Sheet "Skills Frequency"    全量技能，降序
  Skill name | Count
  Python     | 25

Sheet "Budget Distribution" 固定 5 档，空档保留 0
  Bin | Count
  <$50 | 0
  $50-$150 | 2
```

洗的动作只有三类，全在展示层：嵌套结构扁平化（`jobs[]` → 逗号串）、机器格式转人类可读（Unix 秒 → UTC 文本）、相对路径补全（`seo_url` → 绝对 URL）。

### 下游

| 输出 | 消费者 | 验收 |
|------|--------|------|
| `generate_excel()` 的 bytes | 模块 5 的 `GET /api/export`，直接塞进 HTTP 响应体 | AC-005 |
| Sheet 1 | 用户在 Excel 里筛选排序 | AC-005 |
| Sheet 2 | 技能热度，不截断（所以**没用** `top_skills`） | AC-005 |
| Sheet 3 | 复用 `build_budget_distribution`，与前端图表同一口径 | AC-005 |

「同一口径」是关键：前端柱状图和 Excel Sheet 3 调同一个函数，不可能出现网页 7 个、Excel 8 个对不上账。

### 数据流

```
Freelancer API
  ├── /projects/active/?job_details=true ──┐
  └── /currencies/ ────────────────────────┤
                                           ▼
                          enrich_projects(projects, rates)      模块 3
                                           │
                          [{...原始字段, budget_max_usd, bid_avg_usd}]
                                           ▼
                          ┌────── generate_excel() ──────┐      模块 4
                          │                              │
              _projects_frame()          _skills_frame() / _budget_frame()
                          │                              │
              逐字段变换                     直接复用模块 3 的
              时间/技能/URL                build_skill_frequency
                          │                build_budget_distribution
                          └──────────┬───────────────────┘
                                     ▼
                          pd.ExcelWriter(BytesIO)
                                     ▼
                              xlsx bytes  ──►  模块 5 /api/export  ──►  浏览器下载
```

看清一件事：`_skills_frame` 和 `_budget_frame` 各自只有 3 行，因为统计逻辑全在模块 3。模块 4 真正的活只有 `_projects_frame` 那段字段映射。

---

## ★1 返回 bytes，不写磁盘文件

### 设计缘由

先看被否掉的方案：

```python
# 方案 A：写磁盘（本项目没用）
def generate_excel(projects, output_path):
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        ...
    return output_path   # 返回一个路径
```

这样模块 5 的 `/api/export` 就得干这些：编不重名的临时文件名 → 调生成器 → 打开文件读出来发给浏览器 → 记得删掉 → 发送途中报错也要保证删除 → 多用户并发下载时文件名不能撞。一个下载接口被迫管起文件生命周期。

实际方案（L127-L138）：

```python
buffer = BytesIO()
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    ...
return buffer.getvalue()
```

上面那串麻烦全部消失：没有文件，就没有命名冲突、没有清理、没有权限问题、没有并发覆盖。

### BytesIO 是什么

一个**假装自己是文件的内存对象**。

`pd.ExcelWriter` 只要求对方有 `.write()`、`.seek()` 这些方法，从不检查是不是真文件——这叫鸭子类型：走起来像鸭子、叫起来像鸭子，就当鸭子用。`BytesIO` 恰好提供这些方法，但字节只躺在内存里。

```python
from io import BytesIO

buffer = BytesIO()
buffer.write(b"hello")     # 像文件一样写
buffer.getvalue()          # b'hello'  一次性取出全部字节
```

`b"hello"` 的 `b` 前缀是 bytes 字面量。`BytesIO` 只收 bytes 不收 str，因为 xlsx 是二进制格式（本质是 zip 包），不是文本。

### 顺带得到纯函数

方案 A 会在磁盘留痕迹：同样输入调两次，第二次可能因文件已存在而行为不同；测试跑完还要清理现场。

方案 B 的 `generate_excel` 是纯函数——同样的 `projects` 进去永远得到同样的 bytes，对外部世界零影响。这跟模块 3 是一条线：`enrich_projects` 用 `dict(project)` 浅拷贝避免改动入参，同一个念头。

好处直接体现在测试辅助函数上：

```python
def _workbook(projects):
    """Run the generator and load the produced bytes back with openpyxl."""
    return openpyxl.load_workbook(BytesIO(generate_excel(projects)))
```

`BytesIO` 在这里**反向用了一次**：`generate_excel` 吐出 bytes，再用 `BytesIO` 包成「文件」喂给 `openpyxl.load_workbook` 读回来。整个测试不产生临时文件，不需要 `tmp_path` fixture，不需要清理。11 个测试全建在这个函数上。

### 语法速查

| 写法 | 含义 |
|------|------|
| `from io import BytesIO` | 标准库，无需安装 |
| `BytesIO()` | 创建空的内存二进制缓冲 |
| `.getvalue()` | 取出全部字节，不移动读写位置，可反复调用 |
| `BytesIO(data)` | 用已有 bytes 初始化，当作可读「文件」 |
| `b"..."` | bytes 字面量，区别于 str |
| `StringIO` | 同胞，收 str，适合内存造 CSV |

---

## ★2 `generate_excel` 逐行拆解（L118-L140）

### L118 函数签名

```python
def generate_excel(projects: List[dict]) -> bytes:
```

`projects: List[dict]` 和 `-> bytes` 都是类型标注，详见下面 ★2.1。

### L119-L128 docstring

三引号字符串放在函数体第一行就成了文档，`help(generate_excel)` 能打印。格式沿用 `data_processor.py` 的参数/返回分节。内容重点写「为什么返回 bytes」而不是「怎么返回」——后者代码自己会说。

### L129 建缓冲

```python
buffer = BytesIO()
```

内存里开一个空「假文件」，xlsx 字节最终攒在这里，磁盘不留东西。

### L130 关键的一行

```python
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
```

三个东西分开看：

**`pd.ExcelWriter(buffer, ...)`** — 一个「工作簿写入器」，管的是整个 xlsx 文件（多 Sheet 的容器），不是单个表格。第一个参数按惯例叫 `path`，但它接受任何类文件对象，所以能塞 `buffer` 进去。

**`engine="openpyxl"`** — pandas 自己不会写 Excel，它只组织数据，压成 xlsx 二进制的活交给第三方库。openpyxl 是写 `.xlsx` 的标准选择，`requirements.txt` 里锁了 `3.1.5`。不写这个参数 pandas 会自己猜，显式写出来更可靠，也让读者知道依赖是谁。

**`with ... as writer:`** — 见下。

### `with` 为什么不能省

`with` 保证代码块结束时**一定执行收尾动作**，无论正常走完还是中途抛异常。

`ExcelWriter` 的收尾动作是 `close()`，它干的事不轻——xlsx 本质是 zip 包，里面有工作簿描述、样式表、每个 Sheet 的 XML。`close()` 之前这些零件还散在内存里，**buffer 里的字节是不完整的**。

时序：

```
L130  进入 with        → 创建 writer
L131  to_excel Sheet1  → 数据交给 writer，buffer 仍不完整
L134  to_excel Sheet2  → 同上
L137  to_excel Sheet3  → 同上
L139  退出 with        → 自动 close()，zip 打包收尾，buffer 此刻才是合法 xlsx
L140  getvalue()       → 取出完整字节
```

`return buffer.getvalue()` 在 L140、缩进退回函数层级，不是排版偏好而是必须。挪进 `with` 块里：

```python
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    ...
    return buffer.getvalue()   # 错：还没 close，拿到残缺字节
```

得到的字节 openpyxl 自己都读不回来，测试的 `_workbook()` 会直接抛错。**缩进层级在这里等价于正确性。**

任何有 `__enter__` / `__exit__` 的对象都能用 `with`，这类对象叫上下文管理器。`with open(...) as f` 是同一个机制。

### L131-L138 三次写入

```python
_projects_frame(projects).to_excel(
    writer, sheet_name=PROJECTS_SHEET, index=False
)
```

链式调用，拆开等于：

```python
frame = _projects_frame(projects)   # 得到一个 DataFrame
frame.to_excel(writer, sheet_name=..., index=False)
```

`to_excel` 是 DataFrame 自带的方法，三个参数：

| 参数 | 作用 |
|------|------|
| `writer` | 写进哪个工作簿。同一个 writer 传三次，三个表进同一文件；每次新建 writer 会互相覆盖只剩最后一个 |
| `sheet_name=...` | Sheet 标签名，取自 L13-L15 常量 |
| `index=False` | **别写行号**。DataFrame 默认带一列 0,1,2,... 索引，不加这个参数 A 列会变成无意义序号，把 Title 挤到 B 列，直接违反 AC-005 列定义 |

调用顺序决定 Sheet 顺序，由 `test_workbook_has_three_sheets_in_order` 锁住。

### L140 取字节

```python
return buffer.getvalue()
```

一次性交出全部字节，不移动读写位置，调几次都一样。

### 整段的形状

去掉文档和换行，这个函数只有 4 个动作：开缓冲 → 开写入器 → 写三张表 → 交字节。它自己不做任何数据加工，全部委托给三个 `_xxx_frame`。这种「入口只编排、细节在下层」的写法，让你想改 Sheet 1 的列时只看 `_projects_frame`，不用碰这里。

### 语法速查

| 写法 | 含义 |
|------|------|
| `with X() as y:` | 上下文管理器，块结束自动收尾 |
| `obj.method().method2()` | 链式调用，在左边返回值上继续调 |
| `index=False` | 关键字参数，按名传值 |
| `pd.ExcelWriter` | 工作簿级写入器，一个文件一个 |
| `df.to_excel(writer, ...)` | 把一个 DataFrame 写成一个 Sheet |

---

## ★2.1 `-> bytes`：返回值类型标注

```python
def generate_excel(projects: List[dict]) -> bytes:
```

箭头右边是返回值类型，冒号后面是参数类型。读法：「收一个 dict 列表，返回 bytes」。

**运行时完全不生效。** Python 不检查它，下面这个返回 str 照样能跑，没有任何报错：

```python
def f() -> bytes:
    return "我不是 bytes"    # 正常执行，Python 不管
```

标注只是存进函数 `__annotations__` 属性的元数据，解释器执行时看都不看。

**用处在写代码的时候。** 编辑器读到 `-> bytes` 就知道结果能 `.hex()`、不能 `.upper()`，补全和报警都靠它。人读代码同理：不点进函数体就知道拿到的是二进制而不是文件路径——这正是 ★1 那个设计决策的自我说明。

**没有返回值时写 `-> None`**，例如模块 2 的 `async def close(self) -> None`。

本模块几个签名对照：

| 位置 | 签名 | 读法 |
|------|------|------|
| L31 | `(timestamp: Optional[int]) -> Optional[str]` | 可能是 int 也可能是 None，返回同理 |
| L50 | `(project: dict) -> str` | 一定返回字符串，空技能返回 `""` 而非 None |
| L73 | `(projects: List[dict]) -> pd.DataFrame` | 类型可以是第三方库的类 |

`Optional[str]` 等于 `str | None`，是「可能没有值」的标准写法，来自 L4 的 typing 导入。`_format_skills` 返回 `str` 而不是 `Optional[str]` 是刻意的——技能列宁可空字符串也不留 None，这样 Excel 里 Skills 列类型统一。

---

## ★3 `DataFrame(rows, columns=...)` 必须显式传列名

### DataFrame 是什么

一张二维表，可以理解成内存里的 Excel 表格：有列名、若干行、每列有自己的类型。构造它最常见的方式是喂 dict 列表，每个 dict 一行、键作列名：

```python
rows = [
    {"Title": "Scraper", "Budget (USD)": 165.0},
    {"Title": "Bot",     "Budget (USD)": 300.0},
]
pd.DataFrame(rows)
#      Title  Budget (USD)
# 0  Scraper         165.0
# 1      Bot         300.0
```

列名从第一个 dict 的键推断出来了，看起来 `columns=` 完全多余。

### 空列表就崩了

```python
pd.DataFrame([])          # 空 DataFrame，零行零列
```

**零列意味着连表头都没有**，写进 Excel 是一张彻底空白的 Sheet，A1 什么都没有。

这不是理论隐患：用户搜冷门关键词 → `fetch_projects` 返回空数组 → `generate_excel([])` → 下载到三张空白表，看不出报表本该长什么样，甚至会怀疑程序坏了。

AC-005 明确要求空搜索也要产出结构完整的工作簿，`test_empty_result_still_produces_three_sheets_with_headers`（测试文件 L157-L164）钉死了这件事：

```python
wb = _workbook([])

assert wb.sheetnames == [PROJECTS_SHEET, SKILLS_SHEET, BUDGET_SHEET]
assert _rows(wb[PROJECTS_SHEET]) == [tuple(PROJECT_COLUMNS)]   # 恰好只有表头一行
assert _rows(wb[SKILLS_SHEET]) == [("Skill name", "Count")]
assert len(_rows(wb[BUDGET_SHEET])) == len(BUDGET_BINS) + 1     # 5 档 + 表头
```

Budget 表那 6 行是模块 3 `build_budget_distribution` 恒返回 5 档的功劳，跟 `columns` 无关。

### 显式传 columns 解决它

L93：

```python
return pd.DataFrame(rows, columns=PROJECT_COLUMNS)
```

语义是「这张表就是这 8 列，不用你猜」：

| `rows` | 结果 |
|--------|------|
| 有数据 | 8 列 + N 行 |
| `[]` | 8 列 + 0 行 → Excel 里仍有完整表头 |

### 还顺手解决两件事

**列顺序确定。** `rows` 里 dict 的键顺序是 `_projects_frame` 手写字面量的先后决定的——有人调整了那几行的位置，Excel 列顺序就跟着变。而 AC-005 规定 `Title` 必须在 A 列。有了 `columns=PROJECT_COLUMNS`，顺序由 L17-L26 常量单点控制，字典里怎么排都不影响输出。

**列集合固定。** `rows` 里多塞的键不会悄悄变成第 9 列（`columns` 未列出的键被丢弃）；`columns` 里有而 `rows` 里缺的键，那列全填 NaN 而不是消失。列定义是契约，多一列少一列都是违约。

`test_projects_sheet_header_matches_acceptance_columns`（测试文件 L55-L69）里那个看着傻的断言就是为此存在：

```python
assert PROJECT_COLUMNS == ["Title", "Skills", "Budget (USD)", ...]
```

它不是重复，而是在说「这 8 个名字和顺序来自 AC-005，改动请先改验收标准」。有人把 `Avg Bid` 手滑成 `Average Bid`，测试立刻红。

### 另两个 frame 的写法略不同

L103-L105：

```python
return pd.DataFrame(list(frequency.items()), columns=["Skill name", "Count"])
```

这里 `rows` 是**元组列表**：`frequency.items()` 给出 `[("Python", 25), ("Scrapy", 8)]`。这种形状里没有任何键名可推断，`columns=` 不是可选项而是唯一的列名来源。

`list(...)` 那层包装也必要：`.items()` 返回视图对象（模块 3 讲过），pandas 需要能确定长度、能重复遍历的序列，先物化成列表。

`_budget_frame`（L115）完全同构，只是列名不同。

### 语法速查

| 写法 | 含义 |
|------|------|
| `pd.DataFrame(rows)` | 从 dict 列表建表，列名由键推断 |
| `pd.DataFrame(rows, columns=[...])` | 显式指定列名与顺序，空数据也保留表头 |
| `pd.DataFrame(pairs, columns=[a, b])` | 从 (k, v) 元组列表建两列表 |
| `list(d.items())` | 把 dict 视图物化成 `[(k, v), ...]` |
| `tuple(some_list)` | 列表转元组；`iter_rows(values_only=True)` 每行是元组，类型不同 `==` 恒为假 |

---

## ★4 展示层的三个字段变换决策

`_projects_frame` 的 8 列里，5 列直接搬（`title`、`type`、`bid_count`、两个 `_usd` 金额），剩下 3 列各调一个专门函数。

共同判断标准：**这些变换只为「给人看」，不改变数据含义**，所以待在 Excel 层，不污染模块 3 的数据加工。

### 变换一：时间戳 → UTC 文本（L31-L47）

```python
if timestamp is None:
    return None
return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
```

**为什么强制 UTC。** `fromtimestamp(ts)` 不传 `tz` 时用的是**运行机器的本地时区**。上海跑出 `2023-11-15 06:13`，UTC 服务器跑出 `2023-11-14 22:13`，同一批数据两个结果。报表要跨机器复现、要能互相对比，必须锚定固定时区；选 UTC 因为 API 本身就是 UTC 语义。

固定时区也是测试能存在的前提，`test_projects_row_formats_posted_timestamp_as_utc_text`（测试 L111-L115）断言写死的字符串：

```python
assert row[6] == "2023-11-14 22:13"
```

用本地时区的话，这个测试开发机上过、CI 上红。

**为什么返回字符串而不是 `datetime` 对象。** pandas 能写成 Excel 真日期类型，看着更「正确」，但 Excel 显示真日期时会**按打开者的区域设置重新渲染**——中文系统 `2023/11/14`，美式设置 `11/14/2023`，还可能被加上本地时区偏移。交付物内容不该取决于收件人的系统设置，所以主动降级成纯文本：牺牲 Excel 里按日期排序的能力，换所有人看到完全一样的字符。

顺带：`datetime.utcnow()` 和 `utcfromtimestamp()` 在新版 Python 已废弃，因为返回**不带时区信息**的 datetime，极易被误当本地时间。正确写法就是显式 `tz=timezone.utc`。

### 变换二：`jobs[]` → 逗号串（L50-L58）

Excel 一格只能放一个值，数组必须扁平化。

```python
return ", ".join(
    job["name"] for job in project.get("jobs") or [] if job.get("name")
)
```

一行叠了四个东西：

**`project.get("jobs") or []`** — 模块 3 讲过。`get("jobs", [])` 只在**键不存在**时给默认值，而 API 会明确返回 `"jobs": null`，此时 `get` 返回 `None`，`for` 立刻炸。`or []` 同时覆盖两种情况。

**生成器表达式** — `job["name"] for job in ... if ...`，外面没方括号。与列表推导的区别是不先造中间列表，边生成边给 `join` 消费。技能只有几个，性能差异可忽略；选它是因为 `join` 只需遍历一次、不需要可索引的列表，表达意图更准。

**`if job.get("name")`** — 过滤无 name 的条目。这个口径跟模块 3 `build_skill_frequency` 里的 `if name:` 必须一致：否则 Sheet 1 算了、Sheet 2 没算，用户对着两张表数数就发现对不上。

**`", ".join(...)`** — 逗号加空格，Excel 里读着自然，也方便用户用「分列」再拆开。

这个函数返回 `str` 而非 `Optional[str]`：没有技能返回 `""` 不返回 `None`，让 Skills 整列都是文本类型。

`test_projects_row_carries_converted_amounts_and_joined_skills`（测试 L85-L99）验证 `row[1] == "Python, Scrapy"`。

### 变换三：`seo_url` → 绝对地址（L61-L70）

API 返回相对 slug `"python/build-a-scraper"`，粘到地址栏毫无用处。

```python
seo_url = project.get("seo_url")
if not seo_url:
    return None
return f"{PROJECT_URL_PREFIX}{seo_url}"
```

`if not seo_url` 同时挡住 `None` 和空字符串——`not` 对二者都为真，比 `if seo_url is None or seo_url == ""` 干净。缺失时返回 `None` 让单元格留空，而不是产出只有前缀的死链 `https://www.freelancer.com/projects/`。

前缀提成常量 L28 而非内联进 f-string，因为它是可能变的外部事实（换域名、换路径结构），单点定义好改。

`test_projects_row_builds_absolute_url_from_seo_url`（测试 L102-L108）把完整地址写死在断言里，保证拼接结果真的可点。

### 反面对照：金额不做任何变换

L84-L85：

```python
"Budget (USD)": project.get("budget_max_usd"),
"Avg Bid": project.get("bid_avg_usd"),
```

裸取，没有 `f"${amount:.2f}"`。

因为金额要在 Excel 里**被当成数字用**——排序、求和、筛选、画图。格式化成 `"$165.00"` 字符串后这些能力全没。这跟时间列的取舍正好相反：时间列排序不重要、跨机器一致重要；金额列的数值能力才是核心。

同理，缺失金额保持 `None` 不写 0，`test_projects_row_leaves_missing_amounts_empty`（测试 L118-L127）断言 `row[2] is None`。写 0 会让「预算未知」变成「预算为零」，用户按预算排序时这批项目全跑最前面。

还有一个决策：Budget 列取 `budget_max_usd`（上限）而非 min，为了跟 `build_budget_distribution` 的分箱口径一致——Sheet 3 按 max 分箱，Sheet 1 就得显示 max，否则用户看到 Sheet 1 某项目 55 美元、Sheet 3 却把它算进 `$150-$500` 档，会以为程序算错。

### 语法速查

| 写法 | 含义 |
|------|------|
| `datetime.fromtimestamp(ts, tz=timezone.utc)` | Unix 秒 → 带时区的 datetime |
| `.strftime("%Y-%m-%d %H:%M")` | datetime → 格式化字符串 |
| `sep.join(gen)` | 用分隔符连接字符串序列 |
| `x for x in seq if cond` | 生成器表达式，无方括号，边生成边消费 |
| `d.get(k) or []` | 同时兜住「键不存在」和「值为 None」 |
| `if not x:` | None、空串、空列表、0 都为真 |
| `f"{a}{b}"` | f-string 拼接 |

---

## 本模块新增已掌握概念

- 类文件对象 / 鸭子类型：`BytesIO` 冒充文件
- bytes vs str，`b"..."` 字面量
- 上下文管理器 `with`，收尾时机决定数据完整性
- 返回值类型标注 `-> T`，运行时不生效
- pandas DataFrame 构造：dict 列表 vs 元组列表
- `columns=` 的三重作用：空数据保表头、锁顺序、锁列集合
- `index=False` 抑制行索引列
- 展示层格式化与数据层加工的边界划分
- 时区显式化，`utcnow` / `utcfromtimestamp` 已废弃
- 生成器表达式 vs 列表推导
- 纯函数便于测试（`BytesIO` 反向读回，无临时文件）

