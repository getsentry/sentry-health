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
