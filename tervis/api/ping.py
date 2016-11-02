from tervis.web import Endpoint, ApiResponse
from tervis.api import register_endpoint


@register_endpoint(
    method='Get',
    path='/ping',
)
class PingEndpoint(Endpoint):

    async def handle(self):
        return ApiResponse({'ok': True})
