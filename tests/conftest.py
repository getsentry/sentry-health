import pytest

from tervis.environment import Environment


@pytest.fixture(scope='function')
def env():
    return Environment()
