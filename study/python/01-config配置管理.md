# 配置管理 - backend/config.py

## 文件作用
管理应用配置（API 地址、限流参数、CORS 策略）

---

## 核心知识点

### 1. 环境变量读取
```python
FREELANCER_API_BASE_URL: str = os.getenv(
    "FREELANCER_API_BASE_URL",
    "https://www.freelancer.com"
)
```

**说明：**
- `os.getenv("KEY", "默认值")` 从操作系统环境变量读取
- 本地开发用默认值，生产部署通过环境变量覆盖

**环境变量来源：**
```powershell
# PowerShell 临时设置
$env:FREELANCER_API_BASE_URL="https://api.freelancer.com"

# Render Dashboard: Environment Variables → Add
# Docker: docker run -e KEY=VALUE
```

---

### 2. 类型注解（Type Hints）
```python
RATE_LIMIT_PER_MINUTE: int = 50
```

**格式：** `变量名: 类型 = 值`

**作用：**
- IDE 自动补全和错误检查
- 纯文档作用，运行时不强制

---

### 3. CORS 跨域配置
```python
CORS_ORIGINS: List[str] = ["*"]
```

**关键理解：**
- CORS 配置写在**后端**，控制"**谁能调我**"
- `["*"]` = 允许任何域名的前端调用后端（开发方便，生产不安全）
- 生产环境建议白名单：`["http://localhost:5173", "https://yourdomain.com"]`

**跨域流程：**
```
前端（http://localhost:5173）
    ↓ 发送请求
后端（http://localhost:8000）← 检查 CORS_ORIGINS
    ↓ 请求来源在白名单？
    ✅ 允许 / ❌ 浏览器拦截
```

---

### 4. 单例模式
```python
class Settings:
    RATE_LIMIT = 1000

settings = Settings()  # 模块级变量，全局共享
```

**为什么要实例化？**
1. **扩展性**：未来可以传参数创建不同环境配置
2. **一致性**：Python 习惯用法
3. **可升级**：可以改为继承 `pydantic.BaseSettings`

**使用方式：**
```python
# 其他模块导入
from backend.config import settings

print(settings.RATE_LIMIT_PER_MINUTE)  # 50
```

---

## 配置类完整结构
```python
class Settings:
    # API 设置
    FREELANCER_API_BASE_URL: str = os.getenv(...)
    
    # 限流参数（硬编码，API 提供方的限制）
    RATE_LIMIT_PER_MINUTE: int = 50
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # CORS 跨域白名单
    CORS_ORIGINS: List[str] = ["*"]
    
    # 应用元信息
    APP_NAME: str = "Freelancer Job Analyzer"
    APP_VERSION: str = "1.0.0"

settings = Settings()  # 创建单例
```

---

## 常见疑问

**Q: 为什么限流参数不用环境变量？**
A: 这是 Freelancer API 的硬性限制，不是可配置项。用环境变量可能被误改导致封禁。

**Q: CORS 配置能控制后端向外发请求吗？**
A: 不能。CORS 只控制"谁能调我的后端"，不限制后端主动发起的请求。

**Q: `List[str]` 和 `list[str]` 有区别吗？**
A: Python 3.9+ 两种写法等价。旧版本只能用 `from typing import List`。
