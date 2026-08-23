# 模块 2：Freelancer API 客户端

涉及文件：
- `backend/services/api_client.py` — 限流、缓存、参数拼装，封装所有网络访问
- `tests/test_api_client.py` — 用假网络层验证客户端行为（10 个测试）

类清单：
- `RateLimiter` — 滑动窗口限流器
- `CacheEntry` — 带过期时刻的缓存条目
- `FreelancerAPIClient` — 主客户端，方法：`_throttle` / `_get` / `fetch_projects` / `fetch_jobs` / `fetch_currencies`

---

## ★1 transport 依赖注入

### 设计缘由

如果在构造器里硬创建 `httpx.AsyncClient(base_url=...)`，测试就必须打真实网络：

- 要联网，CI 跑不了
- 消耗真实 API 配额（50 次/分钟，几轮测试就打满）
- API 挂了或返回变了，测试就红
- **无法测异常路径** —— 没办法让真实 API 返回 500

根源：「发请求」这个动作被写死在类内部，测试没有插手余地。

| 方案 | 问题 |
|------|------|
| 打真实网络 | 慢、不稳、耗配额、无法测异常 |
| `unittest.mock.patch` 打补丁 | 侵入内部实现，httpx 升级就崩 |
| **构造器注入 transport** ✅ | 用 httpx 官方扩展点，不碰内部实现 |

### 实现要点

httpx 分层：`AsyncClient` 管上层逻辑（拼 URL、header、解析响应），**transport** 层负责真正把字节发到网络。这一层官方允许替换。

```python
def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None):
    self._client = httpx.AsyncClient(
        base_url=settings.FREELANCER_API_BASE_URL,
        timeout=30.0,
        transport=transport,
    )
```

```
transport=None                   → httpx 用默认 AsyncHTTPTransport → 真实网络
transport=MockTransport(handler) → 请求交给 handler 函数           → 完全不碰网络
```

handler 拿到完整的 `httpx.Request`，可检查 URL、查询参数、header，再返回任意响应。**这就是测试能验证「参数拼对了没」的原因**：

```python
def handler(request):
    captured.append(request)                 # 抓住请求，事后断言参数
    return httpx.Response(200, json={...})   # 想返回什么就返回什么

# 测 500 错误：return httpx.Response(500)
```

### 术语

**依赖注入（Dependency Injection）**：依赖从外部传入，而非内部硬创建。Python 不需要框架，构造器参数 + 默认值就够。

原则：凡涉及外部世界（网络、文件、时间）的东西都留注入口子，测试时换假的。后续每个模块的测试都靠这个思想。

---

## ★2 async / await

### 设计缘由

同步版本：`requests.get()` 发出请求后等服务器响应（约 800ms），**这段时间整个线程卡死**，CPU 空转。

翻 5 页 = 800ms × 5 = 4 秒。10 个用户同时搜索，要么开 10 个线程（每线程约 8MB 栈内存），要么排队 40 秒。

根源：**这 800ms 是 I/O 等待，不是 CPU 计算**。CPU 闲着，却被阻塞调用绑住。

| 方案 | 问题 |
|------|------|
| 同步 + 单线程 | 请求串行，多用户排队 |
| 同步 + 多线程池 | 每线程占内存，切换有开销，几百并发就吃不消 |
| **async + 事件循环** ✅ | 单线程挂起上千个等待中的请求，内存开销极小 |

而且这不是自由选择 —— FastAPI 本身建立在 async 之上。

### 核心表述（重点记住）

> `async def` 定义协程函数，调用它返回协程对象而不执行。`await` 驱动它执行；当 `await` 的目标（awaitable，通常底层是一个 Future）尚未就绪时，当前协程挂起，控制权交还事件循环，事件循环转去跑其他就绪任务，并把这个协程搁置不管。操作系统通知 I/O 就绪后，事件循环把对应 Future 标记完成，才将该协程重新放入就绪队列，轮到它时从 `await` 处继续。因为 `await` 依赖协程的挂起机制，它只能出现在 `async def` 内部。

三个易错点：

1. **挂起点不是「遇到 I/O」，而是「await 到一个还没就绪的东西」**。`fetch_jobs()` 缓存命中时直接 return，全程不挂起；`_throttle()` 里 `wait == 0` 时不执行 sleep，也不挂起。
2. **恢复顺序**：事件循环不会「轮转回来傻等 I/O」。挂起的协程完全脱离调度，直到操作系统通知 socket 就绪（Windows 用 IOCP，Linux 用 epoll），事件循环把 Future 标记完成，才重新放进就绪队列。没有轮询，是事件驱动的通知 —— 这才是单线程挂起上千请求不浪费 CPU 的原因。
3. **`async def` ≠ 涉及 I/O 的函数**，只表示「可能挂起」（也可能是等定时器、等锁、等其他任务）。链条底端也不是另一个 `async def`，而是 httpx 内部创建的 **Future**（「将来会有值的占位符」），由事件循环在 I/O 就绪时填值。`await` 后面能跟任何 awaitable：协程、Task、Future，或实现了 `__await__` 的对象。

### 实现要点

```python
async def _get(self, path, params=None) -> dict:
    await self._throttle()                                  # ① 可能等限流
    self.minute_limiter.record()
    self.hour_limiter.record()
    response = await self._client.get(path, params=params)   # ② 等网络 I/O
    response.raise_for_status()
    return response.json()
```

**`asyncio.sleep` 与 `time.sleep` 的致命差别**（限流等待处）：

```python
time.sleep(30)           # 整个线程冻结 30 秒，所有用户请求全部卡死
await asyncio.sleep(30)  # 只有当前请求等待，其他用户照常服务
```

限流触发可能要等几十秒，用错这一行，一个被限流的用户拖垮整个服务。

**传染性**：`await` 只能写在 `async def` 内，所以底层是 async，上层全被逼成 async：

```
路由 async def search()
  └─ await client.fetch_projects()
       └─ await self._get()
            └─ await self._client.get()   ← 真正的 I/O
```

这就是客户端所有公开方法（含 `close()`）都是 `async def` 的原因 —— 不是风格偏好。

### 语法速查

```python
result = client.fetch_jobs()   # ❌ 忘了 await，拿到 <coroutine object>
                               #    不报错，只有 RuntimeWarning，容易忽略

@pytest.mark.asyncio           # pytest 默认不执行协程，需 pytest-asyncio 插件
async def test_xxx(): ...

asyncio.run(main())                       # 顶层入口，创建事件循环
task = asyncio.create_task(fetch_page(1)) # 丢后台跑，不立即等
await asyncio.gather(f1, f2, f3)          # 并发跑多个，总耗时≈最慢那个
```

### 术语与后续

**协作式并发（cooperative concurrency）** —— 任务主动在 `await` 处让出控制权，不是被操作系统抢占。

模块 4 分页抓取会用 `asyncio.gather()` 并发拉多页，5 页只需 800ms 而非 4 秒。

---

## ★3 滑动窗口限流

### 设计缘由

Freelancer API 限制每分钟 50 次，超了返回 429 并可能封 IP，客户端必须自己节流。

朴素方案 —— 固定窗口计数器（每过 60 秒计数归零）有致命缺陷 **边界突刺**：

```
10:00:59  发 50 次   ← 第一个窗口，刚好用满
10:01:00  窗口重置，计数归零
10:01:01  再发 50 次  ← 第二个窗口，也合法

结果：2 秒内发了 100 次。服务端用滑动统计，直接判超限。
```

根源：固定窗口只记「这个窗口发了几次」，**丢失了每次请求发生在什么时刻**的信息，无法回答「最近 60 秒发了几次」。

| 方案 | 问题 |
|------|------|
| 固定窗口计数器 | 边界突刺，2 秒内可能发出 2 倍配额 |
| 令牌桶 | 平滑省内存，但要维护补充速率、浮点累加，实现调试更复杂 |
| **滑动窗口（时间戳列表）** ✅ | 精确直观；代价是存 N 个时间戳（50 个 float ≈ 400 字节，可忽略） |

### 实现要点

核心：**不记次数，记每次请求的时间戳**，判断时只统计落在窗口内的。

```python
def _prune(self, now: float) -> None:
    cutoff = now - self.period                            # 窗口左边界
    self._calls = [t for t in self._calls if t > cutoff]   # 只保留窗口内的

def time_until_available(self) -> float:
    now = time.monotonic()
    self._prune(now)
    if len(self._calls) < self.max_calls:
        return 0                                          # 窗口没满，放行
    oldest = self._calls[0]
    return max(0.0, oldest + self.period - now)           # 等最早那个滑出窗口

def record(self) -> None:
    self._calls.append(time.monotonic())
```

等待时长推导（`period=60`，`max_calls=3` 简化演示）：

```
_calls = [100.0, 130.0, 150.0]   now = 155.0
          ↑ oldest
窗口左边界 = 155 - 60 = 95，三个都 > 95 → 窗口已满

oldest(100.0) 何时滑出？当 now - 60 > 100，即 now > 160
等待 = oldest + period - now = 100 + 60 - 155 = 5 秒
```

- `_calls[0]` 天然是最早的：`record()` 总是 append 到末尾，时间只增不减，列表天然升序，无需排序
- `max(0.0, ...)` 是保险，避免边缘时序算出负数导致 `asyncio.sleep(-1)` 报错

**两个限流器并联**（同一个类，参数不同）：

```python
self.minute_limiter = RateLimiter(max_calls=settings.RATE_LIMIT_PER_MINUTE, period=60)
self.hour_limiter = RateLimiter(max_calls=settings.RATE_LIMIT_PER_HOUR, period=3600)

# _throttle 里对两者都检查，都满足才放行
for limiter in (self.minute_limiter, self.hour_limiter):
    wait = limiter.time_until_available()
    if wait > 0:
        await asyncio.sleep(wait)
```

这就是 `RateLimiter` 不写死 60 秒的原因：参数化 `period` 后一个类复用两处，加第三种限制只需多一行。

### time.monotonic() vs time.time()

- `time.time()`：墙上时钟（Unix 时间戳），**会被回拨** —— NTP 校时、手动改时间、夏令时
- `time.monotonic()`：单调时钟，只增不减，值本身无意义，**只能算差值**

用 `time.time()` 的话，系统时间回拨 1 小时，`now - cutoff` 全乱，限流失效甚至永久卡住。凡「测量间隔」都用 `monotonic`。

### 语法速查

```python
# 列表推导式：[表达式 for 变量 in 可迭代对象 if 条件]
self._calls = [t for t in self._calls if t > cutoff]
# 等价：新建 result 列表，for + if + append，最后赋回
# 注意它创建新列表而非原地修改 —— 边遍历边删是经典 bug 源，重建更安全

for limiter in (a, b):   # (a, b) 是元组（不可变序列）
                         # 表达「固定的两项，不会变」，比 [a, b] 更贴切
```

### 术语与后续

**滑动窗口日志（sliding window log）**，「日志」指保存了每次请求的记录。高配额场景（每秒上万请求）会改用令牌桶/漏桶，因为存时间戳的内存开销会上来。

模块 4 分页抓取时限流器真正生效（抓 20 页会触发分钟级限流并自动 sleep）；模块 6 导出走同一客户端，共享同一套限流状态。

---

## ★4 fetch_projects 的参数翻译

### 设计缘由

这个方法是**业务边界的翻译层**。前端用一套语言描述筛选条件（关键词、技能、预算、类型），Freelancer API 用另一套（`query`、`jobs[]`、`min_price`、`project_types[]`）。

不做翻译的后果：前端要知道 `jobs[]` 这种诡异参数名，要知道「时薪用 `min_hourly_rate`、固定价用 `min_price`」这种 API 私有约定；API 改名整个前端跟着改。

根源：**API 的参数命名是外部系统的实现细节，不该泄漏进我们的领域模型**。

| 方案 | 问题 |
|------|------|
| 前端直接传 API 原生参数 | 细节泄漏，改名要动全栈 |
| 用 dict 透传筛选条件 | 无类型检查、IDE 无提示、拼错 key 静默失败 |
| **显式命名参数 + 内部翻译** ✅ | 类型明确、可补全，API 变更只改这一个方法 |

### 实现要点：三段结构

```python
# ① 固定参数（AC-001 要求，每次都带）
params: List[tuple] = [
    ("job_details", "true"),       # 返回项目关联的技能标签 ← 少了它模块3无法统计技能频率
    ("full_description", "true"),  # 完整描述而非截断
    ("compact", "true"),           # 精简响应体
    ("offset", str(offset)),
    ("limit", str(limit)),
]

# ② 可选筛选（有值才加）
if keywords:
    params.append(("query", keywords))
if jobs:
    for job_id in jobs:
        params.append(("jobs[]", str(job_id)))

# ③ 预算参数的类型分支（核心）
if project_type == "hourly":
    params.append(("min_hourly_rate", str(float(budget_min))))   # 省略 None 判断
else:
    params.append(("min_price", str(float(budget_min))))
```

### 为什么必须分支

| 项目类型 | 预算含义 | API 参数 |
|----------|----------|----------|
| fixed | 整个项目总价 | `min_price` / `max_price` |
| hourly | 每小时费率 | `min_hourly_rate` / `max_hourly_rate` |

用错的后果：给时薪项目传 `min_price=100`，API **静默忽略**该参数，返回全部时薪项目 —— 用户以为筛了预算实际没筛。不报错、只是结果不对，最难发现的 bug 类型。

`else` 覆盖 `"fixed"` 和 `None`（不限类型），因为 API 默认按固定价语义处理。

### 三个易踩细节

**① `is not None` 而非 `if budget_min`**

```python
if budget_min is not None:   # ✅
if budget_min:               # ❌ budget_min=0 会被当成"没传"跳过
```

`0`/`0.0`/`""`/`[]`/`{}` 在 Python 都是 falsy。`0` 是合法最低预算。

对比 `if keywords` —— 那里用 truthy **是故意的**，`""` 和 `None` 都该视为「没有关键词」，无需区分。

**② `str(float(x))` 双重转换**

统一格式。用户可能传 `100`(int) 或 `100.0`(float)，不统一会生成 `min_price=100` 或 `min_price=100.0` 两种 URL，API 都接受但测试断言不稳定。

**③ 元组列表而非字典 —— 因为要支持重复 key**

```python
for job_id in jobs:
    params.append(("jobs[]", str(job_id)))   # → ?jobs[]=3&jobs[]=7
# 字典做不到：{"jobs[]": 3, "jobs[]": 7} 后者覆盖前者
```

注意 `params.append(("query", keywords))` 内层是元组的括号，不是两个参数。

### 补充：query string 拼数组的四种约定

URL query 原生只有 `key=value`，**没有数组语法**，各生态自己约定（都不是标准）：

```
?jobs[]=3&jobs[]=7     方括号后缀   PHP、Rails、Freelancer API
?jobs=3&jobs=7         重复 key     Java Spring、Go、express
?jobs=3,7              逗号分隔     部分 REST API
?jobs[0]=3&jobs[1]=7   带索引       老式 PHP、某些 .NET
```

为什么 GET 不能像 Java 那样把数组放请求体？因为 GET 规范上不该带 body（代理、CDN、fetch API 大多会丢掉），实践中不可用。Java 里常见「请求体放数组」都是 POST/PUT。

Spring 用重复 key（`@RequestParam List<Integer> jobs` 接受 `?jobs=3&jobs=7`），**不认 `jobs[]=3`** —— 会当成名叫 "jobs[]" 的参数，匹配不上，结果空列表。

PHP 发明方括号的原因：它把 query 塞进 `$_GET` 数组，重复 key 会互相覆盖，而动态语言没有 `List<Integer>` 这种类型声明可供推断，只能显式标记「带 `[]` 就当数组」。

### 返回值的安全取值

```python
return data.get("result", {}).get("projects", [])
```

`dict.get(key, 默认值)` 不存在时返回默认值而非抛 `KeyError`。链式：`result` 缺失 → `{}` → `.get("projects", [])` → `[]`。

**取舍**：对**数据缺失**宽容（返回空列表，页面能渲染「无结果」），对 **HTTP 错误**严格（`raise_for_status()` 直接抛，500 是明确故障必须暴露）。

### 术语与后续

**适配器（Adapter）/ 防腐层（Anti-Corruption Layer)** —— 把外部系统的模型隔在边界外，防止腐蚀自己的领域模型。

模块 3 消费这里返回的原始 dict 列表；模块 5 路由层把 `SearchRequest` 的字段解包成这里的命名参数（字段名一致的价值在此体现）。

---

## ○5 CacheEntry 缓存设计

### 设计缘由

要缓存两份数据：

| 数据 | 内容 | 变化频率 |
|------|------|----------|
| 技能标签表 | 全平台约 2000 个技能 | 几个月才增删一次 |
| 汇率表 | 各币种对 USD 汇率 | 每天波动 |

不缓存的后果：用户每搜一次，展示技能下拉框要拉 2000 条技能表，换算预算要拉汇率表 —— 一次搜索变成 3 个 API 请求。

**① 浪费限流配额（硬伤）**。配额只有 50 次/分钟，2 次浪费在几个月不变的数据上。10 个用户同时搜索就是 30 次请求，配额见底，真正的项目搜索被迫 sleep 排队。

**② 白等 800ms**。一次搜索变成三次网络往返。

根源：**数据变化频率与请求频率严重不匹配** —— 几个月变一次的东西被每秒请求好几次。

| 方案 | 问题 |
|------|------|
| 不缓存 | 浪费限流配额（硬伤），响应慢 |
| 硬编码进代码 | 技能表会增删、汇率每天变，不可行 |
| Redis / Memcached | 要部署额外服务、加依赖、配连接。数据仅几百 KB，单进程内存足够 —— 杀鸡用牛刀 |
| `functools.lru_cache` | **不支持过期时间**，缓存了就永久有效；且不适用于 async 函数 |
| **自己写 15 行 CacheEntry** ✅ | 零依赖、逻辑可控、支持 TTL |

判断依据（不过度工程）：需求只要「单进程内存 + 支持过期」，标准库刚好没有直接对应物，自己写比引入 Redis 更合适。

而且明确只有两个 key-value，连传统 LRU 的 `LinkedHashMap` 淘汰结构都不需要 —— 没有容量上限问题，也不需要淘汰策略，只要「值 + 过期时刻」两个字段。

### 实现要点：存「过期时刻」而非「创建时刻」

```python
class CacheEntry:
    def __init__(self, value: Any, ttl: float):
        self.value = value
        self.expires_at = time.monotonic() + ttl      # 创建时算出过期时刻

    @property
    def is_valid(self) -> bool:
        return time.monotonic() < self.expires_at     # 检查时只做一次比较
```

两种存法对比：

```python
# 方式 A：存创建时刻 + TTL
return time.monotonic() - self.created_at < self.ttl   # 每次要减一次再比较

# 方式 B：存过期时刻（本代码采用）
return time.monotonic() < self.expires_at              # 只比较
```

选 B 的真正理由不是性能（差异微不足道），而是**语义直白** —— `expires_at` 一眼知道「何时失效」，调试时打印即可判断，不用心算减法。

同样用 `time.monotonic()`，理由同限流器：系统时间被回拨会导致缓存永久有效或立刻失效。

### 缓存三步曲

```python
async def fetch_jobs(self) -> List[dict]:
    if self._jobs_cache and self._jobs_cache.is_valid:   # ① 查缓存
        return self._jobs_cache.value
    data = await self._get(JOBS_ENDPOINT)                # ② 未命中，请求
    jobs = data.get("result", [])
    self._jobs_cache = CacheEntry(jobs, JOBS_CACHE_TTL)  # ③ 写回缓存
    return jobs
```

`if self._jobs_cache and self._jobs_cache.is_valid` 两重检查缺一不可：

- `self._jobs_cache` — 初始值是 `None`（首次调用还没缓存）。少了它 `None.is_valid` 直接 `AttributeError`
- `.is_valid` — 缓存存在但可能已过期

依赖 `and` 的**短路求值**：左边为假就不求值右边。

### TTL 取值理由

```python
JOBS_CACHE_TTL = 60 * 60            # 1 小时
CURRENCIES_CACHE_TTL = 24 * 60 * 60 # 24 小时
```

写成算式而非 `3600`，一眼看出是「60 秒 × 60 分」。

汇率 TTL 反而更长（24h > 1h），因为汇率日内波动对「预算区间估算」这个用途影响可忽略，而技能表新增标签会直接影响筛选下拉框的完整性。**TTL 取决于「数据过期造成的业务影响」，不是单纯的变化频率。**

### 语法速查

```python
@property
def is_valid(self) -> bool: ...

entry.is_valid      # ✅ 有 @property，像属性一样访问，不加括号
entry.is_valid()    # ❌ 会报 'bool' object is not callable
```

用它的理由：`is_valid` 读起来是一个**状态**（是否有效）而非动作，属性风格更自然。

### 术语与后续

**TTL（Time To Live）缓存 / 进程内缓存（in-process cache）**。局限：多进程部署时每个进程各自一份缓存，命中率下降；但对本项目单进程部署无影响。

模块 3 换算 USD 时会调 `fetch_currencies()`，模块 5 提供技能列表接口时会调 `fetch_jobs()` —— 缓存收益在那时体现。

<!-- CONTINUE_MARKER_A7X -->
