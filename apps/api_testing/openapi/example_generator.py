# apps/api_testing/openapi/example_generator.py
"""从 JSON Schema 生成有意义的示例值"""

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

# OpenAPI Example Object 的已知字段（用于识别 named examples 包裹层）
_EXAMPLE_OBJECT_KEYS = {'summary', 'value', 'description', 'externalValue'}


def first_example_value(examples):
    """从 parameters/requestBody 的 examples 映射中取首个示例值

    兼容两种形态：
    - {'application/json': {...}} 媒体类型 → 值映射
    - {'NamedExample': {'value': {...}, 'summary': ...}} 命名 Example Object

    Args:
        examples: dereferenced examples 字段

    Returns:
        首个示例值；无可用值时返回 None
    """
    if not examples or not isinstance(examples, dict):
        return None
    for value in examples.values():
        # 命名 Example Object 包裹层：仅含 Example Object 词汇的键时解包出 value
        if (isinstance(value, dict) and 'value' in value
                and set(value.keys()) <= _EXAMPLE_OBJECT_KEYS):
            return value['value']
        return value
    return None


def generate_example(schema: dict):
    """从 JSON Schema 生成有意义的示例值

    优先级: example > default > enum[0] > 类型默认值

    Args:
        schema: dereferenced JSON Schema dict

    Returns:
        生成的示例值，无法生成时返回 None
    """
    if not isinstance(schema, dict):
        return None

    if 'example' in schema:
        return schema['example']
    if 'default' in schema:
        return schema['default']
    if 'enum' in schema and schema['enum']:
        return schema['enum'][0]

    schema_type = schema.get('type', 'object')

    if schema_type == 'object':
        result = {}
        properties = schema.get('properties', {})
        for prop_name, prop_schema in properties.items():
            val = generate_example(prop_schema)
            if val is not None:
                result[prop_name] = val
            else:
                # 无任何示例提示的字段留空而不是填 'string' 占位文本
                result[prop_name] = ''
        return result

    elif schema_type == 'array':
        items_schema = schema.get('items', {})
        item = generate_example(items_schema)
        return [item] if item is not None else ['']

    elif schema_type == 'string':
        if 'format' in schema:
            return FORMAT_EXAMPLES.get(schema['format'], '')
        # 无 example/default/enum/format 的 string 字段留空，不造假 'string' 值
        return ''

    elif schema_type == 'integer':
        minimum = schema.get('minimum')
        if minimum is not None:
            return minimum
        return 1

    elif schema_type == 'number':
        minimum = schema.get('minimum')
        if minimum is not None:
            return float(minimum)
        return 1.0

    elif schema_type == 'boolean':
        return False

    return None
