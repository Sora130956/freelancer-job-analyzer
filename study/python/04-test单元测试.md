# 单元测试 - tests/test_main.py

## 文件作用
使用 pytest 框架测试 FastAPI 应用：
1. 测试健康检查端点（`/health`）
2. 测试 CORS 跨域配置

---

## 核心知识点

### 1. pytest 测试框架

#### 命名约定
```python
# ✅ pytest 会自动发现并运行
def test_health_endpoint():
    pass

def test_another_feature():
    pass

# ❌ pytest 不会运行（不是 test_ 开头）
def check_something():
    pass
```

#### 运行测试
```powershell
pytest tests/                              # 运行所有测试
pytest tests/test_main.py                  # 运行单个文件
pytest tests/test_main.py::test_health_endpoint  # 运行单个测试
pytest tests/ -v                           # 详细输出
```

---

### 2. TestClient（测试客户端）

```python
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
response = client.get("/health")  # 不需要启动服务器
```

**TestClient 是什么？**
- FastAPI 提供的测试工具
- 模拟 HTTP 请求（不需要真正启动服务器）
- 直接调用应用内部逻辑

**支持的方法：**
```python
client.get("/path")
client.post("/path", json={...})
client.put("/path", json={...})
client.delete("/path")
client.options("/path", headers={...})
```

**对比真实请求：**
```python
# 真实场景（需要启动服务器）
import requests
response = requests.get("http://localhost:8000/health")

# 测试场景（不需要启动服务器）
from fastapi.testclient import TestClient
client = TestClient(app)
response = client.get("/health")
```

---

### 3. 断言（assert）

```python
assert response.status_code == 200
assert data["status"] == "ok"
assert "version" in data
```

**工作原理：**
```python
# 条件为 True → 什么都不做
assert 1 + 1 == 2  # ✅ 通过

# 条件为 False → 抛出 AssertionError
assert 1 + 1 == 3  # ❌ AssertionError
```

**pytest 如何判断测试结果：**
- 所有 `assert` 通过 → 测试通过 ✅
- 任何一个 `assert` 失败 → 测试失败 ❌

**常用断言模式：**
```python
# 相等性
assert x == y

# 包含性
assert "key" in dict
assert item in list

# 类型检查
assert isinstance(x, int)

# 布尔值
assert x is True
assert x is not None
```

---

### 4. Response 对象

```python
response = client.get("/health")

# 常用属性和方法
response.status_code  # HTTP 状态码（200, 404, 500）
response.json()       # 解析 JSON 响应体
response.headers      # 响应头字典
response.text         # 原始响应文本
```

---

## 测试 1：健康检查端点

```python
def test_health_endpoint():
    """Test health check endpoint returns correct status."""
    from backend.main import app
    
    client = TestClient(app)
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert data["version"] == "1.0.0"
```

**测试步骤：**
1. 创建测试客户端
2. 发送 GET 请求到 `/health`
3. 检查状态码是否为 200
4. 解析 JSON 响应
5. 验证响应数据的结构和内容

---

## 测试 2：CORS 中间件

```python
def test_cors_middleware():
    """Test CORS middleware is configured."""
    from backend.main import app
    
    client = TestClient(app)
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        }
    )
    
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
```

### 为什么测试 OPTIONS 请求？

**CORS 预检流程：**
```
1. 前端: POST http://localhost:8000/api/search
2. 浏览器: 检测到跨域，先发送 OPTIONS 预检
3. 后端: 返回 Access-Control-Allow-Origin: *
4. 浏览器: 检查通过，放行真实的 POST 请求
```

**测试模拟了浏览器的预检请求：**
- `Origin: http://localhost:3000`：请求来自哪个域名
- `Access-Control-Request-Method: GET`：真实请求用什么方法

**后端应该返回的响应头：**
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, PUT, DELETE
Access-Control-Allow-Headers: *
```

---

## pytest 运行流程

### 执行测试
```powershell
pytest tests/test_main.py -v
```

### 输出示例
```
tests/test_main.py::test_health_endpoint PASSED          [50%]
tests/test_main.py::test_cors_middleware PASSED          [100%]

==================== 2 passed in 0.39s ====================
```

**pytest 做了什么？**
1. 扫描 `tests/` 目录的所有 `test_*.py` 文件
2. 发现 `test_` 开头的函数
3. 依次执行每个测试
4. 收集 `assert` 结果
5. 生成测试报告

---

## TDD（测试驱动开发）流程

```
1. 写测试（描述期望的行为）
   def test_health_endpoint():
       response = client.get("/health")
       assert response.status_code == 200

2. 运行测试（应该失败）
   pytest → FAILED

3. 写实现（让测试通过）
   @app.get("/health")
   def health_check():
       return {"status": "ok"}

4. 运行测试（现在应该通过）
   pytest → PASSED

5. 重构（优化代码，测试保护）
```

---

## 测试的价值

### 为什么要写测试？

1. **自动验证功能**：不需要手动 curl 测试
2. **防止回归**：修改代码后运行测试，确保没破坏现有功能
3. **文档作用**：测试代码展示 API 的正确用法
4. **重构信心**：有测试保护，可以放心重构

---

### 手动测试 vs 自动化测试

#### 手动测试
```powershell
# 1. 启动服务器
uvicorn backend.main:app

# 2. 打开另一个终端
curl http://localhost:8000/health

# 3. 检查输出
{"status":"ok","version":"1.0.0"}

# 4. 重复 10 次...每次修改代码都要重新测试
```

#### 自动化测试
```powershell
# 一个命令，自动运行所有测试
pytest tests/ -v

# 输出
test_health_endpoint PASSED
test_cors_middleware PASSED
2 passed in 0.39s
```

---

## 常见疑问

**Q: 为什么 `from backend.main import app` 在函数内部？**
A: 避免循环导入。如果在文件顶部导入，可能导致模块加载顺序问题。

**Q: TestClient 和真实 HTTP 请求有什么区别？**
A: TestClient 直接调用应用内部逻辑（不经过网络），速度更快，适合单元测试。

**Q: pytest 如何发现测试文件？**
A: 扫描 `tests/` 目录下的 `test_*.py` 文件，查找 `test_` 开头的函数。

**Q: assert 失败后会继续执行吗？**
A: 不会。第一个 assert 失败后，pytest 会停止当前测试函数，继续下一个测试。
