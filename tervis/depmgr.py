import inspect
from weakref import ref as weakref
from ._compat import iteritems, isawaitable, PY2

if not PY2:
    import asyncio


containers = {}


if PY2:
    def close_and_collect(dependency_mount):
        info = dependency_mount.__dependency_info__
        for inst in info.iter_instances():
            if hasattr(inst, 'close'):
                inst.close()

else:
    exec('''if 1:
        def close_and_collect(dependency_mount):
            info = dependency_mount.__dependency_info__
            waitables = []
            for inst in info.iter_instances():
                if hasattr(inst, 'close'):
                    rv = inst.close()
                    if isawaitable(rv):
                        waitables.append(rv)
            if waitables:
                async def _wait_and_discard():
                    await asyncio.wait(waitables)
                return _wait_and_discard()
    ''')


class MountInfo(object):
    __slots__ = ('_ref', 'parent', 'scope', 'instances', 'key',
                 'descriptor_type')

    def __init__(self, ref, parent, scope, key=None, descriptor_type=None):
        self._ref = weakref(ref)
        if parent is not None:
            parent = parent.__dependency_info__
        self.parent = parent
        self.scope = scope
        self.instances = {}
        self.key = key
        self.descriptor_type = descriptor_type

    @property
    def ref(self):
        rv = self._ref()
        if rv is None:
            raise RuntimeError('Self reference was garbage collected')
        return rv

    def iter_instances(self):
        self_cls = self.ref.__class__
        for key, value in iteritems(self.instances):
            if isinstance(value, weakref):
                value = value()
            if value is not None:
                yield value

    def resolve_dependency(self, scope, key, descriptor_type):
        if self.key == key and self.descriptor_type is descriptor_type:
            return self.ref

        full_key = descriptor_type, key
        rv = self.instances.get(full_key)
        if rv is not None:
            if isinstance(rv, weakref):
                rv = rv()
            if rv is not None:
                return rv

        # Do not move past the given scope.
        if scope == self.scope:
            return

        if self.parent is not None:
            return self.parent.resolve_dependency(scope, key, descriptor_type)

    def find_scope(self, scope):
        if self.scope == scope:
            return self
        if self.parent is not None:
            return self.parent.find_scope(scope)


class DependencyMount(object):

    def __init__(self, parent=None, scope=None, key=None,
                 descriptor_type=None):
        self.__dependency_info__ = MountInfo(self, parent, scope,
                                             key, descriptor_type)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        wait_for = close_and_collect(self)
        if wait_for is not None:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(wait_for)

    # If we are on Py 3 we support async close methods.
    if not PY2:
        exec('''if 1:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_value, tb):
                wait_for = close_and_collect(self)
                if wait_for is not None:
                    await wait_for
        ''')


class DependencyDescriptor(object):
    scope = 'env'
    key = None

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        return resolve_or_ensure_dependency(self, obj)

    def instanciate(self, obj):
        raise RuntimeError('Cannot instanciate %r objects' %
                           self.__class__.__name__)


def resolve_or_ensure_dependency(descr, owner):
    if not isinstance(owner, DependencyMount):
        raise RuntimeError('Dependencies can only be mounted on a '
                           'dependency mount')
    info = owner.__dependency_info__
    rv = info.resolve_dependency(descr.scope, descr.key, descr.__class__)
    if rv is not None:
        return rv

    scope_obj = info.find_scope(descr.scope)
    if scope_obj is None:
        raise RuntimeError('Could not find scope "%s"' % (descr.scope,))

    rv = descr.instanciate(scope_obj.ref)
    full_key = descr.__class__, descr.key
    scope_obj.instances[full_key] = rv
    return rv
