import asyncio
import socket
import logging
from aiohttp import web

from tervis.producer import Producer
from tervis.environment import CurrentEnvironment
from tervis.dependencies import DependencyMount
from tervis.web import get_endpoints, ApiResponse, is_allowed_origin


logger = logging.getLogger(__name__)


class Server(DependencyMount):
    env = CurrentEnvironment()
    producer = Producer()

    def __init__(self, env):
        DependencyMount.__init__(self, parent=env)
        self.app = web.Application()
        self.shutdown_timeout = env.get_config('apiserver.shutdown_timeout')

        for endpoint_cls in get_endpoints():
            endpoint_cls.register_with_server(self)

    async def add_cors_headers(self, req, resp, endpoint=None):
        origin = req.headers.get('ORIGIN')
        if not origin:
            return resp

        allowed_origins = set(self.env.get_config('apiserver.allowed_origins'))
        if endpoint is not None:
            if not endpoint.allow_cors:
                return resp
            allowed_origins.update(await endpoint.get_allowed_origins())

        if not is_allowed_origin(origin, allowed_origins):
            return exceptions.Forbidden('Origin is not allowed') \
                .get_response().to_http_response()

        if endpoint is not None:
            methods = endpoint.get_methods()
        else:
            methods = ['OPTIONS']
            if req.method not in methods:
                methods.append(req.method)
            if 'GET' in methods and 'HEAD' not in methods:
                methods.append('HEAD')

        resp.headers['Access-Control-Allow-Origin'] = origin
        resp.headers['Access-Control-Allow-Methods'] = \
            ', '.join(sorted(methods))

        return resp

    async def postprocess_response(self, req, resp, endpoint=None):
        if 'origin' not in resp.headers:
            resp = await self.add_cors_headers(req, resp, endpoint)
        return resp

    async def make_response(self, req, rv, endpoint=None):
        if isinstance(rv, dict):
            rv = ApiResponse(rv)
        elif isinstance(rv, tuple):
            rv = ApiResponse(*rv)
        if isinstance(rv, ApiResponse):
            rv = rv.to_http_response()
        return await self.postprocess_response(req, rv, endpoint)

    def run(self, host=None, port=None, fd=None, sock=None, backlog=128):
        loop = asyncio.get_event_loop()

        if sock is not None or fd is not None:
            if sock is not None:
                fd = None
            else:
                sock = socket.fromfd(fd, socket.AF_INET, socket.SOCK_STREAM)
            host = None
            port = None
        else:
            sock = None
            if host is None:
                host = self.env.get_config('apiserver.host')
            if port is None:
                port = self.env.get_config('apiserver.port')

        with self.producer:
            handler = self.app.make_handler(
                access_log=logger,
                slow_request_timeout=self.env.get_config(
                    'apiserver.slow_request_timeout'),
                keepalive_timeout=self.env.get_config(
                    'apiserver.keepalive_timeout'),
                tcp_keepalive=self.env.get_config(
                    'apiserver.tcp_keepalive')
            )
            server = loop.create_server(handler, host=host, port=port,
                                        backlog=backlog, sock=sock)
            srv, startup_res = loop.run_until_complete(
                asyncio.gather(server, self.app.startup(), loop=loop))
            try:
                loop.run_forever()
            except KeyboardInterrupt:
                pass
            finally:
                srv.close()
                loop.run_until_complete(srv.wait_closed())
                loop.run_until_complete(self.app.shutdown())
                loop.run_until_complete(
                    handler.finish_connections(self.shutdown_timeout))
                loop.run_until_complete(self.app.cleanup())


from tervis import exceptions
