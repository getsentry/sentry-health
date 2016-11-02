import json


def test_server_basics(server, runasync):
    @runasync
    async def foo():
        async with server.request('GET', '/ping') as resp:
            assert resp.status == 200
            data = json.loads(await resp.text())
            assert data == {'ok': True}
