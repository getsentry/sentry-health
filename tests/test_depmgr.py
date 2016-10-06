from tervis.depmgr import DependencyDescriptor


class MyDependency(DependencyDescriptor):
    dependency_scope = 'env'

    def instanciate_dependency(self, env):
        return MyStuff(env)


class MyStuff(object):

    def __init__(self, env):
        self.env = env
        self.closed = False

    async def close(self):
        self.closed = True


class DemoObject(object):
    stuff = MyDependency()

    def __init__(self, env):
        self.env = env


def test_depmgr(env):
    with env:
        obj = DemoObject(env)
        assert not obj.stuff.closed
    assert len(env.__dependency_instances__) == 1
    assert next(iter(env.__dependency_instances__.values())) is obj.stuff
    assert obj.stuff.closed
