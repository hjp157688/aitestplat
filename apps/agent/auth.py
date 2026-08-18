"""http transport 的 Bearer token 鉴权（ASGI 包装）。"""
import hmac


def wrap_auth(app, token: str):
    """包一层 ASGI：http 请求必须带 Authorization: Bearer <token>，否则 401。"""
    async def auth_app(scope, receive, send):
        if scope['type'] == 'http':
            headers = {
                k.decode('latin-1').lower(): v.decode('latin-1')
                for k, v in scope.get('headers', [])
            }
            auth = headers.get('authorization', '')
            scheme, _, value = auth.partition(' ')
            ok = scheme.lower() == 'bearer' and bool(value) and hmac.compare_digest(value, token)
            if not ok:
                await send({
                    'type': 'http.response.start',
                    'status': 401,
                    'headers': [(b'content-type', b'application/json')],
                })
                await send({'type': 'http.response.body', 'body': b'{"error":"unauthorized"}'})
                return
        await app(scope, receive, send)
    return auth_app
