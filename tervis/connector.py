import logging

from weakref import ref as weakref

from confluent_kafka import Consumer, Producer

from redis import StrictRedis


consumer_logger = logging.getLogger(__name__ + '.consumer')
producer_logger = logging.getLogger(__name__ + '.producer')


class Connector(object):

    def __init__(self, env):
        self._env = weakref(env)
        self.consumer_logger = consumer_logger
        self.producer_logger = producer_logger

    @property
    def env(self):
        rv = self._env()
        if rv is not None:
            return rv
        raise RuntimeError('Environment went away')

    def get_consumer(self, topics=None):
        rv = Consumer(self.env.get_consumer_config())
        if topics is None:
            return rv
        def _handle_assignment(consumer, partitions):
            self.consumer_logger.debug(
                'Received assignments: %r',
                [(p.topic, p.partition) for p in partitions]
            )
        rv.subscribe(topics, on_assign=_handle_assignment)
        return rv

    def get_producer(self):
        return Producer(self.env.get_producer_config())

    def get_redis(self):
        return StrictRedis(host='redis')
