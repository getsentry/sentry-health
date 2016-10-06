import pytest

from tervis.environment import Environment


@pytest.fixture(scope='module')
def env():
    return Environment()
