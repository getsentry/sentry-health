from tervis.depmgr import DependencyDescriptor, DependencyMount
from tervis.environment import CurrentEnvironment


class MyDependency(DependencyDescriptor):
    scope = 'env'

    def instanciate(self, env):
        return MyStuff(env)


class MyStuff(object):

    def __init__(self, env):
        self.env = env
        self.closed = False

    async def close(self):
        self.closed = True


class DemoObject(DependencyMount):
    env = CurrentEnvironment()
    stuff = MyDependency()

    def __init__(self, env):
        DependencyMount.__init__(self, parent=env)


def test_depmgr(env):
    with env:
        obj = DemoObject(env)
        assert not obj.stuff.closed
    instances = list(env.__dependency_info__.iter_instances())
    assert len(instances) == 1
    assert instances[0] is obj.stuff
    assert obj.stuff.closed
