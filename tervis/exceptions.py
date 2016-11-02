class ConfigError(ValueError):
    pass


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
        return web.ApiResponse(self.to_json(), status_code=self.status_code)


class BadAuth(ApiError):
    status_code = 403


class ClientBlacklisted(ApiError):
    status_code = 403


class ClientReadFailed(ApiError):
    pass


class PayloadTooLarge(ApiError):
    status_code = 413


from tervis import web
