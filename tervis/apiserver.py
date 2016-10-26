import json
from json.decoder import JSONDecodeError

from aiohttp import web

from .auth import Auth
from .event import normalize_event
from .producer import Producer
from .exceptions import ApiError, PayloadTooLarge, ClientReadFailed
from .operation import CurrentOperation, Operation
from .dependencies import DependencyDescriptor, DependencyMount


class CurrentEndpoint(DependencyDescriptor):
    pass


class Endpoint(DependencyMount):
    op = CurrentOperation()

    def __init__(self, op):
        DependencyMount.__init__(self,
            parent=op,
            descriptor_type=CurrentEndpoint
        )

    @classmethod
    async def full_dispatch(cls, env, req):
        project = req.match_info.get('project')
        async with Operation(env, req, project) as op:
            async with cls(op) as self:
                return await self.handle()

    async def handle(self):
        raise NotImplementedError('This endpoint cannot handle')


class SubmitEventEndpoint(Endpoint):
    auth = Auth()

    async def accept_event(self):
        line = await self.op.req.content.readline()
        if not line:
            return
        try:
            line = line.decode('utf-8')
            if len(line) > self.max_json_packet:
                raise PayloadTooLarge('JSON event above maximum size')
            return normalize_event(json.loads(line))
        except IOError as e:
            raise ClientReadFailed(str(e))

    async def process_event(self, event):
        with self.producer.partial_guard():
            self.producer.produce_event(self.auth.project, event,
                                        self.auth.timestamp)

    async def handle(self):
        errors = []
        events = 0
        while 1:
            try:
                event = await self.accept_event()
                if event is None:
                    break
                await self.process_event(event)
                events += 1
            except ApiError as e:
                errors.append(e.to_json())

        return web.Response(text=json.dumps({
            'errors': errors,
            'events': events,
        }))


class Server(object):

    def __init__(self, env):
        self.env = env
        self.auth_manager = AuthManager(env)
        self.producer = Producer(env)
        self.app = web.Application()

        self.app.router.add_route(
            method='POST',
            path='/events/{project}',
            handler=SubmitEventEndpoint.full_dispatch,
            name='submit_event'
        )

        self.max_json_packet = env.get_config('apiserver.limits.max_json_packet')

    def run(self, host=None, port=None):
        if host is None:
            host = self.env.get_config('apiserver.host')
        if port is None:
            port = self.env.get_config('apiserver.port')
        with self.producer:
            web.run_app(self.app, host=host, port=port,
                        print=lambda *a, **kw: None)
