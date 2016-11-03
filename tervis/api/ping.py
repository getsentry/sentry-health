from tervis.web import Endpoint, ApiResponse


class PingEndpoint(Endpoint):
    url_path = '/ping'

    async def get(self):
        return ApiResponse({'ok': True})
