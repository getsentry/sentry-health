import logging

from confluent_kafka import Consumer, Producer

from redis import StrictRedis

from .depmgr import DependencyDescriptor


consumer_logger = logging.getLogger(__name__ + '.consumer')
producer_logger = logging.getLogger(__name__ + '.producer')


class KafkaConsumer(DependencyDescriptor):
    scope = 'env'

    def __init__(self, topics=None):
        self.topics = topics

    @property
    def key(self):
        return (tuple(self.dependency_key or ()),)

    def instanciate(self, env):
        rv = Consumer(env.get_consumer_config())
        if self.topics is None:
            return rv
        def _handle_assignment(consumer, partitions):
            self.consumer_logger.debug(
                'Received assignments: %r',
                [(p.topic, p.partition) for p in partitions]
            )
        rv.subscribe(self.topics, on_assign=_handle_assignment)
        return rv


class KafkaProducer(DependencyDescriptor):
    scope = 'env'

    def instanciate(self, env):
        return Producer(env.get_producer_config())


class Redis(DependencyDescriptor):
    scope = 'env'

    def instanciate(self, env):
        return StrictRedis(host='redis')
