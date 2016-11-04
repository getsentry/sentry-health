import sys
import pkgutil


_missing = object()


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
        raise ValueError('%r is not a package' % path)
    basename = module.__name__ + '.'
    for importer, modname, ispkg in pkgutil.iter_modules(path):
        modname = basename + modname
        yield modname
        if ispkg:
            for item in iter_modules(modname):
                yield item
