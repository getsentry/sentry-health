from tervis.dependencies import DependencyMount, DependencyDescriptor
from tervis.environment import CurrentEnvironment


class Database(DependencyDescriptor):
    """A database dependency descriptor gives access to a specific database
    backend instanciated for the current operation.
    """
    scope = 'operation'

    def __init__(self, config):
        self.config = config

    @property
    def key(self):
        return (self.config,)

    def instanciate(self, op):
        name = op.env.get_config(self.config)
        if name is None:
            raise RuntimeError('Unknown config "%s"' % self.config)
        backend = op.env.get_config('databases', name, 'backend')
        if not backend:
            raise RuntimeError('No configuration for db "%s"' % name)
        return backends[backend](op, name)


class DatabaseBackend(DependencyMount):
    env = CurrentEnvironment()

    def __init__(self, operation, name):
        DependencyMount.__init__(self, parent=operation)
        self.name = name


from tervis.db.backends import backends
