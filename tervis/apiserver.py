import json
from json.decoder import JSONDecodeError
from functools import partial
from ipaddress import ip_address

from aiohttp import web

from .auth import AuthManager
from .exceptions import ApiError, PayloadTooLarge, ClientReadFailed
from ._compat import scalar_types, number_types, string_types


def expect_type(data, key, ty, allow_none=False, validate=None,
                convert=None):
    rv = data.get(key)
    if rv is None:
        if not allow_none:
            raise ApiError('Missing parameter "%s"' % key)
        return None
    if not isinstance(rv, ty):
        raise ApiError('Invalid value for "%s"' % key)
    try:
        if validate is not None:
            validate(rv)
        if convert is not None:
            rv = convert(rv)
    except ValueError:
        raise ApiError('Invalid value for "%s"' % key)
    return rv


expect_string = partial(expect_type, ty=string_types)
expect_scalar = partial(expect_type, ty=scalar_types)
expect_number = partial(expect_type, ty=number_types)
expect_object = partial(expect_type, ty=dict)


def normalize_event(event):
    return {
        'ty': expect_string(event, 'ty'),
        'ts': expect_number(event, 'ts', convert=float),
        'ip': expect_type(event, 'ip', ty=string_types, validate=ip_address,
                          allow_none=True),
        'dt': expect_number(event, 'dt', allow_none=True),
        'dev': expect_object(event, 'dev', allow_none=True) or {},
        'oid': expect_scalar(event, 'oid'),
        'sid': expect_scalar(event, 'sid'),
        'env': expect_string(event, 'env', allow_none=True),
        'rel': expect_string(event, 'rel', allow_none=True),
        'user': expect_object(event, 'user', allow_none=True) or {},
        'data': expect_object(event, 'data', allow_none=True) or {},
    }


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

    async def accept_event(self, request):
        line = await request.content.readline()
        if not line:
            return
        try:
            line = line.decode('utf-8')
            if len(line) > self.max_json_packet:
                raise PayloadTooLarge('JSON event above maximum size')
            return normalize_event(json.loads(line))
        except IOError as e:
            raise ClientReadFailed(str(e))

    async def process_event(self, event, auth):
        pass

    async def on_submit_event(self, request):
        auth = await self.auth_manager.auth_from_request(request)
        errors = []
        events = 0
        while 1:
            try:
                event = await self.accept_event(request)
                if event is None:
                    break
                await self.process_event(event, auth)
                events += 1
            except ApiError as e:
                errors.append(e.to_json())

        return web.Response(text=json.dumps({
            'errors': errors,
            'events': events,
        }))

    def run(self, host=None, port=None):
        if host is None:
            host = self.env.get_config('apiserver.host')
        if port is None:
            port = self.env.get_config('apiserver.port')
        web.run_app(self.app, host=host, port=port,
                    print=lambda *a, **kw: None)
