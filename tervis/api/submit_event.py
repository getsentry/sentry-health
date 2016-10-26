import json

from aiohttp import web

from tervis.apiserver import Endpoint
from tervis.event import normalize_event
from tervis.auth import Auth
from tervis.api import register_endpoint


@register_endpoint(
    method='POST',
    path='/events/{project}',
)
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
