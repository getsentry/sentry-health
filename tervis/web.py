import json
import socket
from ipaddress import ip_address
from aiohttp import web

from tervis.dependencies import DependencyDescriptor, DependencyMount
from tervis.operation import CurrentOperation, Operation
from tervis.exceptions import ApiError


def is_valid_proxy(env, ip):
    for proxy_ip in env.get_config('apiserver.proxies'):
        proxy_ip = ip_address(proxy_ip)
        if ip_address(ip) == proxy_ip:
            return True
    return False


def get_remote_addr(env, req):
    try:
        ip_trail = [x.strip().split(':')[0] for x in
                    req.headers['X-FORWARDED-FOR'].split(',')]
    except LookupError:
        ip_trail = []

    if len(ip_trail) >= 2:
        if all(is_valid_proxy(env, ip) for ip in ip_trail[1:]):
            return ip_trail[0]

    family = req.transport.get_extra_info('socket').family
    if family in (socket.AF_INET, socket.AF_INET6):
        return req.transport.get_extra_info('peername')[0]


class ApiResponse(object):

    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code

    def to_json(self):
        return self.data

    def to_http_response(self):
        return web.Response(text=json.dumps(self.to_json()),
                            status=self.status_code,
                            content_type='application/json')


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
    def as_handler(cls, env):
        async def handler(req):
            try:
                project_id = req.match_info.get('project_id')
                if project_id is not None:
                    try:
                        project_id = int(project_id)
                    except ValueError:
                        raise ApiError('Invalid project ID')
                async with Operation(env, req, project_id) as op:
                    async with cls(op) as self:
                        return (await self.handle()).to_http_response()
            except exceptions.ApiError as e:
                return e.get_response().to_http_response()
        return handler

    async def handle(self):
        raise NotImplementedError('This endpoint cannot handle')


from tervis import exceptions
