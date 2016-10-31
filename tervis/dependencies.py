import asyncio
import inspect

from contextlib import contextmanager
from threading import RLock
from weakref import ref as weakref


containers = {}


class UninitializedObject(object):

    def __init__(self, descriptor, owner):
        self.__descriptor = descriptor
        self.__owner = weakref(owner)

    def __fail(self):
        owner = self.__owner()
        raise RuntimeError('Cannot use the dependency descriptor %r before '
                           'the associated owner (%r) has been '
                           'entered' % (self.__descriptor.__class__.__name__,
                                        owner.__class__.__name__))

    def __geattr__(self, name):
        self.__fail()

    def __call__(self, *args, **kwargs):
        self.__fail()

    def __repr__(self):
        return '<UninitializedObject %r>' % \
            self.__descriptor.__class__.__name__


class ManagedResourceBox(object):
    __slots__ = ('res', 'obj', 'should_deinit')

    def __init__(self, res, obj):
        self.res = res
        self.obj = obj
        self.should_deinit = isinstance(obj, UninitializedObject)

    async def ensure_initialized(self):
        if not isinstance(self.obj, UninitializedObject):
            return
        if hasattr(self.res, '__aenter__'):
            self.obj = await self.res.__aenter__()
        elif hasttr(self.res, '__enter__'):
            self.obj = self.res.__enter__()
        else:
            raise AssertionError('Found uninitialized object that cannot '
                                 'be initialized.')

    async def deinit(self, *exc_info):
        if self.should_deinit:
            if hasattr(self.res, '__aexit__'):
                await self.res.__aexit__(*exc_info)
            elif hasttr(self.res, '__exit__'):
                self.res.__exit__(*exc_info)


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

    async def close_and_collect(self, exc_type, exc_value, tb):
        if self.closed:
            return
        awaitables = []
        for box in self.iter_instances(raw=True):
            if box.should_deinit:
                awaitables.append(box.deinit(exc_type, exc_value, tb))
            elif hasattr(box.obj, 'close_async'):
                awaitables.append(box.obj.close_async())
            elif hasattr(box.obj, 'close'):
                box.obj.close()
        self.closed = True
        if awaitables:
            await asyncio.wait(awaitables)

    def iter_instances(self, raw=False):
        for key, value in self.instances.items():
            if not raw:
                value = value.obj
            yield value

    def resolve_dependency(self, scope, key, descriptor_type):
        if self.key == key and self.descriptor_type is descriptor_type:
            return self.ref

        full_key = descriptor_type, key
        rv = self.instances.get(full_key)
        if rv is not None:
            return rv.obj

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


class DependencyDescriptor(object):
    """A dependency descriptor is a descriptor that will instanciate an
    object if it does not exist yet.  That object can be anything really
    but there are two special rules about it:

    *   if that object is a `DependencyMount` it will automatically be
        activated when the dependency mount is entered if the object is not
        lazy.  The use of the `with` statement is in that case makes no sense.
        It's exited when the associated scope is exited itself.
    *   if the returned object has a `close()` method it will be invoked
        when the owner is shut down (or `close_async()`).
    """
    scope = 'env'
    key = None
    lazy = False

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        return resolve_or_ensure_dependency(self, obj)

    def instanciate(self, obj):
        raise RuntimeError('Cannot instanciate %r objects' %
                           self.__class__.__name__)


class DependencyMountType(type):

    def __new__(cls, name, bases, d):
        rv = type.__new__(cls, name, bases, d)
        eager_dependencies = set(getattr(rv, '__eager_dependencies__', ()))
        for value in d.values():
            if isinstance(value, DependencyDescriptor) and \
               not value.lazy:
                eager_dependencies.add(value)
        rv.__eager_dependencies__ = eager_dependencies
        return rv


class DependencyMount(object, metaclass=DependencyMountType):

    def __init__(self, parent=None, scope=None, key=None,
                 descriptor_type=None, synchronized=False):
        self.__dependency_info__ = MountInfo(self, parent, scope,
                                             key, descriptor_type,
                                             synchronized)

    async def close_async(self):
        pass

    def __enter__(self):
        coro = self.__aenter__()
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)

    def __exit__(self, exc_type, exc_value, tb):
        coro = self.__aexit__(exc_type, exc_value, tb)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(coro)

    async def __aenter__(self):
        info = self.__dependency_info__
        info.active += 1

        # Instanciate non lazy dependencies.  They will be entered with
        # the enter of the dependency mount.
        for descr in self.__class__.__eager_dependencies__:
            box = resolve_or_ensure_dependency(descr, self, box_init=True)
            if box is not None:
                await box.ensure_initialized()

        return self

    async def __aexit__(self, exc_type, exc_value, tb):
        info = self.__dependency_info__
        info.active -= 1
        if info.active == 0:
            await self.close_async()
            await info.close_and_collect(exc_type, exc_value, tb)


def resolve_or_ensure_dependency(descr, owner, box_init=False):
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
        if box_init:
            return
        return rv

    if info.active == 0:
        raise RuntimeError('Attempted to resolve dependency %r but the '
                           'owner object (%r) is not active. Use a '
                           'with block.' % (descr.__class__.__name__,
                                            owner.__class__.__name__))

    with info.locked():
        # Look it up a second time in our lock if we are indeed a
        # synchronized mount info
        if info.synchronized:
            rv = info.resolve_dependency(descr.scope, descr.key,
                                         descr.__class__)
            if rv is not None:
                if box_init:
                    return
                return rv

        scope_obj = info.find_scope(descr.scope)
        if scope_obj is None:
            raise RuntimeError('Could not find scope "%s" from %r to resolve %r'
                               % (descr.scope, owner.__class__.__name__,
                                  descr.__class__.__name__))

        res = obj = descr.instanciate(scope_obj.ref)

        # Non lazy objects that are context managers are represented by an
        # uninitiliazed stand-in until the container is entered.
        if not descr.lazy and (hasattr(res, '__aenter__') or
                               hasattr(res, '__enter__')):
            obj = UninitializedObject(descr, owner)

        full_key = descr.__class__, descr.key
        box = ManagedResourceBox(res, obj)
        scope_obj.instances[full_key] = box

        if box_init:
            return box
        return obj
