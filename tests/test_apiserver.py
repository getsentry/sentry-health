import json

from tervis.auth import dsns, DSN_ACTIVE


def test_server_basics(server, runasync):
    @runasync
    async def run():
        async with server.request('GET', '/ping') as resp:
            assert resp.status == 200
            data = json.loads(await resp.text())
            assert data == {'ok': True}


def test_event_ingestion(dsn, server, runasync):
    path = '/events/%s' % dsn['project_id']
    headers = {
        'X-Sentry-Auth': dsn['auth'],
    }

    ev1 = {
        'ty': 'basic',
        'ts': 42.0,
        'oid': 13,
        'sid': 13,
    }
    ev2 = {
        'ty': 'success',
        'ts': 23.0,
        'oid': 14,
        'sid': 13,
    }

    @runasync
    async def run():
        data = '%s\n%s' % (json.dumps(ev1), json.dumps(ev2))
        async with server.request('POST', path, headers=headers,
                                  data=data) as resp:
            data = json.loads(await resp.text())
            assert data['errors'] == []
            assert data['events'] == 2


def test_project_blacklists(dsn, server, runasync, projectoptions):
    projectoptions.update({
        'sentry:blacklisted_ips': ['192.168.0.1'],
    }, project_id=42)

    path = '/events/%s' % dsn['project_id']

    ev = {
        'ty': 'basic',
        'ts': 42.0,
        'oid': 13,
        'sid': 13,
    }

    @runasync
    async def run():
        headers = {
            'X-Sentry-Auth': dsn['auth'],
            'X-Forwarded-For': '192.168.0.1, 127.0.0.1',
        }
        data = json.dumps(ev)
        async with server.request('POST', path, headers=headers,
                                  data=data) as resp:
            assert resp.status == 403

        headers = {
            'X-Sentry-Auth': dsn['auth'],
            'X-Forwarded-For': '192.168.0.2, 127.0.0.1',
        }
        async with server.request('POST', path, headers=headers,
                                  data=data) as resp:
            assert resp.status == 200
