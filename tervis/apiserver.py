import asyncio
import socket
import logging
from aiohttp import web

from tervis.producer import Producer
from tervis.environment import CurrentEnvironment
from tervis.dependencies import DependencyMount


logger = logging.getLogger(__name__)


class Server(DependencyMount):
    env = CurrentEnvironment()
    producer = Producer()

    def __init__(self, env):
        DependencyMount.__init__(self, parent=env)
        self.app = web.Application()

        from tervis.api import endpoint_registry
        for name, opts in endpoint_registry.items():
            opts = dict(opts)
            opts['handler'] = opts.pop('endpoint').as_handler(env)
            self.app.router.add_route(**opts)

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
            handler = self.app.make_handler(access_log=logger)
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
                loop.run_until_complete(app.shutdown())
                loop.run_until_complete(
                    handler.finish_connections(shutdown_timeout))
                loop.run_until_complete(app.cleanup())
