import json

from tervis.auth import dsns, DSN_ACTIVE


def test_server_basics(server, runasync):
    @runasync
    async def run():
        async with server.request('GET', '/ping') as resp:
            assert resp.status == 200
            data = json.loads(await resp.text())
            assert data == {'ok': True}


def test_event_ingestion(auth_db, server, runasync):
    @runasync
    async def dsn():
        await auth_db.conn.execute(dsns.insert(values={
            'project_id': 42,
            'public_key': 'a' * 20,
            'status': DSN_ACTIVE,
            'roles': 1,
        }))
        rv = await auth_db.conn.execute(dsns.select())
        rows = await rv.fetchall()
        assert len(rows) == 1
        return rows[0]

    auth = (
        'Sentry sentry_key=%s, sentry_timestamp=23, '
        'sentry_client=foo/1.0' % dsn['public_key']
    )
    path = '/events/%s' % dsn['project_id']
    headers = {
        'X-Sentry-Auth': auth,
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
