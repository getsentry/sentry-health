import asyncio
import inspect

from contextlib import contextmanager
from threading import RLock
from weakref import ref as weakref


containers = {}


class MountInfo(object):

    def __init__(self, ref, parent, scope, key=None, descriptor_type=None,
                 synchronized=False):
        self._ref = weakref(ref)
        if parent is not None:
            parent = parent.__dependency_info__
        self.parent = parent
        self.scope = scope
        self.instances = {}
        self.key = key
        self.descriptor_type = descriptor_type
        self.active = 0
        self.closed = False
        self.synchronized = synchronized
        if synchronized:
            self._lock = RLock()

    @property
    def ref(self):
        rv = self._ref()
        if rv is None:
            raise RuntimeError('Self reference was garbage collected')
        return rv

    @contextmanager
    def locked(self):
        if self.synchronized:
            with self._lock:
                yield
        else:
            yield

    async def close_and_collect(self):
        if self.closed:
            return
        awaitables = []
        for inst in self.iter_instances():
            if hasattr(inst, 'close_async'):
                awaitables.append(inst.close_async())
            elif hasattr(inst, 'close'):
                inst.close()
        self.closed = True
        if awaitables:
            await asyncio.wait(awaitables)

    def iter_instances(self):
        self_cls = self.ref.__class__
        for key, value in self.instances.items():
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
                 descriptor_type=None, synchronized=False):
        self.__dependency_info__ = MountInfo(self, parent, scope,
                                             key, descriptor_type,
                                             synchronized)

    async def close_async(self):
        await self.__dependency_info__.close_and_collect()

    def __enter__(self):
        self.__dependency_info__.active += 1
        return self

    def __exit__(self, exc_type, exc_value, tb):
        coro = self.__aexit__(exc_type, exc_value, tb)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(coro)

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_value, tb):
        self.__dependency_info__.active -= 1
        if self.__dependency_info__.active == 0:
            await self.close_async()


class DependencyDescriptor(object):
    """A dependency descriptor is a descriptor that will instanciate an
    object if it does not exist yet.  That object can be anything really
    but there are two special rules about it:

    *   if that object is a `DependencyMount` it will automatically be
        activated.  The use of the `with` statement is in that case not
        necessary.
    *   if the returned object has a `close()` method it will be invoked
        when the owner is shut down.
    """
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
    """Given a descriptor and an owner object this attempts to resolve an
    already existing instance that matches the descriptor and return it,
    or alternatively create a new instance and persist it with the matching
    scope if such a scope exists.
    """
    if isinstance(owner, DependencyDescriptor):
        raise RuntimeError('Dependencies cannot be mounted on dependency '
                           'descriptors.')
    elif not isinstance(owner, DependencyMount):
        raise RuntimeError('Dependencies can only be mounted on a '
                           'dependency mount')

    info = owner.__dependency_info__
    rv = info.resolve_dependency(descr.scope, descr.key, descr.__class__)
    if rv is not None:
        return rv

    if info.active == 0:
        raise RuntimeError('Attempted to resolve dependency but the '
                           'owner object (%r) is not active. Use a '
                           'with block.' % owner.__class__.__name__)

    with info.locked():
        # Look it up a second time in our lock if we are indeed a
        # synchronized mount info
        if info.synchronized:
            rv = info.resolve_dependency(descr.scope, descr.key,
                                         descr.__class__)
            if rv is not None:
                return rv

        scope_obj = info.find_scope(descr.scope)
        if scope_obj is None:
            raise RuntimeError('Could not find scope "%s"' % (descr.scope,))

        rv = descr.instanciate(scope_obj.ref)

        # If we are producing a dependency mount we can safely active it.  The
        # system will automatically invoke close() on teardown
        if isinstance(rv, DependencyMount):
            rv.__dependency_info__.active += 1

        full_key = descr.__class__, descr.key
        scope_obj.instances[full_key] = rv
        return rv
