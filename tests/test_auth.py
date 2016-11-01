from tervis.auth import dsns, DSN_ACTIVE, AuthInfo


def test_auth_basics(auth_db, runasync):
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

    assert dsn['project_id'] == 42

    ai = AuthInfo.from_header('Sentry sentry_key=%s, sentry_timestamp=23, '
                              'sentry_client=foo/1.0' % ('a' * 20), 42)
    assert ai.project_id == 42
    assert ai.client == 'foo/1.0'
    assert ai.public_key == 'a' * 20
    assert ai.timestamp == 23.0
