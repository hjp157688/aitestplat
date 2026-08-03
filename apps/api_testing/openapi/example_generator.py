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
                result[prop_name] = 'string'
        return result

    elif schema_type == 'array':
        items_schema = schema.get('items', {})
        item = generate_example(items_schema)
        return [item] if item is not None else ['string']

    elif schema_type == 'string':
        if 'format' in schema:
            return FORMAT_EXAMPLES.get(schema['format'], 'string')
        return 'string'

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
