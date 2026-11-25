"""Tiny ASGI test client (httpx is not installed in this environment)."""
import asyncio
import re
import uuid
from http.cookies import SimpleCookie
from urllib.parse import urlencode, urlsplit


class Response:
    def __init__(self, status, headers, body):
        self.status_code, self.headers, self.content = status, headers, body

    @property
    def text(self):
        return self.content.decode("utf-8", "replace")

    @property
    def location(self):
        return self.headers.get("location")


class Client:
    def __init__(self, app):
        self.app, self.cookies = app, {}

    def _multipart(self, data, files):
        b = uuid.uuid4().hex
        parts = []
        for k, v in (data or {}).items():
            parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        for k, (fn, content, ct) in (files or {}).items():
            parts.append((f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{fn}"\r\n'
                          f'Content-Type: {ct}\r\n\r\n').encode() + content + b"\r\n")
        parts.append(f"--{b}--\r\n".encode())
        return b"".join(parts), f"multipart/form-data; boundary={b}"

    def request(self, method, url, data=None, files=None, follow=False):
        sp = urlsplit(url)
        headers = [(b"host", b"testserver")]
        body = b""
        if files:
            body, ct = self._multipart(data, files)
            headers.append((b"content-type", ct.encode()))
        elif data is not None:
            body = urlencode(data).encode()
            headers.append((b"content-type", b"application/x-www-form-urlencoded"))
        if self.cookies:
            headers.append((b"cookie", "; ".join(f"{k}={v}" for k, v in self.cookies.items()).encode()))
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
                 "scheme": "http", "path": sp.path, "raw_path": sp.path.encode(), "query_string": sp.query.encode(),
                 "headers": headers, "client": ("127.0.0.1", 5000), "server": ("testserver", 80), "root_path": ""}
        out = {"status": 500, "headers": [], "body": b""}

        async def run():
            sent = False

            async def receive():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                await asyncio.sleep(3600)

            async def send(msg):
                if msg["type"] == "http.response.start":
                    out["status"], out["headers"] = msg["status"], msg["headers"]
                elif msg["type"] == "http.response.body":
                    out["body"] += msg.get("body", b"")

            await self.app(scope, receive, send)

        asyncio.run(run())
        hdrs = {}
        for k, v in out["headers"]:
            k = k.decode().lower()
            if k == "set-cookie":
                c = SimpleCookie()
                c.load(v.decode())
                for name, morsel in c.items():
                    if morsel.value == "" or morsel["max-age"] == "0":
                        self.cookies.pop(name, None)
                    else:
                        self.cookies[name] = morsel.value
                hdrs.setdefault("set-cookie-raw", []).append(v.decode())
            else:
                hdrs[k] = v.decode()
        resp = Response(out["status"], hdrs, out["body"])
        if follow and resp.status_code in (301, 302, 303, 307) and resp.location:
            return self.request("GET", resp.location, follow=True)
        return resp

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, data=None, **kw):
        return self.request("POST", url, data=data if data is not None else {}, **kw)

    # helpers
    def csrf(self, html=None):
        r = self.get("/notifications") if html is None else None
        text = html if html is not None else r.text
        m = re.search(r'name="csrf" value="([^"]+)"', text)
        return m.group(1) if m else None
