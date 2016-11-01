import os
import yaml

from tervis._compat import text_type
from tervis.utils import merge, iter_segments
from tervis.exceptions import ConfigError
from tervis.dependencies import DependencyMount, DependencyDescriptor


CONFIG_DEFAULTS = {
    'apiserver': {
        'port': 8000,
        'host': '0.0.0.0',
        'limits': {
            'max_json_packet': 1024 * 64,
        },
        'auth_db': 'default',
    },
    'recorder': {
        'ttl': 60 * 60 * 24 * 7,
        'resolutions': [60, 60 * 60],
        'batch_size': 1000,
    },
    'kafka': {
        'consumer': {
            'group.id': 'tarvis-events',
            'enable.auto.commit': 'false',
            'default.topic.config': {
                'auto.offset.reset': 'earliest',
            },
        }
    },
    'databases': {
        'default': {
            'backend': 'postgres',
            'database': 'sentry',
            'host': '127.0.0.1',
            'user': None,
            'password': None,
        },
    }
}


def load_config(filename):
    with open(filename, 'rb') as f:
        return yaml.safe_load(f) or {}


def discover_config():
    fn = os.environ.get('TERVIS_CONFIG')
    if not fn:
        raise RuntimeError('TERVIS_CONFIG not exported as envvar')
    return load_config(fn)


class CurrentEnvironment(DependencyDescriptor):
    pass


class Environment(DependencyMount):

    def __init__(self, config=None):
        DependencyMount.__init__(self,
            scope='env',
            descriptor_type=CurrentEnvironment,
            synchronized=True
        )
        if config is None:
            config = discover_config()
        self.config = merge(CONFIG_DEFAULTS, config)

    def get_config(self, *items):
        rv = self.config
        for seg in iter_segments(items):
            if not isinstance(rv, dict):
                raise ConfigError('%r is not not a dictionary' %
                                  '.'.join(map(text_type, seg)))
            if rv is None:
                rv = {}
            rv = rv.get(seg)
        return rv

    def get_consumer_config(self):
        return merge(self.get_config('kafka.common'),
                     self.get_config('kafka.consumer'))

    def get_producer_config(self):
        return merge(self.get_config('kafka.common'),
                     self.get_config('kafka.producer'))
