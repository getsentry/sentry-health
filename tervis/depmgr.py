from ._compat import with_metaclass


scopes = {}


class DependencyContainerType(type):

    def __new__(cls, name, bases, d):
        scope = d.get('__dependency_scope__')
        rv = type.__new__(cls, name, bases, d)
        if scope is not None:
            scopes[scope] = rv
        return rv

    def __call__(cls, *args, **kwargs):
        rv = type.__call__(cls, *args, **kwargs)
        rv.__dependency_instances__ = {}
        return rv


class DependencyContainer(with_metaclass(DependencyContainerType)):
    scope = None


class Dependency(object):
    scope = 'env'

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        return resolve_or_ensure_dependency(self, obj)

    def __resolve_dependency__(self, obj):
        raise RuntimeError('Not implemented')


def resolve_or_ensure_dependency(dep, owner):
    expected_class = scopes.get(dep.scope)
    if expected_class is None:
        raise RuntimeError('Unknown scope \'%s\'' % dep.scope)

    if not isinstance(owner, expected_class):
        rv = getattr(owner, dep.scope, None)
        if rv is not None and isinstance(rv, expected_class):
            owner = rv
        else:
            resolver = getattr(owner, '__resolve_dependency_scope__', None)
            if resolver is not None:
                owner = resolver(scope)
            else:
                raise RuntimeError('Cannot resolve \'%s\' from %r' %
                                   (dep.scope, owner))

    instance = owner.__dependency_instances__.get(dep)
    if instance is None:
        instance = dep.__resolve_dependency__(owner)
        owner.__dependency_instances__[dep] = instance
    return instance
