class ConfigError(ValueError):
    pass


class ApiError(Exception):

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message

    def to_json(self):
        return {
            'type': self.__class__.__name__,
            'message': self.message,
        }


class PayloadTooLarge(ApiError):
    pass
