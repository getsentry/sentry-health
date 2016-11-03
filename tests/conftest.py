import os
import sys
import yaml
import signal
import socket
import aiohttp
import tempfile
import asyncio
import pytest
from urllib.parse import urljoin

from tervis.environment import Environment
from tervis.dependencies import DependencyMount
from tervis.projectoptions import ProjectOptions
from tervis.db import Database
from tervis.auth import dsns, DSN_ACTIVE


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
def databases(request, op):
    from tervis.auth import metadata as auth_metadata
    from tervis.projectoptions import metadata as projectoptions_metadata

    all_databases = {
        'apiserver.auth_db': [auth_metadata],
        'apiserver.project_db': [projectoptions_metadata],
    }

    rv = {}
    for config, metadatas in all_databases.items():
        class Container(DependencyMount):
            db = Database(config=config)
            def __init__(self):
                DependencyMount.__init__(self, parent=op)

        container = Container()
        container.__enter__()
        for metadata in metadatas:
            ensure_schema(request, metadata, container.db.conn)
        request.addfinalizer(lambda: container.__exit__(None, None, None))
        rv[config] = container.db

    return rv


@pytest.fixture(scope='module')
def env_factory():
    def factory():
        return Environment(config={
            'apiserver': {
                'proxies': ['127.0.0.1'],
                'allowed_origins': ['https://example.com'],
            },
            'databases': {
                'default': {
                    'database': 'sentry_health_test',
                }
            }
        })
    return factory


@pytest.fixture(scope='module')
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
def auth_db(databases):
    return databases['apiserver.auth_db']


@pytest.fixture(scope='function')
def project_db(databases):
    return databases['apiserver.project_db']


@pytest.fixture(scope='module')
def runasync():
    import asyncio
    def runner(f):
        return asyncio.get_event_loop().run_until_complete(f())
    return runner


@pytest.fixture(scope='module')
def server(env, request):
    server_pid = None

    loop = asyncio.get_event_loop()

    session_mgr = aiohttp.ClientSession()
    session = loop.run_until_complete(session_mgr.__aenter__())

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', 0))
    sock.set_inheritable(True)
    sock.listen(128)
    print(sock.fileno())
    port = sock.getsockname()[1]

    @request.addfinalizer
    def cleanup():
        if server_pid is not None:
            os.kill(server_pid, signal.SIGKILL)
        loop.run_until_complete(session_mgr.__aexit__(None, None, None))
        sock.close()

    # Spawn the server in a child.  Reasons.
    server_pid = os.fork()
    if server_pid == 0:
        # Shit fucks up on fork
        loop.close()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        from tervis.apiserver import Server
        with Server(env) as server:
            server.run(sock=sock)
        os._exit(0)

    class ServerInfo(object):

        def __init__(self):
            self.port = port
            self.session = session

        def request(self, method, path, **kwargs):
            return self.session.request(
                method, urljoin('http://127.0.0.1:%s/' % self.port, path),
                **kwargs)

    return ServerInfo()


@pytest.fixture(scope='function')
def projectoptions(request, op, project_db, runasync):
    class Helper(DependencyMount):
        options = ProjectOptions()
        def __init__(self):
            DependencyMount.__init__(self, parent=op)

    helper = Helper()
    helper.__enter__()

    class Options(object):
        def update(self, options, project_id):
            @runasync
            async def run():
                for key, value in options.items():
                    await helper.options.set_unsafe(key, value, project_id)

    request.addfinalizer(lambda: helper.__exit__(None, None, None))

    return Options()


@pytest.fixture(scope='function')
def dsn(runasync, auth_db):
    @runasync
    async def dsn():
        await auth_db.conn.execute(dsns.insert(values={
            'project_id': 42,
            'public_key': 'a' * 20,
            'status': DSN_ACTIVE,
            'roles': 1,
        }))
        rv = await auth_db.conn.execute(dsns.select())
        return dict(await rv.fetchone())

    dsn['auth'] = (
        'Sentry sentry_key=%s, sentry_timestamp=23, '
        'sentry_client=foo/1.0' % dsn['public_key']
    )
    return dsn
