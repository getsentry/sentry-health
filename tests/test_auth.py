from tervis.auth import dsns, DSN_ACTIVE


def test_auth_basics(auth_db, runasync):
    @runasync
    async def test():
        await auth_db.conn.execute(dsns.insert(values={
            'project_id': 42,
            'public_key': 'a' * 20,
            'status': DSN_ACTIVE,
            'roles': 1,
        }))
        rv = await auth_db.conn.execute(dsns.select())
        rows = await rv.fetchall()
        assert len(rows) == 1
