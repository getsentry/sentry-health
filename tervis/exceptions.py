from ._compat import implements_to_string


class ConfigError(ValueError):
    pass


@implements_to_string
class ApiError(Exception):

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


class ClientReadFailed(ApiError):
    pass


class PayloadTooLarge(ApiError):
    pass
