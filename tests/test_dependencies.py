import pytest

from tervis.dependencies import DependencyDescriptor, DependencyMount, \
    UninitializedObject
from tervis.environment import CurrentEnvironment


class MyDependency(DependencyDescriptor):
    scope = 'env'

    def instanciate(self, env):
        return MyStuff(env)


class MyStuff(object):

    def __init__(self, env):
        self.env = env
        self.entered = False
        self.closed = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc_value, tb):
        self.closed = True


class DemoObject(DependencyMount):
    env = CurrentEnvironment()
    stuff = MyDependency()

    def __init__(self, env):
        DependencyMount.__init__(self, parent=env)


def test_basic(env_factory):
    env = env_factory()

    # The demo object is haivng a dependency to "MyStuff" which however is
    # scoped to the environment.  As a result the object is entered as
    # soon as the demo object is entered as well.
    with env:
        obj = DemoObject(env)

        # If the dependency mount is not active we can't resolve
        # dependencies
        with pytest.raises(RuntimeError):
            obj.stuff

        # However once we enter it, the object is entered and not yet
        # closed.
        with obj:
            assert obj.stuff.entered
            assert not obj.stuff.closed

        # Since the object is scoped to the environment it does not closed
        # yet.
        assert not obj.stuff.closed

    # However it's closed now.
    assert obj.stuff.closed

    instances = list(env.__dependency_info__.iter_instances())
    assert len(instances) == 1
    assert instances[0] is obj.stuff
