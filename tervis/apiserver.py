import json
from json.decoder import JSONDecodeError

from aiohttp import web

from .auth import AuthManager
from .exceptions import PayloadTooLarge


class Server(object):

    def __init__(self, env):
        self.env = env
        self.auth_manager = AuthManager(env)
        self.app = web.Application()
        self.app.router.add_route(
            method='POST',
            path='/events',
            handler=self.on_submit_event,
            name='submit_event'
        )

        self.max_json_packet = env.get_config('apiserver.limits.max_json_packet')

    def normalize_event(self, event):
        return {
            'id': event.get('id'),
            'ty': event.get('ty'),
            'ts': event.get('ts'),
        }

    async def accept_events(self, request):
        events = []
        errors = []
        while 1:
            line = await request.content.readline()
            if not line:
                break
            try:
                line = line.decode('utf-8')
                if len(line) > self.max_json_packet:
                    raise PayloadTooLarge('JSON event above maximum size')
                events.append(self.normalize_event(json.loads(line)))
            except (IOError, JSONDecodeError) as e:
                errors.append(e)
        return events, errors

    async def on_submit_event(self, request):
        auth = await self.auth_manager.auth_from_request(request)
        events = await self.accept_events(request)
        return web.Response(text='%r: %r!\n' % (auth, events))

    def run(self, host=None, port=None):
        if host is None:
            host = self.env.get_config('apiserver.host')
        if port is None:
            port = self.env.get_config('apiserver.port')
        web.run_app(self.app, host=host, port=port,
                    print=lambda *a, **kw: None)
