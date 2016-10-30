import pytest

from tervis.environment import Environment


@pytest.fixture(scope='function')
def env_factory():
    return Environment


@pytest.fixture(scope='function')
def env(request, env_factory):
    env = env_factory()
    env.__enter__()
    request.addfinalizer(lambda: env.__exit__(None, None, None))
    return env
