# 模块 5：API 路由

涉及文件：
- `backend/models.py` — 修正 `Project` 模型匹配真实 API 形态
- `backend/dependencies.py` — 33 行，客户端单例的存取点
- `backend/routes/jobs.py` — `GET /api/jobs`，返回缓存的技能标签
- `backend/routes/search.py` — 121 行，模块 5 核心（筛选参数 + offset 翻页 + 汇总）
- `backend/routes/export.py` — 42 行，`GET /api/export`，返回 xlsx 字节流
- `backend/main.py` — lifespan 单例 + 路由挂载 + 异常归一
- `tests/test_routes.py` — 12 个测试，全程不出网

成员清单：

| 成员 | 位置 | 作用 |
|------|------|------|
| `lifespan` | main.py L21-L34 | 启停时建/关客户端单例 |
| `PASSTHROUGH_STATUS` | main.py L17 | 需原样透传的上游状态码 |
| `upstream_status_error_handler` | main.py L53-L71 | 状态码类错误 → 404/429/502 |
| `upstream_transport_error_handler` | main.py L74-L82 | 连接类错误 → 502 兜底 |
| `_api_client` | dependencies.py L11 | 进程内唯一的客户端槽位 |
| `set_api_client` | dependencies.py L14-L17 | lifespan 用，写入/清空 |
| `get_api_client` | dependencies.py L20-L32 | Depends 用，取出 |
| `SearchFilters` | search.py L23-L37 | 筛选条件的数据载体 |
| `search_filters` | search.py L40-L62 | URL 参数 → `SearchFilters` |
| `collect_projects` | search.py L65-L101 | offset 翻页拉取 + USD 换算 |
| `search_projects` | search.py L104-L120 | `GET /api/search` |
| `_filename` | export.py L18-L21 | 带 UTC 时间戳的文件名 |
| `export_projects` | export.py L24-L42 | `GET /api/export` |

---

## 上下游数据

### 上游：Freelancer API 的真实响应

模块 5 是**唯一直接面向 HTTP 的层**：对外接前端的请求，对内向上游 API 发请求。

三个数据来源：

| 来源 | 谁调 | 拿到什么 |
|------|------|---------|
| `/projects/0.1/projects/active/` | `fetch_projects()` | 项目列表，单次最多 100 条 |
| `/projects/0.1/currencies/` | `fetch_currencies()` | `{"USD": 1.0, "EUR": 1.1}`，缓存 24h |
| `/projects/0.1/jobs/` | `fetch_jobs()` | 技能标签全量表，实测 3422 条 |

前端传进来的查询参数形状（`GET /api/search?...`）：

```
keywords=python          关键词，转成上游的 query
jobs[]=3&jobs[]=7        技能 id 多选，同名参数重复出现
budget_min=100           预算下限，转成上游的 min_price
budget_max=1000          预算上限
project_type=fixed       fixed | hourly，正则限定
time_range=72            24 / 72 / 168 / 720 小时
limit=250                10..500，超界直接 422
```

上游返回的单个项目（★ 是本模块或下游会读的字段）：

```json
{
  "id": 12345678,
  "title": "Python E-Commerce Stock Monitor",   // ★
  "type": "fixed",                              // ★
  "seo_url": "python/stock-monitor",            // ★ 可能缺失
  "time_submitted": 1699999999,                 // ★
  "currency":  { "code": "EUR", "exchange_rate": 1.1 },  // ★ 与 budget 同级！
  "budget":    { "minimum": 50.0, "maximum": 150.0 },    // ★ 可能缺失
  "bid_stats": { "bid_avg": 100.0, "bid_count": 12 },    // ★ 可能缺失
  "jobs": [ { "id": 13, "name": "Python" } ]     // ★
}
```

模块 1 定的模型和这个形态**不一致**，模块 5 第一步就是修它：`currency` 原本被塞在 `Budget` 内部，实际上是 `Project` 的同级字段；`seo_url` / `budget` / `bid_stats` / `currency` 都可能缺，缺一个就让整批数据校验失败是不能接受的，所以全改 Optional，兜底交给模块 3（缺汇率按 1.0、缺金额留 None）。

### 本模块洗成什么样

三个端点各自的输出：

```
GET /api/jobs
  ["PHP", "Python", "Java", ...]                  实测 3422 条

GET /api/search
  {
    "projects": [ {...原始字段, budget_min_usd, budget_max_usd, bid_avg_usd} ],
    "total": 97,
    "skills_frequency": { "Python": 25, "Scrapy": 8 },
    "budget_distribution": { "<$50": 0, "$50-$150": 2, ... }
  }

GET /api/export
  <xlsx 二进制字节>
  Content-Type: application/vnd.openxmlformats-...spreadsheetml.sheet
  Content-Disposition: attachment; filename="freelancer-projects-20260826-071530.xlsx"
```

洗的动作只有两类：**参数翻译**（前端的 `budget_min` → 上游的 `min_price`、`time_range` 小时数 → 上游的 `from_time` 时间戳）和**多页拼装**（上游单次 100 条，这一层循环凑到最多 500 条）。真正的计算全在模块 3、渲染全在模块 4，模块 5 只做搬运和编排。

### 下游

| 输出 | 消费者 | 验收 |
|------|--------|------|
| `/api/jobs` 的字符串数组 | 前端筛选面板的技能多选框 | AC-002（> 500 条） |
| `/api/search` 的 `projects` | 前端项目列表表格 | AC-001 |
| `/api/search` 的 `skills_frequency` | 前端技能热度图表 | AC-003 |
| `/api/search` 的 `budget_distribution` | 前端预算分布柱状图 | AC-004 |
| `/api/export` 的 bytes | 浏览器直接下载 | AC-005 |

技能频次和预算分布在后端算好一起返回，前端画图直接用，省得为了画图再遍历一遍全量数据。

### 数据流

```
                          前端 GET /api/search?keywords=python&limit=250
                                           │
                          search_filters()  ← URL 参数解析 + 校验（越界 422）
                                           │
                                    SearchFilters
                                           ▼
                          ┌──── collect_projects() ────┐          模块 5
                          │                            │
              fetch_currencies()          while 循环 offset 0→100→200
              （缓存 24h）                  每轮 fetch_projects(limit≤100)
                          │                 不满一页立即 break
                          │                            │
                          └──────────┬─────────────────┘
                                     ▼
                          enrich_projects(projects, rates)         模块 3
                                     │
                          [{...原始字段, *_usd}]
                          ┌──────────┴──────────┐
                          ▼                     ▼
              build_skill_frequency    generate_excel()            模块 3 / 4
              build_budget_distribution        │
                          │                    ▼
                          ▼               xlsx bytes
                  SearchResponse (JSON)        │
                          ▼                    ▼
                    前端图表 + 表格         浏览器下载
```

看清一件事：`/api/export` 和 `/api/search` 走的是**同一个 `collect_projects`**，翻页规则、USD 换算、limit 截断一份代码两处用，不可能出现网页 97 条、Excel 98 条对不上账。

上游出错时的旁路：

```
fetch_projects → raise_for_status() 抛 HTTPStatusError
                        │  一路冒泡，路由层不接
                        ▼
              main.py 的 exception_handler
                        │
        ┌───────────────┴───────────────┐
   404 / 429 原样透传              其余归一 502
```

---

## ★1 lifespan：为什么客户端必须是单例

### 设计缘由

先看被否掉的方案：

```python
# 方案 A：模块顶层建（本项目没用）
client = FreelancerAPIClient()

# 方案 B：每个请求新建（本项目没用）
async def search_projects():
    client = FreelancerAPIClient()
```

方案 A 死在**事件循环**上。客户端内部持有 `httpx.AsyncClient`，异步客户端要绑定正在运行的事件循环，而模块 import 发生在 uvicorn 建好循环**之前**，绑错循环之后发请求就报错。而且模块顶层建的对象没有对称的销毁点，连接池一直挂着不释放。

方案 B 死在**状态**上。客户端里有两样必须跨请求共享的东西：

| 状态 | 每请求新建的后果 |
|------|-----------------|
| `minute_limiter` / `hour_limiter` | 10 个并发 = 10 套各自为政的计数器，每套都觉得「才发了 1 次」，上游实际收到 10 次，限流失效被甩 429 |
| `_jobs_cache` / `_currencies_cache` | 每次都是 `None`，24h TTL 一次都命中不了，每次搜索白打一趟汇率请求 |

所以单例不是「为了省内存」，是**这两个机制的正确性依赖于状态在整个进程里只有一份**。

### 代码结构

`main.py` L21-L34：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    client = FreelancerAPIClient()
    set_api_client(client)
    try:
        yield
    finally:
        set_api_client(None)
        await client.close()
```

`yield` 是分界线：

```
yield 之前  →  应用启动时跑一次
yield       →  卡住，整个服务运行期间都停在这一行
yield 之后  →  应用关闭时跑一次
```

时间线：

```
uvicorn 启动
  → L28  建实例
  → L29  存进单例槽位
  → L31  yield ← 停住
       ...... 服务对外提供请求，期间每个请求都拿到同一个 client ......
  → Ctrl+C
  → 从 L31 恢复，进 finally
  → L33  清空槽位
  → L34  关闭连接池
```

`@asynccontextmanager` 的作用是让「带一个 yield 的异步函数」能被当成 `async with` 用，FastAPI 内部差不多就是 `async with lifespan(app):` 这样调它。

用 `try/finally` 而不是顺序写，是为了「一定会跑」——运行期间抛异常，异常会从 `yield` 那行冒出来，`finally` 依然执行。

单看 L21-L22 它只是个普通异步函数，真正让它变成钩子的是 L40 的 `FastAPI(..., lifespan=lifespan)`。函数名叫什么无所谓，参数位置才决定身份。

### 单例存在哪

存在 `dependencies.py` L11 的模块级变量：

```python
_api_client: Optional[FreelancerAPIClient] = None
```

Python 的模块只会被 import 一次，之后任何文件 `from backend.dependencies import ...` 拿到的都是同一个模块对象，所以这个模块级变量天然就是「进程内唯一的一格」。

`set_api_client`（L14-L17）往里放东西，必须写 `global _api_client`：

```python
def set_api_client(client):
    global _api_client
    _api_client = client
```

不写 `global` 的话，函数内 `_api_client = client` 会被 Python 当成创建**局部变量**，函数一返回就没了，模块级那一格根本没动。这是 Python 的赋值规则：函数内对一个名字赋值，默认创建局部变量。

为什么不用 `app.state`？FastAPI 内置的 `app.state` 也能挂共享对象，但那样 `search.py` 就得 `import main`。而 `main.py` 本来就要 import 各路由模块，路由反向 import main 就成了循环 import，Python 直接报错。多一个 `dependencies.py` 把这个环断开。

### 拿出来的那一端

`get_api_client`（L20-L32）从那一格读，读到 `None` 抛 503。它自己**不解析任何请求参数**，签名是空的——这和 `search_filters` 完全不同。`search_filters` 是「把 URL 参数翻译成对象」，`get_api_client` 是「从全局取资源」。两者都用 `Depends`，但用途是两类。

### 给测试带来的好处

关键在 `test_routes.py` L53：

```python
app.dependency_overrides[get_api_client] = lambda: _client_for(handler)
```

`dependency_overrides` 是个字典，键是原依赖函数，值是替代函数。一写，FastAPI 解依赖时就不调 `get_api_client`，改调那个 lambda，于是路由拿到的是用 `MockTransport` 造的假客户端——请求全被 handler 拦下就地返回，一个字节都不出网。

注意 L57-L60 那个 `autouse=True` fixture，每个测试跑完自动 `clear()`。`dependency_overrides` 挂在 `app` 上，而 `app` 是模块级对象、所有测试共用，不清就会漏到下一个测试里。

---

## ★2 依赖注入的两种形态

`search_projects` 的签名（search.py L105-L108）：

```python
async def search_projects(
    filters: SearchFilters = Depends(search_filters),
    client: FreelancerAPIClient = Depends(get_api_client),
) -> SearchResponse:
```

两个 `Depends`，代表两种完全不同的依赖。

### 第一种：解析参数型

`search_filters`（L40-L48）的职责是把 URL 查询参数翻译成 `SearchFilters`。它**自己也有参数**（`keywords`、`jobs`、`limit` 等），FastAPI 会先解出这些参数、跑完函数、把返回值作为 `filters` 传给端点。

它为什么能读到 URL 参数？因为参数上标了来源标记。FastAPI 一共几种：

| 标记 | 数据来自 |
|------|---------|
| `Query` | URL 的 `?a=1&b=2` |
| `Path` | 路径占位段 |
| `Header` | 请求头 |
| `Cookie` | Cookie |
| `Body` | 请求体 |

`keywords: Optional[str] = None` 没写 `Query` 也读查询字符串，是 FastAPI 的推断规则：**参数是可哈希的简单类型且不在路径里出现 → 当作查询参数；参数类型是 Pydantic 模型 → 当作请求体**。`keywords` 是 `Optional[str]`，简单类型，路径 `/search` 里也没有 `{keywords}`，所以推断成查询参数。

那为什么另四个显式写了 `Query`？因为要挂配置，不写 `Query` 没地方放：

- `jobs` 需要 `alias="jobs[]"`——参数名带中括号不是合法 Python 标识符
- `project_type` 需要 `pattern` 正则
- `limit` 需要 `ge=10, le=500`
- `time_range` 的 `Query(default=None)` 其实和不写等价，属冗余

`List[int]` 必须显式写 `Query`，否则 FastAPI 会把它推断成请求体。写了 `Query` 之后，`?jobs[]=3&jobs[]=7` 这种重复参数会被收集成 `[3, 7]`，字符串 `"3"` 顺手转成整数 `3`。

### 第二种：取资源型

`get_api_client` 签名是空的，不解析任何东西，纯粹从全局拿已建好的实例。它的存在价值是给测试留替换口——见 ★1 末尾。

### 执行顺序

```
请求到达
  → FastAPI 看 search_projects 签名，发现两个 Depends
  → 调 search_filters()   → SearchFilters 实例
  → 调 get_api_client()   → 客户端单例
  → 才调 search_projects(filters=..., client=...)
```

FastAPI 解依赖是**递归**的：依赖函数自己的参数里如果又有 `Depends`，那一层先被解。本项目没用到这种嵌套。

---

## ★3 Query 参数校验与 422

### 校验规则挂在类型上

`limit: int = Query(default=PAGE_SIZE, ge=10, le=MAX_RESULTS)`（search.py L47）。

- `ge=10`：大于等于 10
- `le=500`：小于等于 500

`ge` / `le` 是 FastAPI 直接传给 Pydantic 的校验约束。越界时**函数体一行都不跑**，FastAPI 直接回 422（Unprocessable Entity）。这就是为什么业务代码里没有任何 `if limit > 500` 的判断——校验层已经挡掉了，进业务代码的值必然合法。

`project_type: Optional[str] = Query(default=None, pattern="^(fixed|hourly)$")`（L45）用正则限定，避免把非法值透传给上游 API。

### 422 是 FastAPI 的

注意 422 不是「服务端错误」，是「请求格式不对」，语义告诉前端「别重试，改参数」。这和上游挂了的 502 是两码事。

### 验证这套解析的测试

`test_routes.py` L148-L170 发 `?keywords=scraper&jobs[]=3&jobs[]=7&budget_min=100...`，断言确实被翻译成上游要的 `query` / `jobs[]` / `min_price`。L166 的 `get_list("jobs[]") == ["3", "7"]` 证明多值数组解析对了。

---

## ★4 offset 翻页循环

上游单次最多给 100 条，需求要最多 500 条，这一层负责把多页拼起来。全部在 search.py L82-L101：

```python
collected = []
offset = 0
while len(collected) < filters.limit:
    page_size = min(PAGE_SIZE, filters.limit - len(collected))
    page = await client.fetch_projects(..., offset=offset, limit=page_size)
    collected.extend(page)
    if len(page) < page_size:
        break
    offset += page_size

return enrich_projects(collected[: filters.limit], rates)
```

### 要点一：循环条件用「已收够了没」，不用固定次数

`while len(collected) < filters.limit` 比 `for i in range(5)` 好，因为「5」是 500÷100 推出来的隐含知识，改 `MAX_RESULTS` 时容易忘同步。用「还没收够就继续」，`limit` 是多少都自动成立。

### 要点二：`min()` 决定这一页要几条

`page_size = min(100, filters.limit - len(collected))`——两个上限取小的：上游一次最多给 100，同时不能超过「还差多少条」。

`limit=250` 时三轮：

| 轮次 | 已收 | 还差 | `min(100, 还差)` | offset |
|---|---|---|---|---|
| 1 | 0 | 250 | 100 | 0 |
| 2 | 100 | 150 | 100 | 100 |
| 3 | 200 | 50 | **50** | 200 |

第三轮只要 50 条，不多要。固定每页都请求 100 会拿回 300 条再切掉 50 条，多下载的部分纯浪费。

### 要点三：不满一页就停（最要紧的一行）

```python
if len(page) < page_size:
    break
```

要了 100 条只回 43 条，只能说明上游库里没有更多匹配数据了。不 break 的话，下一轮 `offset=100` 拿回空数组，`collected` 长度不变，`while` 条件永远成立——死循环，而且每一圈都在打上游接口。

实测 `keywords=python` 只有 97 条数据，第一轮就触发这个 break。`test_routes.py` L119-L135 专门守这个行为：`limit=500` 但上游只回 2 条，断言 `offsets == [0]`，只请求了一次。

### 要点四：offset 递增用 `page_size` 而不是 `PAGE_SIZE`

`offset += page_size`。`offset` 的含义是「跳过前面几条」，这轮要了 `page_size` 条，下一轮就该从 `offset + page_size` 开始。硬编码 `+= 100` 在末轮 `page_size=50` 的场景会跳过中间那段，数据出现空洞。

### 出口的切片是最后一道闸

```python
return enrich_projects(collected[: filters.limit], rates)
```

理论上 `min()` 已保证不超发，但如果上游不讲武德——你要 50 条它回 80 条——`collected` 就会超出 `limit`。这个切片兜住「对外承诺最多 500 条」。Python 切片超出长度不报错，`[1,2][:500]` 就是 `[1,2]`。

### 一个隐藏成本

这个循环是**串行**的——`await` 一页，收到再发下一页。`limit=500` 意味着最多 5 次顺序往返。没做成并发，两个原因：`RateLimiter` 的限流窗口本来就要求请求分散开，并发只会立刻撞上限流然后被迫等待；并发拿不到「不满一页就停」的短路收益，会白打请求。

---

## ★5 异常处理器与错误码归一

### 异常从哪来

源头在 `api_client.py` L96：

```python
response.raise_for_status()
```

httpx 的方法：状态码是 2xx 什么都不做，4xx/5xx 抛 `httpx.HTTPStatusError`。它把「错误状态码」变成「异常」，否则每个调用点都得写 `if response.status_code != 200`，忘写一处就拿着错误响应当正常数据用。

抛出之后异常沿调用栈往上冒，路由层没有任何 `try/except` 拦它，一路到 FastAPI 框架被 `exception_handler` 接住。这是**故意的**：不分散到三个端点各自处理，避免三套错误响应格式，前端不必分别适配。

### 注册处理器

`@app.exception_handler(httpx.HTTPStatusError)`（main.py L53）装饰器告诉 FastAPI：任何地方抛出这个类型的异常，都交给下面这个函数生成响应。函数签名固定两个参数 `request` 和 `exc`，`request` 这里没用但必须留着，框架按位置传的。

### 归一规则

核心在 main.py L62-L67：

```python
upstream_status = exc.response.status_code
status_code = (
    upstream_status
    if upstream_status in PASSTHROUGH_STATUS   # {404, 429}
    else UPSTREAM_FAILURE_STATUS              # 502
)
```

`exc.response` 是 httpx 把原始响应挂在异常对象上了，所以能读到上游到底回的什么码。映射表（L17-L18）：

| 上游回 | 我们回 | 为什么 |
|---|---|---|
| 404 | 404 | 查无此项，前端显示「没找到」 |
| 429 | 429 | 上游限流，前端该退避后重试 |
| 500/502/503 | 502 | 上游挂了，前端显示「服务暂时不可用」 |

抽成模块级常量而不是内联 `{404, 429}`，是为了让「哪些码要透传」这个决策在文件顶部一眼可见。

### 为什么 500 要变 502，不直接透传

HTTP 状态码在描述「**谁出了问题**」：
- `500` = **我自己**的代码有 bug
- `502` = 我作为网关，**从上游拿不到有效响应**

上游挂了，我们的代码没问题。回 500 是在撒谎，误导排查方向——运维看到 500 会翻我们日志，翻半天发现代码没错。回 502 直接指向「问题在上游」。

另一层：如果不写这个 handler，异常冒到框架最外层被兜成 500，前端只能看到「服务器错误」，无法区分「上游限流稍后重试」和「本服务真有 bug」——前端的处理策略完全不同。

### 两个 handler 为什么不会打架

httpx 异常家族（继承关系）：

```
httpx.HTTPError              ← [L74] 注册的是这个
├── HTTPStatusError          ← [L53] 注册的是这个（子类）
└── TransportError
    ├── TimeoutException     ← ConnectTimeout / ReadTimeout ...
    ├── NetworkError         ← ConnectError / ReadError ...
    └── ProtocolError
```

`HTTPStatusError` 是 `HTTPError` 的**子类**，两个 handler 的覆盖面是包含关系。上游回 500 抛 `HTTPStatusError`，它同时也「是」一个 `HTTPError`，两个都匹配得上。

**谁生效？最具体的那个赢。** FastAPI（底层 Starlette）查 handler 是沿异常继承链从下往上找，第一个命中就用：

- 抛 `ConnectTimeout` → 一路往上找，命中 L74 的 `HTTPError`
- 抛 `HTTPStatusError` → 命中 L53，立刻停

所以状态码错误必走 L53 那个精细的（能读 `exc.response`），连接类错误落到 L74 那个粗的兜底。

关键结论：**与两个装饰器书写先后无关**，决定优先级的是异常类继承深度。把 L74 挪到 L53 上面行为完全一样。这与你熟悉的 `try/except` 不同——`except` 从上到下按书写顺序匹配，父类写在前面会把子类分支吃掉。

### 为什么 L74 必须写成父类

它是**兜底**。`TransportError` 底下十几个具体子类，逐个注册写不完、httpx 升级新增还会漏。注册最上层 `HTTPError` 等于说「所有 HTTP 通信相关失败，没有更精细 handler 的都归我」。

它**不能**读 `exc.response`——请求根本没发到对方，压根没有响应对象。所以 L79-L82 没有任何判断，直接一个固定 502。这就是必须拆成两个 handler 的原因：能不能读到 `response` 是两类错误的本质差别。

### 测试怎么钉住四条路

`test_routes.py` L211-L249 四个测试，一条路一个：

| 测试 | 造什么 | 走哪个 handler | 断言 |
|---|---|---|---|
| 429 透传 | `httpx.Response(429)` | L53 命中透传 | 429 |
| 404 透传 | `httpx.Response(404)` | L53 命中透传 | 404 |
| 500 归一 | `httpx.Response(500)` | L53 不在集合 | 502 |
| 网络错误 | `raise httpx.ConnectTimeout` | L74 兜底 | 502 |

最后一个值得看：`MockTransport` 的 handler 平时 `return httpx.Response(...)`，这里改成 `raise`。handler 就是「假装的网络层」，在网络层里抛异常，效果等同于真的连不上——不需要真去断网。这是 `MockTransport` 除了造假数据之外的第二个用途。

### 一个还没覆盖的缺口

两个 handler 都只返回 `{"detail": ...}`，**没有记日志**。上游挂了这件事在服务端不留痕迹，只能靠前端报错反推。生产环境至少 502 那条路应该 `logger.warning` 带上 URL 和上游状态码。这是 code review 阶段要记的点。

---

## ★6 返回二进制文件

### 关键差别：没有 response_model

```python
@router.get("/search", response_model=SearchResponse)   # search.py L104
@router.get("/export")                                  # export.py L24
```

`/api/export` 没有 `response_model`，因为**没有模型可写**——返回的不是结构化数据，是一坨二进制。返回的是 `Response` 对象而不是 dict。这两点连在一起的意义：**FastAPI 完全不插手，字节原样出门**。平时端点返回 dict，FastAPI 会做「校验 → 转 JSON → 加 Content-Type」三件事；这里返回 `Response`，框架识别出「响应已造好」，直接发走。

要是不小心返回 `bytes` 而不是 `Response`，FastAPI 会试图 JSON 序列化，结果是一串 base64 或直接报错。

### Response 的三个参数

```python
return Response(
    content=content,                # 字节串本身
    media_type=XLSX_MEDIA_TYPE,     # 告诉浏览器这是什么文件
    headers={"Content-Disposition": f'attachment; filename="{_filename()}"'},
)
```

`content` 直接吃 `generate_excel` 的返回值——模块 4 定的签名就是 `generate_excel(projects) -> bytes`，Excel 在内存里生成完就是一段字节，不落磁盘、不产生临时文件。

### media_type 与 Content-Disposition 分工不同

- `media_type` → `Content-Type` 头，回答「**这是什么文件**」。写对了，用户下载后系统图标是 Excel、双击能用 Excel 打开。写成 `application/octet-stream` 也能下载，但变成「未知类型二进制文件」。
- `Content-Disposition: attachment` → 回答「**浏览器怎么处理**」：`attachment` 触发下载存磁盘，`inline` / 不写则尝试在标签页内联显示。对 xlsx 浏览器显示不了，不写多半也下载，但那是靠浏览器兜底猜测，行为不一致，显式写死意图。

注意 `filename` 的引号嵌套（export.py L41）：外层 `f'...'` 单引号，内层 `"{_filename()}"` 双引号。文件名必须双引号包住，否则名字里有空格，浏览器只取空格前那一截。

### 文件名为什么带时间戳

```python
stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
return f"freelancer-projects-{stamp}.xlsx"
```

固定叫 `projects.xlsx` 的话，用户导出三次得到 `projects.xlsx`、`projects(1).xlsx`、`projects(2).xlsx`——靠浏览器加序号区分，看不出哪个更新。时间戳自带顺序，文件名排序就是时间排序。

`tz=timezone.utc` 显式指定时区。`datetime.now()` 不传 tz 拿的是服务器本地时间，部署到不同时区机器文件名的时间含义就变了。固定 UTC 让它与部署环境无关。

### 为什么不接受前端回传数据

这是 export 最重要的设计判断（export.py L31-L32）。

另一种做法：前端已有搜索结果，导出时把数据 POST 给后端转 Excel。看着省——不用重新请求上游。但没这么做：

- **数据可能被篡改**：POST 上来的内容后端无从验证，等于把「导出什么」的控制权交给客户端
- **payload 太大**：500 条项目带完整描述 JSON 可能有几 MB，上传比后端重新拉一遍还慢
- **一致性更好保证**：export 直接调 `collect_projects`，和 search 是同一个函数，翻页/USD/截断不可能漂移

代价是导出会重新打一次上游接口。但 export.py L7 把 `SearchFilters` / `collect_projects` / `search_filters` 三个都借了过来，URL 参数写法完全一致，所以 `/api/export?keywords=python` 和 `/api/search?keywords=python` 拿到的必然是同一批数据。

### 前端怎么触发下载

因为设计成 `GET` + 查询参数，前端不需要写任何下载逻辑：

```html
<a href="/api/export?keywords=python&limit=200">导出 Excel</a>
```

点一下浏览器自己就下载了。要设计成 `POST` + 请求体，前端得手动 `fetch` → 拿 `blob` → 造临时 `<a>` → 模拟点击 → 释放 URL，五步。这也是 search 选 `GET` 的连带好处。

### 测试怎么验

`test_routes.py` L188-L208 验了三层：L201-L203 断言 content-type 是那个长 MIME；L204 断言 content-disposition 有 attachment；L205-L208 最实在——把响应字节喂给 `openpyxl` 真的打开，断言三个 Sheet 名。

```python
workbook = openpyxl.load_workbook(BytesIO(response.content))
```

`BytesIO` 把内存字节包装成「像文件一样的对象」，`openpyxl` 以为在读文件，实际读内存，测试不用往磁盘写临时文件。能被 `openpyxl` 成功打开，就证明字节流是完整有效的 xlsx，中途没被 JSON 序列化污染。

---

## ★7 一次请求的完整链路

假设前端发出 `GET /api/search?keywords=python&jobs[]=3&limit=200`：

1. **CORS 中间件**（main.py L44-L50）——前端 5173、后端 8000，浏览器视为跨域，这里允许，否则浏览器拦掉响应。
2. **路由匹配**（main.py L86）——search 路由挂 `/api` 前缀，路由内部 `/search`，拼成 `/api/search`。
3. **解依赖**——先 `search_filters` 读参数并校验（200 合法放行），再 `get_api_client` 取单例。
4. **端点开跑**（search.py L114）——第一句调 `fetch_currencies`，首次真拉、之后命中 24h 缓存。
5. **offset 循环**（`limit=200` 两轮）——第一轮 `offset=0` 要 100 条，真回 100 条不 break，offset 推到 100；第二轮还差 100 条，若只回 43 条触发「不满一页」break，共 143 条不再白跑。
6. **每轮请求内部**——`fetch_projects` 把 `SearchFilters` 翻译成上游参数名（`keywords→query`、`budget_min→min_price`、时薪项目换 `min_hourly_rate`），交给 `_get`：先 `_throttle()` 等限流窗口，再发请求，`raise_for_status()` 遇 4xx/5xx 抛异常。
7. **补 USD**（search.py L101）——切片砍到不超过 limit，交给模块 3 `enrich_projects` 加 `budget_min_usd` 等。
8. **算统计组装**（search.py L115-L120）——`build_skill_frequency` + `build_budget_distribution` 连同 projects、total 塞进 `SearchResponse`。
9. **序列化出门**——`response_model=SearchResponse` 按 models.py 结构转 JSON 发回前端。
10. **如果第 6 步抛异常**——冒到 main.py：上游 429 透传、500 归一 502、超时兜底 502。

浓缩一条线：

```
浏览器 → CORS → 路由匹配 /api/search
       → search_filters 解析+校验（越界 422）
       → get_api_client 取单例
       → fetch_currencies（缓存）
       → while: fetch_projects(offset += 100) 直到满 limit 或页不满
       → enrich_projects 补 USD
       → build_skill_frequency + build_budget_distribution
       → SearchResponse → JSON → 浏览器
```

---

## 知识点分级

### ★ 必学

| # | 知识点 | 位置 |
|---|--------|------|
| ★1 | 模块级单例 + lifespan 生命周期 | dependencies.py、main.py L21-L40 |
| ★2 | Depends 两种形态 + dependency_overrides | search.py L40-L62、test_routes.py L51-L60 |
| ★3 | Query 参数校验与 422 | search.py L40-L48 |
| ★4 | offset 翻页循环 | search.py L82-L101 |
| ★5 | 异常处理器 + 错误码归一 | main.py L53-L82 |
| ★6 | 返回二进制文件 | export.py L24-L42 |
| ★7 | 一次请求的完整链路 | search.py L104-L120 |

### ○ 选学

- `@dataclass` 与 Pydantic BaseModel 的取舍（`SearchFilters` 用 dataclass）
- `@asynccontextmanager` 原理（`yield` 前后即启动/关闭）
- `datetime.now(tz=timezone.utc).strftime` 时间格式化
- `from_time = now - hours*3600` 时间换算（api_client.py L140-L141）

### × 跳过

- `APIRouter()` / `include_router(prefix=...)` 样板
- CORS 中间件（模块 1 已讲）
- `/health` 端点
- `models.py` 的 Optional 改动（模块 3 已讲 Optional 与兜底）

---

## code review 待记的缺口

- `SearchRequest` 模型（models.py L59-L67）现在没人用了——search 选 `GET` + 查询参数，`SearchRequest` 成了死代码，要么删要么让 `SearchFilters` 复用它
- 两个 exception handler 都没记日志，上游错误在服务端无痕，应补 `logger.warning`

