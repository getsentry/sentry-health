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


def get_db(request, config, metadata, op):
    class Container(DependencyMount):
        db = Database(config=config)
        def __init__(self):
            DependencyMount.__init__(self, parent=op)

    container = Container()
    container.__enter__()
    ensure_schema(request, metadata, container.db.conn)
    request.addfinalizer(lambda: container.__exit__(None, None, None))
    return container.db


@pytest.fixture(scope='module')
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
def auth_db(request, op):
    from tervis.auth import metadata
    return get_db(request, 'apiserver.auth_db', metadata, op)


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
