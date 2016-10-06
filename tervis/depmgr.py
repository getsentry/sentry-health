import inspect
from ._compat import with_metaclass, itervalues, isawaitable, PY2

if not PY2:
    import asyncio


containers = {}


class DependencyContainerType(type):

    def __new__(cls, name, bases, d):
        dependency_scope = d.get('dependency_scope')
        rv = type.__new__(cls, name, bases, d)
        if dependency_scope is not None:
            if dependency_scope in containers:
                raise TypeError('Duplicated scope dependency_key %r' %
                                dependency_scope)
            containers[dependency_scope] = rv
        return rv

    def __call__(cls, *args, **kwargs):
        rv = type.__call__(cls, *args, **kwargs)
        rv.__dependency_instances__ = {}
        return rv


def close_and_collect(dependency_container):
    waitables = []
    for instance in itervalues(dependency_container.__dependency_instances__):
        if hasattr(instance, 'close'):
            rv = instance.close()
            if isawaitable(rv):
                waitables.append(rv)
    return waitables


class DependencyContainer(with_metaclass(DependencyContainerType)):
    dependency_scope = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        wait_for = close_and_collect(self)
        if wait_for:
            raise RuntimeError('Attempted sync context management but '
                               'contained objects returned awaitable '
                               'results on close (%r)' % wait_for)

    # If we are on Py 3 we support async close methods.
    if not PY2:
        exec('''if 1:
            def __aenter__(self):
                return self

            def __aexit__(self, exc_type, exc_value, tb):
                wait_for = close_and_collect(self)
                async def _wait_and_discard():
                    await asyncio.wait(wait_for)
                return _wait_and_discard()
        ''')


class DependencyDescriptor(object):
    dependency_scope = 'env'
    dependency_key = None

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        return resolve_or_ensure_dependency(self, obj)

    def instanciate_dependency(self, obj):
        raise RuntimeError('Not implemented')


def resolve_or_ensure_dependency(dep, owner):
    expected_class = containers.get(dep.dependency_scope)
    if expected_class is None:
        raise RuntimeError('Unknown dependency_scope \'%s\'' %
                           dep.dependency_scope)

    if not isinstance(owner, expected_class):
        rv = getattr(owner, dep.dependency_scope, None)
        if rv is not None and isinstance(rv, expected_class):
            owner = rv
        else:
            resolver = getattr(owner, '__resolve_dependency_scope__', None)
            if resolver is not None:
                owner = resolver(dependency_scope)
            else:
                raise RuntimeError('Cannot resolve \'%s\' from %r' %
                                   (dep.dependency_scope, owner))

    dependency_key = dep.__class__, dep.dependency_key

    instance = owner.__dependency_instances__.get(dependency_key)
    if instance is None:
        instance = dep.instanciate_dependency(owner)
        owner.__dependency_instances__[dependency_key] = instance
    return instance
