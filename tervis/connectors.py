import logging

from confluent_kafka import Consumer

from redis import StrictRedis

from libtervis.utils import merge
from tervis.dependencies import DependencyDescriptor


consumer_logger = logging.getLogger(__name__ + '.consumer')


class KafkaConsumer(DependencyDescriptor):
    scope = 'env'

    def __init__(self, topics=None):
        self.topics = topics

    @property
    def key(self):
        return tuple(self.topics or ())

    def instanciate(self, env):
        config = merge(env.get_config('kafka.common'),
                       env.get_config('kafka.consumer'))
        rv = Consumer(config)
        if self.topics is None:
            return rv

        def _handle_assignment(consumer, partitions):
            consumer_logger.debug(
                'Received assignments: %r',
                [(p.topic, p.partition) for p in partitions]
            )
        rv.subscribe(self.topics, on_assign=_handle_assignment)
        return rv


class Redis(DependencyDescriptor):
    scope = 'env'

    def instanciate(self, env):
        return StrictRedis(host='redis')
