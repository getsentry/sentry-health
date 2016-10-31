import json

from ._compat import implements_to_string


class ConfigError(ValueError):
    pass


@implements_to_string
class ApiError(Exception):
    status_code = 400

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message

    def __str__(self):
        return self.message

    def to_json(self):
        return {
            'type': self.__class__.__name__,
            'message': self.message,
        }

    def get_response(self):
        # Use local import since this code might be included in older
        # versions of Python that do not support async
        from aiohttp import web
        return web.Response(text=json.dumps(self.to_json()),
                            status=self.status_code,
                            content_type='application/json')


class BadAuth(ApiError):
    pass


class ClientReadFailed(ApiError):
    pass


class PayloadTooLarge(ApiError):
    pass
