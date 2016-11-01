import asyncio
import pytest

from tervis.environment import Environment
from tervis.dependencies import DependencyMount
from tervis.db import Database


def dump_schema(metadata):
    from sqlalchemy import create_engine
    buf = []
    def dump(sql, *multiparams, **params):
        buf.append(str(sql.compile(dialect=engine.dialect)))
    engine = create_engine('postgres://', strategy='mock', executor=dump)

    metadata.create_all(engine)
    create_sql = ''.join(buf)

    del buf[:]
    metadata.drop_all(engine)
    drop_sql = ''.join(buf)

    return create_sql, drop_sql


def ensure_schema(request, metadata, conn):
    create_sql, drop_sql = dump_schema(metadata)

    async def create():
        await conn.execute(create_sql)

    async def drop():
        await conn.execute(drop_sql)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(create())
    request.addfinalizer(lambda: loop.run_until_complete(drop()))


@pytest.fixture(scope='function')
def env_factory():
    def factory():
        return Environment(config={
            'databases': {
                'default': {
                    'database': 'sentry_health_test',
                }
            }
        })
    return factory


@pytest.fixture(scope='function')
def env(request, env_factory):
    env = env_factory()
    env.__enter__()
    request.addfinalizer(lambda: env.__exit__(None, None, None))
    return env


@pytest.fixture(scope='function')
def op(request, env):
    from tervis.operation import Operation
    op = Operation(env)
    op.__enter__()
    request.addfinalizer(lambda: op.__exit__(None, None, None))
    return op


@pytest.fixture(scope='function')
def auth_db(request, op):
    class Container(DependencyMount):
        db = Database(config='apiserver.auth_db')
        def __init__(self):
            DependencyMount.__init__(self, parent=op)

    with Container() as container:
        from tervis.auth import metadata
        ensure_schema(request, metadata, container.db.conn)
        yield container.db


@pytest.fixture(scope='module')
def runasync():
    import asyncio
    def runner(f):
        asyncio.get_event_loop().run_until_complete(f())
        return f
    return runner
