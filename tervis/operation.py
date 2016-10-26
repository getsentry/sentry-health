from .dependencies import DependencyMount, DependencyDescriptor
from .environment import CurrentEnvironment


class CurrentOperation(DependencyDescriptor):
    pass


class Operation(DependencyMount):
    env = CurrentEnvironment()

    def __init__(self, env, req=None, project=None):
        DependencyMount.__init__(self,
            parent=env,
            scope='operation',
            descriptor_type=CurrentOperation
        )
        self.req = req
        self.project = project
