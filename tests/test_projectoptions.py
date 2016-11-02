from tervis.dependencies import DependencyMount
from tervis.projectoptions import ProjectOptions


def test_basics(project_db, op, runasync):
    class Stuff(DependencyMount):
        options = ProjectOptions()
        def __init__(self):
            DependencyMount.__init__(self, parent=op)

    @runasync
    async def run():
        async with Stuff() as stuff:
            await stuff.options.set_unsafe('sentry:blacklisted_ips',
                                           ['127.0.0.1'], 42)
            val = await stuff.options.get('sentry:blacklisted_ips', 42)
            assert val == ['127.0.0.1']

            stuff.options.cache.clear()

            val = await stuff.options.get('sentry:blacklisted_ips', 42)
            assert val == ['127.0.0.1']
