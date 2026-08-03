# OpenAPI 导入解析与前端展示优化设计

**日期**: 2026-08-03
**状态**: 设计完成

---

## 1. 背景与问题

### 1.1 当前问题

**后端解析**（`apps/api_testing/services.py`）：

| 问题 | 影响 |
|------|------|
| 手写 `$ref` 解析，不支持外部引用、循环引用 | 复杂 OpenAPI 文档解析失败或丢失数据 |
| `allOf`/`oneOf`/`anyOf` 处理过于简单 | schema 继承/多态无法正确解析 |
| 安全认证（Security Schemes）未提取 | 导入的接口缺少认证头，无法直接发送 |
| schema 示例生成返回 `'string'` 占位符或 `{}` | 前端 Body tab 显示为空 |
| 路径参数直接替换为示例值 | 丢失 URL 模板信息 |
| 不支持 cookie 参数、操作级 servers、deprecated 标记 | 部分 OpenAPI 3.0 特性缺失 |

**前端显示**：

| 问题 | 影响 |
|------|------|
| `KeyValueEditor` prop 类型 `Object` 不接受数组 | Headers/Params 显示为空 |
| Body tab 显示 `{}` 或无内容 | 用户无法了解接口 body 结构 |
| 无法查看原始 schema 定义 | 用户不知道接口的完整数据结构 |
| 无认证信息展示 | 用户不知道接口需要哪些认证 |
| 导入预览信息太少 | 只有 method + path + summary |

### 1.2 目标

- 后端解析覆盖 OpenAPI 3.0/3.1 和 Swagger 2.0 的完整特性
- 前端展示达到 Apifox 级别的数据完整性
- 使用成熟的 Python 开源库处理 `$ref` 解析

---

## 2. 技术方案

### 2.1 选型：prance + 自定义管线

使用 [prance](https://pypi.org/project/prance/) 库负责 `$ref` 引用解析，自定义管道式转换器将 dereferenced spec 转为 `ApiRequest` 数据。

**新增依赖**：
```txt
prance>=0.22.0  # OpenAPI spec parsing & $ref dereferencing
```

### 2.2 后端架构：四阶段管道

```
OpenAPI 文件 (JSON/YAML)
        │
        ▼
┌─────────────────────────────┐
│ 1. SpecLoader               │
│    使用 prance.ResolvingParser│
│    · 解析 JSON/YAML          │
│    · 解析所有 $ref           │
│    · Swagger 2.0 → 3.0 转换  │
│    输出: dereferenced spec   │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 2. SecurityExtractor        │
│    · 解析 components/       │
│      securitySchemes        │
│    · 匹配 operation.security│
│    · 生成认证请求头          │
│    输出: auth_headers[]      │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 3. EndpointExtractor        │
│    · 遍历 paths              │
│    · 提取 parameters:        │
│      query/path/header/cookie│
│    · 提取 requestBody        │
│    · 提取 responses schema   │
│    · 提取 servers / deprecated│
│    输出: endpoints[]         │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 4. RequestConverter         │
│    · schema → example 生成  │
│    · 组装 headers[]          │
│    · 组装 params[]           │
│    · 组装 body{type,data}    │
│    · 保留路径参数 {{param}}  │
│    输出: ApiRequest 创建数据 │
└──────────────┬──────────────┘
               │
               ▼
        ApiRequest.objects.create()
```

### 2.3 各阶段详细设计

#### 阶段 1：SpecLoader

```python
class SpecLoader:
    """使用 prance 加载并 dereference OpenAPI spec"""

    def load(self, file_path: str) -> dict:
        import prance
        parser = prance.ResolvingParser(
            file_path,
            backend='openapi-spec-validator',  # 严格校验
            strict=False,  # 非严格模式，容忍部分不规范 spec
        )
        parser.parse()
        return parser.specification  # 完全 dereferenced 的 dict
```

#### 阶段 2：SecurityExtractor

```python
class SecurityExtractor:
    """提取安全认证方案并转为请求头"""

    def extract(self, spec: dict) -> dict:
        """
        返回格式:
        {
            "global": [  # 全局安全方案
                {"key": "Authorization", "value": "Bearer {{bearer_token}}",
                 "enabled": True, "description": "BearerAuth"}
            ],
            "by_operation": {  # 按 operationId 索引
                "createPet": [{"key": "X-API-Key", "value": "{{api_key}}", ...}]
            }
        }
        """
```

安全方案 → 请求头映射：

| 安全方案类型 | 生成的 Header |
|-------------|--------------|
| `http/bearer` | `Authorization: Bearer {{bearer_token}}` |
| `http/basic` | `Authorization: Basic {{basic_auth}}` |
| `apiKey/header` | `<name>: {{api_key}}` |
| `apiKey/query` | 转为 query 参数 |
| `oauth2` | `Authorization: Bearer {{oauth_token}}` |
| `openIdConnect` | `Authorization: Bearer {{oidc_token}}` |

#### 阶段 3：EndpointExtractor

```python
class EndpointExtractor:
    """从 dereferenced spec 中提取所有端点"""

    def extract(self, spec: dict) -> list[dict]:
        """
        返回格式:
        [{
            "path": "/pets",
            "method": "GET",
            "summary": "查询宠物列表",
            "description": "返回所有宠物",
            "operation_id": "listPets",
            "tags": ["pets"],
            "deprecated": False,
            "parameters": [
                {"name": "limit", "in": "query", "required": False,
                 "schema": {"type": "integer", "default": 10},
                 "description": "分页大小"},
            ],
            "request_body": {
                "content_type": "application/json",
                "schema": {"type": "object", "properties": {...}},
                "example": {"name": "doggie", ...},
                "required": True,
            },
            "response_schemas": {
                "200": {"type": "object", "properties": {...}},
                "400": {"type": "object", ...},
            },
            "security": [{"BearerAuth": []}],
            "servers": [{"url": "https://api.example.com/v2"}],
        }]
        """
```

新增提取：
- **cookie 参数**：OpenAPI 3.0 的 `in: cookie` 参数
- **操作级 servers**：覆盖全局 servers 的 base URL
- **deprecated**：标记废弃接口
- **response_schemas**：响应的 JSON Schema，用于前端 Schema 预览

#### 阶段 4：RequestConverter

```python
class RequestConverter:
    """将 endpoint 转为 ApiRequest 创建数据"""

    def convert(self, endpoint: dict, auth_headers: list,
                base_url: str) -> dict:
        """
        返回格式:
        {
            "name": "查询宠物列表",
            "method": "GET",
            "url": "{{baseUrl}}/pets",
            "headers": [
                {"key": "Accept", "value": "application/json", ...},
                {"key": "Authorization", "value": "Bearer {{bearer_token}}", ...},
            ],
            "params": [
                {"key": "limit", "value": "10", "enabled": False, ...},
            ],
            "body": {"type": "none", "data": {}},  # GET 无 body
            "auth_spec": {"type": "bearer", ...},
            "request_schema": {...},
            "response_schemas": {...},
            "deprecated": False,
        }
        """
```

**schema → example 生成改进**：

```python
def generate_example(schema: dict) -> Any:
    """从 JSON Schema 生成有意义的示例值"""
    if 'example' in schema:
        return schema['example']
    if 'default' in schema:
        return schema['default']
    if 'enum' in schema:
        return schema['enum'][0]

    schema_type = schema.get('type', 'object')

    if schema_type == 'object':
        result = {}
        for prop, prop_schema in schema.get('properties', {}).items():
            result[prop] = generate_example(prop_schema)
        return result

    elif schema_type == 'array':
        items = schema.get('items', {})
        return [generate_example(items)]

    elif schema_type == 'string':
        if 'format' in schema:
            return FORMAT_EXAMPLES.get(schema['format'], 'string')
        return 'string'  # 有意义的占位符，而非空字符串

    elif schema_type == 'integer':
        return schema.get('minimum', 1)

    elif schema_type == 'number':
        return schema.get('minimum', 1.0)

    elif schema_type == 'boolean':
        return False

    return None
```

`FORMAT_EXAMPLES` 映射表：

```python
FORMAT_EXAMPLES = {
    'date': '2024-01-01',
    'date-time': '2024-01-01T00:00:00Z',
    'email': 'user@example.com',
    'uri': 'https://example.com',
    'url': 'https://example.com',
    'uuid': '550e8400-e29b-41d4-a716-446655440000',
    'hostname': 'example.com',
    'ipv4': '192.168.1.1',
    'ipv6': '::1',
    'byte': 'U3dhZ2dlciByb2Nrcw==',
    'binary': 'binary',
    'password': 'password123',
    'phone': '+86-13800138000',
}
```

**路径参数处理**：保留 `{param}` 模板：
```python
# 之前：url = url.replace('{' + key + '}', value)
# 之后：保留 {petId}，让用户看到完整路径模板
url = "{{baseUrl}}/pets/{petId}"  # 不替换，保留模板
```

### 2.4 数据模型变更

`apps/api_testing/models.py` 中 `ApiRequest` 新增字段：

```python
class ApiRequest(models.Model):
    # ... 现有字段保持不变 ...

    # 新增字段
    auth_spec = models.JSONField(default=dict, verbose_name='认证配置')
    # 格式: {"type": "bearer", "scheme": "bearer", "header_name": "Authorization",
    #        "header_value": "Bearer {{bearer_token}}"}

    request_schema = models.JSONField(default=dict, verbose_name='请求体Schema')
    # 存储原始 JSON Schema，用于 Schema 预览

    response_schemas = models.JSONField(default=dict, verbose_name='响应Schema')
    # 格式: {"200": {"type": "object", "properties": {...}}, "400": {...}}

    deprecated = models.BooleanField(default=False, verbose_name='是否已废弃')
```

### 2.5 文件结构

```
apps/api_testing/
├── services.py              # 保留，但 OpenAPIParser 改为调用新模块
├── openapi/                 # 新增 openapi 包
│   ├── __init__.py
│   ├── loader.py            # SpecLoader (prance)
│   ├── security.py          # SecurityExtractor
│   ├── endpoints.py         # EndpointExtractor
│   ├── converter.py         # RequestConverter
│   └── example_generator.py # Schema → Example 生成器
├── models.py                # 修改：新增 3 个字段
├── serializers.py           # 修改：ApiRequestSerializer 新增字段
├── views.py                 # 修改：导入接口适配新字段
└── urls.py                  # 无需改动
```

---

## 3. 前端设计

### 3.1 导入预览增强

`ImportOpenApiDialog.vue` 预览从三列扩展到五列，增加 params/body/auth 摘要：

```
┌─────────────────────────────────────────────────────────┐
│ 解析结果: Petstore API (OpenAPI 3.0)                     │
│ 45 个接口 · Base URL: https://api.example.com            │
├─────────────────────────────────────────────────────────┤
│ ▼ pets (12)                                             │
│   GET    /pets          查询宠物列表    Query: limit...  │
│   POST   /pets          创建宠物       Body: JSON       │
│   GET    /pets/{petId}  查询宠物详情    Path: petId      │
│ ▼ users (8)                                              │
│   GET    /users         用户列表       Auth: Bearer      │
│   POST   /users         创建用户       Auth: Bearer      │
└─────────────────────────────────────────────────────────┘
```

### 3.2 接口详情页（Apifox 风格）

`InterfaceManagement.vue` tabs 调整：

```
Params │ Headers │ Body │ Auth │ Schema │ Pre-request │ Tests │ Assert
```

**Headers tab** — 自动填入认证头 + 自定义头：

```
☑ Accept           application/json
☑ Content-Type     application/json
☑ Authorization    Bearer {{bearer_token}}    ← 从 securitySchemes 提取
☑ X-Request-Id     {{request_id}}             ← 从 header 参数提取
[+ 添加]
```

**Body tab** — 支持表格编辑 + raw 双模式切换：

导入的 JSON body 默认以**表格模式**展示，每行一个字段，可直接编辑 key/value：

```
POST /pets:
● json  ○ form-data  ○ urlencoded  ○ raw  ○ none
┌──────────────────────────────────────────────────┐
│ ☑ name          doggie      string               │
│ ☑ species       dog         enum: cat, dog, bird  │
│ ☑ age           3           integer              │
│ [+ 添加行]                                       │
│                                                  │
│ 点击某行 value 可编辑，嵌套对象 value 显示为 JSON  │
│ 字符串，可展开到 raw 编辑器修改                    │
└──────────────────────────────────────────────────┘
```

对于**嵌套对象/数组**，表格模式展平到顶层字段：

```
POST /order:
● json  ○ form-data  ○ urlencoded  ○ raw  ○ none
┌──────────────────────────────────────────────────────┐
│ ☑ userId       123           integer                │
│ ☑ items        [{"id":1}]    array → 点击切换 raw 编辑│
│ ☑ address      {"city":"BJ"} object → 点击切换 raw 编辑│
│ [+ 添加行]                                          │
└──────────────────────────────────────────────────────┘
```

用户可以**一键切换到 raw 模式**直接编辑原始 JSON（当前已有的 raw 编辑器）。

**Schema 提示**：每行右侧显示从 OpenAPI schema 提取的类型/约束信息（如 `required`、`enum`、`format`），与 Apifox 的字段描述列类似。

**实现方式**：在 `onNodeClick` 中，当 body.type === 'json' 时，默认调用 `setBodyFromJson(data)` 进入表格模式。嵌套字段的 value 显示为 `JSON.stringify()` 后的字符串，用户可点击切换到 raw 编辑器修改。现有 `bodyType` 切换逻辑保持不变。

**Params tab** — 自动填入 query/path 参数：

```
☐ limit           10          分页大小
☐ offset          0           偏移量
☐ status          available   状态过滤
[+ 添加]
```

**Auth tab**（新增）— 展示认证配置：

```
认证类型: Bearer Token
┌──────────────────────────────────────┐
│ ☑ Authorization    Bearer {{bearer_token}} │
│ 来源: OpenAPI securitySchemes.BearerAuth   │
└──────────────────────────────────────┘
```

**Schema tab**（新增）— JSON Schema 树形展示：

```
请求体 Schema:
▼ Pet
  ├─ name: string               required
  ├─ species: string            enum: cat, dog, bird
  └─ age: integer

响应 Schema (200):
▼ Pet
  ├─ id: integer
  ├─ name: string
  └─ species: string

响应 Schema (400):
▼ Error
  ├─ code: integer
  └─ message: string
```

### 3.3 左侧树节点优化

- 废弃接口显示灰色 + 删除线样式
- 方法标签颜色保持不变

### 3.4 前端文件改动清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `KeyValueEditor.vue` | 修改 | prop 类型 `[Object, Array]`（已修复） |
| `InterfaceManagement.vue` | 修改 | 新增 Auth、Schema tab；树节点废弃样式 |
| `ImportOpenApiDialog.vue` | 修改 | 预览表格增加列 |
| `locales/zh-cn/api-testing.js` | 修改 | 新增 i18n 词条 |
| `locales/en/api-testing.js` | 修改 | 新增 i18n 词条 |

---

## 4. 兼容性

### 4.1 向后兼容

- 现有 `ApiRequest` 记录不受影响（新字段有默认值）
- `ApiRequestSerializer` 新增字段为只读或可选
- 旧导入的接口在打开时不显示 Schema/Auth tab（新字段为空）

### 4.2 数据一致性注意事项

- `params` 和 `headers` 在导入时存储为**数组格式** `[{key, value, enabled, description}]`，这与 `KeyValueEditor` 的 `v-model` 格式一致（已通过 prop 类型修复解决）
- `saveRequest` 函数将 `params` 转为 dict 格式存储，导致格式不一致。本次实现中 `RequestConverter` 统一输出数组格式，与 `KeyValueEditor` 保持一致

### 4.3 Swagger 2.0 兼容

- prance 自动将 Swagger 2.0 转换为 OpenAPI 3.0 格式
- `host` + `basePath` + `schemes` → `servers[0].url`
- `definitions` → `components/schemas`
- `body parameter` → `requestBody`

---

## 5. 测试要点

### 5.1 后端测试

- [ ] 解析 OpenAPI 3.0/3.1 spec（JSON + YAML）
- [ ] 解析 Swagger 2.0 spec
- [ ] `$ref` 内部引用（循环引用、嵌套引用）
- [ ] `$ref` 外部文件引用
- [ ] `allOf`/`oneOf`/`anyOf` schema 继承
- [ ] 安全方案提取（bearer/apiKey/basic/oauth2）
- [ ] 操作级 security 覆盖全局 security
- [ ] cookie 参数提取
- [ ] 操作级 servers 覆盖
- [ ] schema 示例生成（各种类型 + format）
- [ ] 空 body 的接口（GET/DELETE）

### 5.2 前端测试

- [ ] 导入预览显示完整信息
- [ ] Headers tab 包含认证头
- [ ] Body tab 默认表格模式展示示例数据
- [ ] Body tab 表格模式与 raw 模式一键切换
- [ ] 嵌套对象/数组在表格中显示为 JSON 字符串，可点击切换 raw 编辑
- [ ] Params tab 显示 query 参数
- [ ] Auth tab 显示认证配置
- [ ] Schema tab 树形展示
- [ ] 废弃接口在树中灰显
- [ ] 切换不同接口时数据正确更新