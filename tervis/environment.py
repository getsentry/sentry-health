import os
import yaml

from ._compat import text_type
from .connector import Connector
from .utils import merge, iter_segments
from .exceptions import ConfigError


CONFIG_DEFAULTS = {
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


class Environment(object):

    def __init__(self, config=None):
        if config is None:
            config = discover_config()
        self.config = merge(CONFIG_DEFAULTS, config)
        self.connector = Connector(self)

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
