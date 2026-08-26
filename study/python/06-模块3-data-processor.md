# 模块 3：数据处理器

涉及文件：
- `backend/services/data_processor.py` — USD 换算、技能频次、预算分箱（无类，全是函数）
- `tests/test_data_processor.py` — 15 个测试，纯输入输出验证，无外部依赖

函数清单：
- `BUDGET_BINS` / `TOP_SKILLS_LIMIT` — 模块级常量
- `_exchange_rate` — 解析汇率（表优先，回退项目内嵌值）
- `_to_usd` — 金额换算，None 进 None 出
- `enrich_projects` — 加 3 个 USD 字段，返回新 dict
- `build_skill_frequency` — 技能计数，降序
- `top_skills` — 取前 N 名
- `build_budget_distribution` — 按 `budget_max_usd` 分 5 档

---

## 上下游数据

### 上游 1：项目搜索 `GET /projects/0.1/projects/active/`

```json
{
  "id": 12345678,
  "title": "Build a Python web scraper",
  "seo_url": "projects/python/Build-Python-web-scraper",
  "type": "fixed",
  "time_submitted": 1700000000,
  "budget":    { "minimum": 50.0, "maximum": 150.0 },
  "currency":  { "code": "EUR", "exchange_rate": 1.1 },
  "jobs":      [ { "id": 3, "name": "Python" }, { "id": 335, "name": "Web Scraping" } ],
  "bid_stats": { "bid_count": 12, "bid_avg": 100.0 }
}
```

三个要点：
1. **金额是原币种**，不是 USD。`budget.minimum=50` + `currency.code="EUR"` 表示 50 欧元。
2. **`jobs` 就是技能标签**。Freelancer 把技能叫 "job"，只有 `job_details=true` 才返回。
3. **多字段可缺失**：`budget` 可能整体为 null，`bid_avg` 零投标时为 null，`jobs` 可能为空数组。

### 上游 2：汇率表 `GET /projects/0.1/currencies/`

模块 3 接收整理后的扁平映射：

```python
rates = {"USD": 1.0, "EUR": 1.1, "INR": 0.012}
```

`exchange_rate` 语义是「1 单位该币种 = 多少 USD」，所以换算是**乘法**：50 EUR × 1.1 = 55 USD。

### 下游三种形状

| 消费者 | 需要什么 | 出自 |
|--------|---------|------|
| Excel Sheet 1 / 前端表格 | 逐个项目，金额统一 USD | `enrich_projects` |
| Excel Sheet 2 / 柱状图 | Top 10 技能及次数 | `build_skill_frequency` → `top_skills` |
| Excel Sheet 3 / 分布图 | 5 个预算区间计数 | `build_budget_distribution` |

**为什么必须洗成 USD**：一批项目里 `maximum` 有 150（EUR）、5000（INR）、200（USD），三个数字完全不可比。排序会把 5000 INR（≈$60）排在 200 USD 前面，预算分箱彻底失真。统一到 USD 是让数据可比、可排序、可统计的前提。

**为什么保留原字段**：前端要显示「€50-€150（≈$55-$165）」，原币种和符号都要展示，丢掉原值无法还原。

### 数据流

```
Freelancer API
   ├─ /projects/active/  ──►  原始项目 dict 列表
   └─ /currencies/       ──►  rates
                  ┌────────────┴─────────────┐
                  ▼                          ▼
      enrich_projects(projects, rates)   build_skill_frequency(projects)
                  │                          │  只读 jobs，不需要汇率
                  ▼                          ▼
        含 *_usd 字段的新列表        {"Python": 3, ...}
                  │                          │
                  ▼                          ▼
      build_budget_distribution()      top_skills(freq, 10)
                  │                          │
                  ▼                          ▼
          {"<$50": 1, ...}          [("Python", 3), ...]
```

`build_skill_frequency` 不依赖汇率，可与 `enrich_projects` 并行走两条支路 —— 纯函数设计的直接好处。

---

## ★1 纯函数 + 不可变数据

### 设计缘由

最直觉的写法是原地给项目「加字段」：

```python
def enrich_projects(projects, rates):
    for project in projects:
        project["budget_min_usd"] = project["budget"]["minimum"] * rate  # 原地改
    return projects
```

三个坑：

1. **同一批数据不能加工两次**。模块 5 返回 JSON、模块 4 生成 Excel 可能复用同一批 `projects`。第一次调用改了原 dict，第二次拿到的已是被改过的数据；若期间汇率表刷新，结果就是脏的。
2. **调用方不知道自己的数据被改了**。`return {"projects": enriched, "total": len(raw)}` —— `raw` 也被改了，只是你不知道。
3. **测试互相污染**。多个测试共用 fixture，第一个跑完，第二个拿到的数据已带上 `budget_min_usd`。

根源：**原地修改让「数据的当前状态」取决于「之前调用过哪些函数」**，行为不再由输入唯一决定。

| 方案 | 问题 |
|------|------|
| 原地修改 dict | 状态依赖调用历史，测试污染，无法重复加工 |
| 定义 `EnrichedProject` 类/Pydantic 模型 | 字段要全量声明，API 加字段就得同步改；此处只加 3 个派生字段，不值得建模 |
| **返回新 dict（浅拷贝）** ✅ | 输入永不变，可反复加工；代价是多一份字典外壳（引用共享，开销小） |

### 实现要点

关键一行 `dict(project)`：

```python
item = dict(project)              # 浅拷贝，新建字典
item["budget_min_usd"] = _to_usd(budget.get("minimum"), rate)
item["budget_max_usd"] = _to_usd(budget.get("maximum"), rate)
item["bid_avg_usd"] = _to_usd(bid_stats.get("bid_avg"), rate)
```

浅拷贝的确切含义：

```
project                        item = dict(project)
├─ "id" ──────► 111            ├─ "id" ──────► 111（同一 int 对象）
├─ "title" ───► "Build..."     ├─ "title" ───► "Build..."（同一 str）
└─ "budget" ──┐                └─ "budget" ──┐
              ▼                              ▼
        {"minimum": 50, ...}  ◄──────────────┘  同一个嵌套字典！
```

顶层是两个独立字典，嵌套的 `budget`/`currency`/`jobs` 仍指向同一批对象：

```python
item["budget_min_usd"] = 55.0        # ✅ 只动 item 自己的顶层键
item["budget"]["minimum"] = 999      # ❌ budget 共享，project 也被改
```

代码只做前者，从不改嵌套结构，所以浅拷贝够用。

测试锁住这条约定：

```python
def test_enrich_does_not_mutate_input():
    projects = [_project(code="EUR")]
    enrich_projects(projects, RATES)
    assert "budget_min_usd" not in projects[0]
```

不验证任何业务计算，专门守住「不改入参」。将来有人为省内存删掉 `dict(project)`，测试立刻红。

### 为什么整个模块没有类

四个公开函数都是纯函数：给定相同输入必然返回相同输出，不读写外部状态。

对比模块 2 的 `FreelancerAPIClient` —— 它必须是类，因为要持有连接池、限流时间戳、缓存条目，这些是**跨调用保持的状态**。

这个模块无状态可保。硬包成类只为少传一个 `rates`，还得管理「这个实例的 rates 是何时的」。不如显式传参 —— 函数签名就说清了全部依赖。

### 关于纯函数的准确表述

> 不需要维护跨调用状态、只对输入数据做处理、且不影响外部状态的逻辑，应设计为纯函数：输出只由输入决定，不改入参、不改全局、不做 I/O。
>
> 当函数需要输出「入参的修改版」时，用 `dict(x)` 浅拷贝再改新对象；浅拷贝只隔离顶层，嵌套对象仍是共享引用，所以只能新增/覆盖顶层键，不能改嵌套内容。若必须改嵌套，用 `copy.deepcopy` 或只重建路径上的那几层：
> ```python
> {**project, "budget": {**project["budget"], "minimum": 999}}
> ```
>
> 若函数只做读取聚合（如统计、分箱），返回全新对象即可，**无需拷贝**。

`build_skill_frequency` 和 `build_budget_distribution` 就是后者 —— 同样是纯函数，一次拷贝都没做。所以浅拷贝不是纯函数的必要条件，只是「需要输出修改版」时的手段。

### 语法补充

`dict(x)` 的等价写法：

```python
dict(other)                   # 浅拷贝
other.copy()                  # 等价，更明确
{**other}                     # 解包语法
{**other, "new": 1}           # 复制并同时加字段
```

`get(k) or {}` 与 `get(k, {})` 的区别：

```python
d = {"budget": None}
d.get("budget", {})      # → None   键存在，返回其值 None
d.get("budget") or {}    # → {}     None 是 falsy，走 or 右边
```

API 可能返回 `"budget": null`。用 `get(k, {})` 会拿到 `None`，下一行 `None.get("minimum")` 直接 `AttributeError`。用 `or {}` 同时兜住「键缺失」和「键存在但为 null」。

### 术语与后续

**纯函数（pure function）**、**不可变数据流（immutable data flow）**、**副作用（side effect）**（函数除返回值外对外部产生的影响）。

后续：模块 4 的 Excel 生成器同时需要三个函数的结果填三个 Sheet，各自独立调用、互不影响，正是这个设计的收益。

---

## ★2 BUDGET_BINS 数据驱动分箱

对应代码：`data_processor.py#L5-L12`（常量表）、`#L94-L108`（分箱逻辑）

### 设计缘由

朴素写法把区间硬编码进 if-elif 链：

```python
def build_budget_distribution(projects):
    dist = {"<$50": 0, "$50-$150": 0, "$150-$500": 0, "$500-$1000": 0, "$1000+": 0}
    for p in projects:
        amount = p.get("budget_max_usd")
        if amount is None:
            continue
        if amount < 50:
            dist["<$50"] += 1
        elif amount < 150:
            dist["$50-$150"] += 1
        elif amount < 500:
            dist["$150-$500"] += 1
        elif amount < 1000:
            dist["$500-$1000"] += 1
        else:
            dist["$1000+"] += 1
    return dist
```

问题：**区间定义散落在三处** —— 初始化字典的标签、if 条件里的数字、赋值时的标签字符串。改一档要同步改三处，标签写错一个字母就静默产生一个永远为 0 的键。加一档要插一个 elif 且必须插在正确位置（顺序错了逻辑就错）。

根源：**配置（区间怎么分）和逻辑（怎么归类计数）耦合在一起**。

| 方案 | 问题 |
|------|------|
| if-elif 硬编码 | 区间定义分散三处，改一处漏一处；顺序敏感 |
| 每档一个独立常量（`BIN_1_MAX = 50`...） | 标签和边界仍分离，遍历不了，还是得写 if 链 |
| **一张常量表 + 遍历** ✅ | 区间定义集中一处，逻辑代码与档位数量无关 |

### 实现要点

配置抽成模块级常量表：

```python
# (label, lower bound inclusive, upper bound exclusive); None means unbounded.
BUDGET_BINS: List[Tuple[str, float, Optional[float]]] = [
    ("<$50",       0.0,    50.0),
    ("$50-$150",   50.0,   150.0),
    ("$150-$500",  150.0,  500.0),
    ("$500-$1000", 500.0,  1000.0),
    ("$1000+",     1000.0, None),
]
```

每行一个三元组：标签、下界（含）、上界（不含）。`None` 表示无上界。

逻辑代码只做遍历，完全不认识具体数字：

```python
distribution = {label: 0 for label, _, _ in BUDGET_BINS}   # 预填所有键为 0
for project in projects:
    amount = project.get("budget_max_usd")
    if amount is None:
        continue
    for label, lower, upper in BUDGET_BINS:
        if amount >= lower and (upper is None or amount < upper):
            distribution[label] += 1
            break
```

三个关键点：

**1. 预填所有键为 0** —— 即使某档没有项目，键也存在且为 0。测试锁住了这条：

```python
def test_budget_distribution_keeps_empty_bins():
    assert build_budget_distribution([]) == {
        "<$50": 0, "$50-$150": 0, "$150-$500": 0, "$500-$1000": 0, "$1000+": 0
    }
```

为什么重要：前端直方图如果拿到的键数量随数据变化，X 轴档位会忽多忽少、颜色错位。固定 5 个键让图表结构稳定。附带好处 —— dict 保证插入顺序，预填顺序即图表从左到右的顺序。

**2. `upper is None or amount < upper` 的短路求值** —— 最后一档 `upper` 是 `None`，`amount < None` 在 Python 3 会抛 `TypeError`。`or` 是短路的：左边 `upper is None` 为真就不再求值右边，安全跳过比较。

**3. `break`** —— 命中一档立刻退出内层循环。区间互斥，没有 break 也不会重复计数（后续条件都不满足），但 break 省掉无意义的遍历，也表明「只归一档」的意图。

### 边界规则

左闭右开：`50` 归入 `$50-$150` 而不是 `<$50`。测试直接打在边界值上：

```python
def test_budget_distribution_boundary_values():
    # 50 → $50-$150，150 → $150-$500，1000 → $1000+
```

这类「区间端点归哪边」的规则必须有测试，否则半年后没人记得当初怎么定的。

### 语法补充

**字典推导式 + 元组解包 + `_` 占位符**：

```python
{label: 0 for label, _, _ in BUDGET_BINS}
```

`for label, _, _ in BUDGET_BINS` 把每个三元组拆成三个变量，`_` 是约定俗成的「这个值我不用」占位符（它是合法变量名，只是社区约定表示丢弃）。等价的啰嗦写法：

```python
d = {}
for item in BUDGET_BINS:
    d[item[0]] = 0
```

**`List[Tuple[str, float, Optional[float]]]`** —— 嵌套类型注解，读作「一个列表，元素是三元组，依次为 str / float / 可空 float」。运行时不校验，纯给类型检查器和读代码的人看。

### 术语与后续

**分箱（binning / bucketing / discretization）** —— 把连续变量转成分类变量。
**表驱动法（table-driven method）/ 数据驱动设计** —— 把变化的部分抽成数据表，逻辑代码只遍历表。

后续：模块 4 的 Excel Sheet 3 直接消费这个字典；模块 6 前端直方图用它的键作 X 轴标签。要调整档位只改 `BUDGET_BINS` 一处，三个下游自动跟随。

---

## ★3 `_exchange_rate` 双层回退策略

对应代码：`data_processor.py#L17-L34`

### 数据链路定位

入参 `project` 来自 `/projects/active/`，`rates` 来自 `/currencies/`（模块 2 缓存 24 小时）。返回值只被 `_to_usd` 使用，是 `enrich_projects` 内部的一步。

两个数据源都带汇率信息，但口径不同：

| 来源 | 特点 |
|------|------|
| `/currencies/` 汇率表 | 全平台统一、每日更新；但只覆盖平台主要币种 |
| 项目内嵌 `currency.exchange_rate` | 每个项目自带；但是项目**发布时**的快照，可能过期 |

### 设计缘由

只用一个来源都有盲区：

```python
# 只用汇率表 —— 遇到表里没有的币种直接崩
return rates[project["currency"]["code"]]      # KeyError

# 只用项目内嵌值 —— 老项目用的是几个月前的汇率，同一批数据口径不一
return project["currency"]["exchange_rate"]
```

| 方案 | 问题 |
|------|------|
| 只用汇率表 | 未知币种 KeyError，整批请求失败 |
| 只用项目内嵌值 | 汇率是发布时快照，同批数据口径不统一 |
| 遇到未知币种就丢弃项目 | 用户搜到的结果莫名变少，且不知道为什么 |
| **表优先 → 内嵌值 → 1.0** ✅ | 口径尽量统一，未知币种仍可换算，最差也不丢数据 |

### 实现要点

```python
def _exchange_rate(project: dict, rates: Dict[str, float]) -> float:
    currency = project.get("currency") or {}
    code = currency.get("code")
    if code in rates:
        return rates[code]
    return currency.get("exchange_rate", 1.0)
```

三层，从优到劣：

```
① code 在 rates 表里     → 用表里的值（口径统一，最新）
② 表里没有               → 用项目自带 exchange_rate（可能过期，但有值）
③ 连自带的也没有          → 1.0（当作已是 USD）
```

第 ③ 层是**有意的不精确**：宁可让金额保持原值显示，也不丢弃项目。丢弃会让用户困惑（搜到的项目数对不上），而 1.0 只影响这一个项目的金额，且未知币种本身极罕见。

`if code in rates` 用 `in` 而不是 `try/except KeyError`，因为「表里没有」是**预期的正常分支**，不是异常。

测试锁住第 ② 层：

```python
def test_enrich_falls_back_to_project_exchange_rate():
    project = _project(code="EUR")           # exchange_rate = 1.1
    result = enrich_projects([project], {})  # 空汇率表，强制走回退
    assert result[0]["budget_min_usd"] == 55.0   # 50 × 1.1
```

传空字典 `{}` 是让回退分支必然执行的最简手段 —— 不需要构造复杂场景。

### 与 `_to_usd` 的分工

`_exchange_rate` 只负责「拿到一个能用的汇率」，`_to_usd` 只负责「换算 + 处理 None」：

```python
def _to_usd(amount, rate):
    if amount is None:
        return None
    return round(amount * rate, 2)
```

`None` 进 `None` 出，绝不返回 0。若返回 0，`build_budget_distribution` 会把「预算未填」的项目统计进 `<$50` 档，直方图彻底失真。**缺失和零是两种不同的语义，不能混同。**

### 语法补充

`currency.get("exchange_rate", 1.0)` —— `dict.get(key, default)` 的第二个参数是键不存在时的返回值。这里用 `get(k, default)` 而不是 `get(k) or default` 是对的：汇率不会是 `null`，且 `0` 汇率虽荒谬但如果真出现，`or` 会把它错误替换成 1.0。

**函数命名的下划线前缀** —— `_exchange_rate` / `_to_usd` 开头的 `_` 是约定：这是模块内部实现，不属于对外 API。Python 不强制（外部照样能 import），但 `from module import *` 不会导入它，读代码的人也知道不该依赖它。

### 术语与后续

**回退链（fallback chain）/ 层级降级（graceful degradation）** —— 主方案不可用时逐级退到次优方案，而不是直接失败。

后续：模块 5 的路由会先调 `fetch_currencies` 拿 `rates` 再传进来。若该请求失败，传空字典即可 —— 整条链路自动降级到项目内嵌汇率，搜索功能不中断。

---

## ★4 `Counter` + `most_common()`

对应代码：`data_processor.py#L69-L81`（`build_skill_frequency`）、`#L84-L91`（`top_skills`）

### 数据链路定位

```
fetch_projects(?job_details=true)  ──►  原始项目列表
                                             │
                                             ▼
                                  build_skill_frequency
                                             │
                                  {"Python": 3, "Scrapy": 1}
                                             │
                         ┌───────────────────┴──────────────┐
                         ▼                                  ▼
              Excel Sheet 2（全量）              top_skills(freq, 10)
                                                            ▼
                                                  技能柱状图（AC-004）
```

关键前提：**API 请求必须带 `job_details=true`，否则返回的项目里没有 `jobs` 数组**，本函数会全部拿到空结果。

Excel 要全量、图表只要前 10 —— 这就是拆成两个函数的原因，而不是让 `build_skill_frequency` 直接返回前 10。

### 设计缘由

手写计数的样板：

```python
freq = {}
for project in projects:
    for job in project["jobs"]:
        name = job["name"]
        freq[name] = freq.get(name, 0) + 1        # 每次都要处理「键还不存在」
sorted_freq = dict(sorted(freq.items(), key=lambda kv: kv[1], reverse=True))
```

两处纯样板：`get(name, 0) + 1` 的默认值处理、`sorted(..., key=lambda kv: kv[1], reverse=True)` 的降序排序。

### 实现要点

```python
counter: Counter = Counter()
for project in projects:
    for job in project.get("jobs") or []:
        name = job.get("name")
        if name:
            counter[name] += 1
return dict(counter.most_common())
```

**`Counter` 是 dict 的子类**，唯一实质区别是缺失键默认当 0。所以 `counter[name] += 1` 对从未出现过的键不会 `KeyError`。

**`most_common()`** 是 `sorted(items, key=第二个元素, reverse=True)` 的封装，返回 `(键, 次数)` 的**列表**：

```python
[("Python", 3), ("Scrapy", 1), ("React", 1)]
```

**`dict(...)` 把降序固化进插入顺序** —— 这是容易忽略的一步。Python 3.7+ 的 dict 保证插入顺序，所以 `dict(counter.most_common())` 不只是「转成字典」，它让字典的迭代顺序 == 排名顺序。这就是为什么 `top_skills` 只需切片、不用再排序：

```python
return list(frequency.items())[:limit]
```

测试断言的是**顺序**而非数值，把这条约定锁住：

```python
def test_skill_frequency_is_sorted_descending():
    freq = build_skill_frequency(projects)
    assert list(freq.keys())[0] == "Python"
```

### 两处防御

```python
for job in project.get("jobs") or []:
```

`or []` 同时兜住「没有 jobs 键」和「jobs 是 null」。测试直接 `del project["jobs"]` 验证不抛异常。

```python
name = job.get("name")
if name:
```

用 `if name` 而不是 `if name is not None`，顺手过滤空字符串 —— 空串做字典键合法，但在图表里是个无名柱子。

### 语法补充

**`.items()` 返回视图对象（view）**，不支持索引和切片，所以要先 `list(...)` 再切片。视图是动态的：原 dict 变了，视图跟着变。

**切片越界安全**：`[:10]` 在元素不足 10 个时返回全部，不报错。所以 `top_skills` 不需要额外判断长度。

**`counter: Counter = Counter()`** —— 函数体内的变量类型注解，与类字段声明同一套语法，运行时不做任何校验。

### 术语与后续

**Counter** —— `collections` 模块的计数器，dict 子类，缺失键默认 0。
**most_common(n)** —— 按计数降序返回 `(键, 计数)` 列表，不传 n 返回全部。
**视图对象（view）** —— `.keys()` / `.values()` / `.items()` 返回的动态视图。

后续：模块 4 的 Sheet 2 直接写 `build_skill_frequency` 的全量结果（依赖它已排好序）；模块 6 的柱状图消费 `top_skills` 的 10 个二元组。

---

## 语法速查

| 写法 | 含义 |
|------|------|
| `dict(x)` / `x.copy()` / `{**x}` | 浅拷贝，三者等价 |
| `{**x, "k": v}` | 复制并同时加/覆盖字段 |
| `d.get(k) or {}` | 兜住「键缺失」和「键存在但为 null」 |
| `d.get(k, default)` | 只兜「键缺失」，键存在为 null 时返回 null |
| `{a: 0 for a, _, _ in table}` | 字典推导式 + 元组解包，`_` 表示丢弃 |
| `A is None or x < A` | 短路求值，避免 `x < None` 的 TypeError |
| `Counter()[k] += 1` | 缺失键默认 0，无需初始化 |
| `counter.most_common()` | 按计数降序返回 `(键, 计数)` 列表 |
| `list(d.items())[:n]` | 视图不能切片，先转 list；越界安全 |
| `_name` 前缀 | 约定的模块内部成员，不对外 |

## 本模块新增已掌握概念

纯函数与副作用、浅拷贝 vs 深拷贝、表驱动法、分箱、回退链、Counter/most_common、dict 插入顺序保证、视图对象、短路求值、元组解包与 `_` 占位符

