import sys
import pkgutil


def merge(*objs):
    """Recursively merges objects together."""
    def _merge(a, b):
        if a is None:
            a = {}
        elif not isinstance(a, dict):
            return a
        else:
            a = dict(a)
        for key, value in b.items():
            if isinstance(value, dict):
                value = _merge(a.get(key) or {}, value)
            a[key] = value
        return a

    rv = None
    for obj in objs:
        if obj is not None:
            rv = _merge(rv, obj)
    return rv or {}


def iter_segments(items):
    for item in items:
        for x in item.split('.'):
            if x.isdigit():
                x = int(x)
            yield x


def iter_modules(path):
    __import__(path)
    module = sys.modules[path]
    path = getattr(module, '__path__', None)
    if path is None:
        raise ValueError('%r is not a package' % import_path)
    basename = module.__name__ + '.'
    for importer, modname, ispkg in pkgutil.iter_modules(path):
        modname = basename + modname
        yield modname
        if ispkg:
            for item in iter_modules(modname):
                yield item
