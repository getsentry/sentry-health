import json
from ipaddress import ip_address, ip_network

from tervis.environment import CurrentEnvironment
from tervis.event import normalize_event
from tervis.auth import Auth
from tervis.api import register_endpoint
from tervis.producer import Producer
from tervis.exceptions import ApiError, PayloadTooLarge, ClientReadFailed, \
    ClientBlacklisted
from tervis.web import Endpoint, ApiResponse, get_remote_addr


def ip_is_blacklisted(env, addr):
    addr = ip_address(addr)
    for net in env.get_config('apiserver.whitelisted_ips'):
        try:
            net = ip_network(net, strict=False)
        except ValueError:
            continue
        if addr in net:
            return False
    for net in env.get_config('apiserver.blacklisted_ips'):
        try:
            net = ip_network(net, strict=False)
        except ValueError:
            continue
        if addr in net:
            return True
    return False


@register_endpoint(
    method='POST',
    path='/events/{project_id}',
)
class SubmitEventEndpoint(Endpoint):
    env = CurrentEnvironment()
    auth = Auth()
    producer = Producer()

    async def accept_event(self):
        max_json_packet = self.env.get_config(
            'apiserver.limits.max_json_packet')
        line = await self.op.req.content.readline()
        if not line:
            return
        try:
            line = line.decode('utf-8')
            if len(line) > max_json_packet:
                raise PayloadTooLarge('JSON event above maximum size')
            return normalize_event(json.loads(line))
        except IOError as e:
            raise ClientReadFailed(str(e))

    async def process_event(self, event):
        self.producer.produce_event(self.auth.project_id, event,
                                    self.auth.timestamp)

    async def handle(self):
        remote_addr = get_remote_addr(self.env, self.op.req)
        if remote_addr is not None \
           and ip_is_blacklisted(self.env, remote_addr):
            raise ClientBlacklisted('The ip address of the client is '
                                    'blacklisted for event submission')

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

        return ApiResponse({
            'errors': errors,
            'events': events,
        })
