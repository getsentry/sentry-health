from aiohttp import web

from tervis.producer import Producer
from tervis.environment import CurrentEnvironment
from tervis.dependencies import DependencyMount


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

        self.max_json_packet = env.get_config(
            'apiserver.limits.max_json_packet')

    def run(self, host=None, port=None):
        if host is None:
            host = self.env.get_config('apiserver.host')
        if port is None:
            port = self.env.get_config('apiserver.port')
        with self.producer:
            # We need to make sure that the run_app method does not
            # terminate the event loop when it closes down.  This would be
            # an issue for our cleanup logic.
            self.app.loop.close = lambda: None
            try:
                web.run_app(self.app, host=host, port=port,
                            print=lambda *a, **kw: None)
            finally:
                del self.app.loop.close
