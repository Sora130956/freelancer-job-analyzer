# FastAPI 应用入口 - backend/main.py

## 文件作用
FastAPI 应用的入口文件，完成三件事：
1. 创建 FastAPI 应用实例
2. 配置 CORS 跨域中间件
3. 定义健康检查端点（`/health`）

---

## 核心知识点

### 1. 创建 FastAPI 应用

```python
from fastapi import FastAPI
from backend.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION
)
```

**说明：**
- `app` 是 FastAPI 应用实例（整个应用的核心对象）
- `title` 和 `version` 显示在自动生成的 API 文档中（`/docs`）

**效果：**
访问 `http://localhost:8000/docs` 会看到：
```
标题: Freelancer Job Analyzer
版本: 1.0.0
```

---

### 2. 中间件（Middleware）

#### 什么是中间件？
中间件是**请求和响应之间的处理层**：

```
前端发送请求
    ↓
[CORS 中间件] ← 检查来源，决定是否允许
    ↓
路由处理函数（/health）
    ↓
[CORS 中间件] ← 添加 CORS 响应头
    ↓
返回响应给前端
```

#### 配置 CORS 中间件
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # ["*"] 允许所有域名
    allow_credentials=True,               # 允许发送 Cookies
    allow_methods=["*"],                  # 允许所有 HTTP 方法
    allow_headers=["*"],                  # 允许所有请求头
)
```

**参数说明：**

| 参数 | 含义 | 示例 |
|------|------|------|
| `allow_origins` | 允许哪些域名调用后端 | `["*"]` 或 `["http://localhost:5173"]` |
| `allow_credentials` | 是否允许发送认证信息 | `True`（需要登录功能时必须开启） |
| `allow_methods` | 允许哪些 HTTP 方法 | `["*"]` 或 `["GET", "POST"]` |
| `allow_headers` | 允许哪些请求头 | `["*"]` 或 `["Content-Type", "Authorization"]` |

---

### 3. CORS 跨域问题

#### 什么是跨域？
前端和后端的**域名、端口、协议**任一不同就是跨域：

```
前端: http://localhost:5173
后端: http://localhost:8000
→ 端口不同，属于跨域
```

#### CORS 工作流程
```
1. 前端发送请求: POST http://localhost:8000/api/search
2. 浏览器发现跨域，先发送预检请求（OPTIONS）
3. 后端 CORS 中间件检查 allow_origins
4. 后端返回: Access-Control-Allow-Origin: http://localhost:5173
5. 浏览器检查：后端允许跨域 ✅
6. 浏览器放行真实的 POST 请求
```

**如果没有配置 CORS：**
```
Access to fetch at 'http://localhost:8000/api/search' 
from origin 'http://localhost:5173' has been blocked by CORS policy
```

---

### 4. 路由装饰器（Route Decorator）

```python
@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok", version=settings.APP_VERSION)
```

#### 装饰器语法
```python
@app.get("/health")
def health_check():
    pass

# 等价于
def health_check():
    pass
health_check = app.get("/health")(health_check)
```

**作用：**
- 将函数注册为路由处理器
- 当访问 `GET /health` 时，自动调用 `health_check()` 函数

#### 常用装饰器
```python
@app.get("/path")    # GET 请求
@app.post("/path")   # POST 请求
@app.put("/path")    # PUT 请求
@app.delete("/path") # DELETE 请求
```

---

### 5. 异步函数（async/await）

```python
async def health_check():
    return {"status": "ok"}
```

**同步 vs 异步：**

| 类型 | 语法 | 特点 |
|------|------|------|
| **同步函数** | `def func()` | 一个请求处理完才能处理下一个（阻塞） |
| **异步函数** | `async def func()` | 可以同时处理多个请求（非阻塞） |

**为什么用 `async`？**
1. **性能更好**：可以同时处理多个请求
2. **必须配合异步库**：后续会用 `httpx`（异步 HTTP 客户端）
3. **FastAPI 推荐**：官方文档推荐优先使用异步函数

---

### 6. 响应模型（response_model）

```python
@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok", version="1.0.0")
```

**`response_model` 的作用：**
1. **自动验证**：检查返回值是否符合 `HealthResponse` 模型
2. **自动序列化**：将 Pydantic 对象转为 JSON
3. **生成文档**：在 `/docs` 中显示响应示例

**FastAPI 自动处理流程：**
```python
# 1. 函数返回 HealthResponse 对象
return HealthResponse(status="ok", version="1.0.0")

# 2. FastAPI 自动转为字典
{"status": "ok", "version": "1.0.0"}

# 3. 转为 JSON 字符串
'{"status":"ok","version":"1.0.0"}'

# 4. 设置响应头
Content-Type: application/json

# 5. 返回给客户端
```

---

## 完整代码结构

```python
# 1. 创建应用
app = FastAPI(title="...", version="...")

# 2. 配置中间件
app.add_middleware(CORSMiddleware, ...)

# 3. 定义路由
@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok", version=settings.APP_VERSION)
```

---

## 运行和测试

### 启动服务器
```powershell
uvicorn backend.main:app --reload
```

**参数说明：**
- `backend.main:app`：模块路径 + 应用变量名
- `--reload`：代码改动后自动重启（开发模式）

### 测试健康检查
```powershell
curl http://localhost:8000/health
```

**返回：**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

### 查看 API 文档
浏览器访问：`http://localhost:8000/docs`

自动生成的内容：
- 应用标题和版本
- 所有端点列表
- 每个端点的请求/响应示例
- 可以直接在浏览器测试 API

---

## 常见疑问

**Q: 为什么要配置 CORS？**
A: 前端和后端在不同端口，浏览器会拦截跨域请求。CORS 中间件告诉浏览器"允许跨域"。

**Q: `async` 函数和普通函数有什么区别？**
A: `async` 函数可以在等待 I/O 操作时处理其他请求，性能更好。后续模块会用到异步 HTTP 请求。

**Q: `response_model` 是必须的吗？**
A: 不是必须，但强烈推荐。它能自动验证返回值、生成文档、提供类型检查。

**Q: 装饰器 `@app.get` 是怎么工作的？**
A: 装饰器将函数注册到 FastAPI 的路由表中。当请求到达时，FastAPI 根据路径和方法找到对应的函数并调用。
