from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

import time
import gzip
import io


class ProcessTimeHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers['X-Process-Time'] = str(process_time)
        return response


class GZipMiddleware:
    def __init__(self, app: ASGIApp, minimum_size: int = 500) -> None:
        self.app = app
        self.minimum_size = minimum_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = Headers(scope=scope)
            if "gzip" in headers.get("Accept-Encoding", ""):
                responder = GZipResponder(self.app, self.minimum_size)
                await responder(scope, receive, send)
                return
        await self.app(scope, receive, send)


class GZipResponder:
    def __init__(self, app: ASGIApp, minimum_size: int) -> None:
        self.app = app
        self.minimum_size = minimum_size
        self.send = unattached_send  # type: Send
        self.initial_message = {}  # type: Message
        self.started = False
        self.gzip_buffer = io.BytesIO()
        self.gzip_file = gzip.GzipFile(mode="wb", fileobj=self.gzip_buffer)
        self.status_code = 200

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        self.send = send
        await self.app(scope, receive, self.send_with_gzip)

    async def send_with_gzip(self, message: Message) -> None:
        message_type = message["type"]
        if message_type == "http.response.start":
            self.status_code = message['status']
            # Don't send the initial message until we've determined how to
            # modify the outgoing headers correctly.
            self.initial_message = message
        elif message_type == "http.response.body" and not self.started:
            self.started = True
            body = message.get("body", b"")
            more_body = message.get("more_body", False)
            if len(body) < self.minimum_size and not more_body:
                # Don't apply GZip to small outgoing responses.
                await self.send(self.initial_message)
                await self.send(message)
            elif not more_body:
                if self.status_code == 204:
                    await self.send(self.initial_message)
                    await self.send(message)
                else:
                    # Standard GZip response.
                    self.gzip_file.write(body)
                    self.gzip_file.close()
                    body = self.gzip_buffer.getvalue()

                    headers = MutableHeaders(raw=self.initial_message["headers"])
                    headers["Content-Encoding"] = "gzip"
                    headers["Content-Length"] = str(len(body))
                    headers.add_vary_header("Accept-Encoding")
                    message["body"] = body

                    await self.send(self.initial_message)
                    await self.send(message)
            else:
                if self.status_code == 204:
                    await self.send(self.initial_message)
                    await self.send(message)
                else:
                    # Initial body in streaming GZip response.
                    headers = MutableHeaders(raw=self.initial_message["headers"])
                    headers["Content-Encoding"] = "gzip"
                    headers.add_vary_header("Accept-Encoding")
                    del headers["Content-Length"]

                    self.gzip_file.write(body)
                    message["body"] = self.gzip_buffer.getvalue()
                    self.gzip_buffer.seek(0)
                    self.gzip_buffer.truncate()

                    await self.send(self.initial_message)
                    await self.send(message)

        elif message_type == "http.response.body":
            if self.status_code == 204:
                await self.send(message)
            else:
                # Remaining body in streaming GZip response.
                body = message.get("body", b"")
                more_body = message.get("more_body", False)

                self.gzip_file.write(body)
                if not more_body:
                    self.gzip_file.close()

                message["body"] = self.gzip_buffer.getvalue()
                self.gzip_buffer.seek(0)
                self.gzip_buffer.truncate()

                await self.send(message)


async def unattached_send(message: Message) -> None:
    raise RuntimeError("send awaitable not set")  # pragma: no cover
