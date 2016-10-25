from .depmgr import DependencyMount, DependencyDescriptor


class CurrentOperation(DependencyDescriptor):
    pass


class Operation(DependencyMount):
    dependency_scope = 'operation'

    def __init__(self, env, req=None):
        DependencyMount.__init__(self,
            parent=env,
            scope='operation',
            descriptor_type=CurrentOperation
        )
        self.parent_container = env
        self.env = env
        self.req = req
