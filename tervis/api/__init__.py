endpoint_registry = {}


def register_endpoint(method, path, name=None):
    def decorator(cls):
        if name is None:
            real_name = cls.__name__
        else:
            real_name = name
        endpoint_registry[real_name] = {
            'method': method,
            'path': path,
            'endpoint': cls,
        }
        return cls
    return decorator


class ApiResponse(object):

    def __init__(self, data, status_code=200):
        self.data = data
        self.status_code = status_code

    def to_json(self):
        return self.data

    def get_response(self):
        import json
        from aiohttp import web
        return web.Response(text=json.dumps(self.to_json()),
                            status=self.status_code,
                            content_type='application/json')
