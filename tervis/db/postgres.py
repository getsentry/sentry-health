from aiopg.sa import create_engine

from tervis.dependencies import DependencyMount, DependencyDescriptor
from tervis.db.base import DatabaseBackend


class Engine(DependencyDescriptor):
    """Implements a dependency to the engine.  The engine is scoped to the
    environment which makes it and the contained pool persist between
    operations.
    """
    scope = 'env'

    def __init__(self, name='default'):
        self.name = name

    @property
    def key(self):
        return (self.name,)

    def instanciate(self, env):
        cfg = env.get_config('databases', self.name)
        return create_engine(
            host=cfg['host'],
            user=cfg['user'],
            password=cfg.get('password'),
            database=cfg['database'],
        )


class PostgresBackend(DatabaseBackend):
    engine = Engine()

    async def __aenter__(self):
        await super().__aenter__()
        self._conn_mgr = self.engine.acquire()
        self.conn = await self._conn_mgr.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_value, tb):
        await self._conn_mgr.__aexit__(exc_type, exc_value, tb)
        await super().__aexit__(exc_type, exc_value, tb)
