# 数据模型 - backend/models.py

## 文件作用
定义 8 个 Pydantic 数据模型，负责：
1. **类型验证**：自动检查字段类型
2. **JSON 序列化**：Python 对象 ↔ JSON 自动转换
3. **API 文档生成**：FastAPI 自动生成 OpenAPI 文档

---

## 核心知识点

### 1. Pydantic 基础

#### 继承 BaseModel
```python
from pydantic import BaseModel

class Job(BaseModel):
    id: int
    name: str
```

**自动功能：**
```python
# 创建实例（自动验证类型）
job = Job(id=1, name="Python")  # ✅

job = Job(id="abc", name="Python")  # ❌ ValidationError

# 序列化为 JSON
job.model_dump()  # {"id": 1, "name": "Python"}

# 从 JSON 创建对象
job = Job.model_validate({"id": 2, "name": "React"})
```

---

### 2. 字段类型语法

#### 必填字段
```python
id: int
name: str
```

#### 可选字段（可以是指定类型或 None）
```python
from typing import Optional

bid_avg: Optional[float] = None

# 等价写法（Python 3.10+）
bid_avg: float | None = None
```

**使用：**
```python
# 不传 bid_avg（使用默认值 None）
stats = BidStats(bid_count=10)
print(stats.bid_avg)  # None

# 传值
stats = BidStats(bid_count=10, bid_avg=75.5)
```

#### 嵌套模型
```python
class Budget(BaseModel):
    minimum: float
    maximum: float
    currency: Currency  # 另一个 Pydantic 模型

# Pydantic 自动递归验证
budget = Budget(
    minimum=50,
    maximum=100,
    currency={"code": "USD", "exchange_rate": 1.0}  # 字典自动转为 Currency 对象
)
```

---

### 3. Field() 配置函数

#### 设置默认值 + 验证规则
```python
from pydantic import Field

limit: int = Field(default=100, ge=10, le=500)
```

**参数说明：**
- `default=100`：默认值 100
- `ge=10`（greater or equal）：最小值 10
- `le=500`（less or equal）：最大值 500

**工作原理：**
1. **类定义时**：`limit` 被赋值为 `Field` 配置对象（存储在类元数据中）
2. **实例化时**：Pydantic 读取配置对象
   - 没传值 → 使用默认值 100
   - 传了值 → 校验是否在 10-500 范围内
3. **实例的 `limit` 属性是 `int` 类型的值，不是 `Field` 对象**

**验证示例：**
```python
req = SearchRequest()  # limit = 100（默认值）
req = SearchRequest(limit=50)  # ✅
req = SearchRequest(limit=5)   # ❌ ValidationError: limit >= 10
req = SearchRequest(limit=1000) # ❌ ValidationError: limit <= 500
```

---

### 4. 列表字段的默认值（重要陷阱）

#### ❌ 错误写法（Python 经典坑）
```python
class Project(BaseModel):
    jobs: List[Job] = []

# 问题：所有实例共享同一个列表
p1 = Project(id=1, title="A", ...)
p2 = Project(id=2, title="B", ...)
p1.jobs.append(Job(id=1, name="Python"))
print(p2.jobs)  # [Job(id=1, name="Python")] ← 被污染了！
```

**原因：**
- Python 的类成员默认值**在类定义时只执行一次**
- `[]` 创建唯一的列表对象（内存地址固定）
- 所有实例的 `jobs` 都指向同一个地址

#### ✅ 正确写法
```python
jobs: List[Job] = Field(default_factory=list)
```

**工作原理：**
1. **类定义时**：存储函数对象 `list`（不调用）
2. **实例化时**：调用 `list()` 创建新列表

```python
# 每个实例有独立的列表
p1 = Project()
p2 = Project()
p1.jobs.append(Job(id=1, name="Python"))
print(p2.jobs)  # [] ← 独立的空列表
```

---

## 8 个模型类说明

### 1. Job - 技能标签
```python
class Job(BaseModel):
    id: int
    name: str
```
示例：`{"id": 3, "name": "Python"}`

---

### 2. Currency - 货币信息
```python
class Currency(BaseModel):
    code: str
    exchange_rate: float
```
示例：`{"code": "USD", "exchange_rate": 1.0}`

---

### 3. Budget - 预算信息
```python
class Budget(BaseModel):
    minimum: float
    maximum: float
    currency: Currency  # 嵌套模型
```

---

### 4. BidStats - 投标统计
```python
class BidStats(BaseModel):
    bid_count: int
    bid_avg: Optional[float] = None  # 可选字段
```

---

### 5. Project - 项目完整信息
```python
class Project(BaseModel):
    id: int
    title: str
    seo_url: str
    budget: Budget
    jobs: List[Job] = Field(default_factory=list)  # 列表字段
    bid_stats: BidStats
    type: str  # "fixed" or "hourly"
    time_submitted: int  # Unix timestamp
    
    # 计算字段（由数据处理器填充）
    budget_min_usd: Optional[float] = None
    budget_max_usd: Optional[float] = None
    bid_avg_usd: Optional[float] = None
```

---

### 6. SearchRequest - 搜索请求参数
```python
class SearchRequest(BaseModel):
    keywords: Optional[str] = None
    jobs: List[int] = Field(default_factory=list)
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    project_type: Optional[str] = None
    time_range: Optional[int] = None
    limit: int = Field(default=100, ge=10, le=500)  # 带验证规则
```

---

### 7. SearchResponse - 搜索响应
```python
class SearchResponse(BaseModel):
    projects: List[Project]
    total: int
    skills_frequency: dict  # {"Python": 15, "React": 8}
    budget_distribution: dict  # {"$0-$100": 5, "$100-$500": 10}
```

---

### 8. HealthResponse - 健康检查响应
```python
class HealthResponse(BaseModel):
    status: str
    version: str
```
示例：`{"status": "ok", "version": "1.0.0"}`

---

## Pydantic vs 手写验证

### 手写验证（50 行代码）
```python
def validate_request(data):
    if "limit" not in data:
        raise ValueError("limit is required")
    if not isinstance(data["limit"], int):
        raise TypeError("limit must be int")
    if data["limit"] < 10 or data["limit"] > 500:
        raise ValueError("limit must be 10-500")
    # ... 重复 10 个字段
```

### Pydantic（3 行代码）
```python
class SearchRequest(BaseModel):
    limit: int = Field(ge=10, le=500)
```

---

## 常见疑问

**Q: 为什么用 `Field(default_factory=list)` 而不是 `= []`？**
A: Python 的类成员默认值只执行一次，`[]` 会导致所有实例共享同一个列表。`default_factory` 每次调用函数生成新列表。

**Q: `Optional[int]` 和 `int` 有什么区别？**
A: `Optional[int]` = `int | None`（可以是整数或 None），`int` 必须是整数。

**Q: Field() 参数中的 ge/le 是什么意思？**
A: `ge` = greater or equal（>=），`le` = less or equal（<=）。
