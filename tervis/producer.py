import time
import json
import logging
import functools

from contextlib import contextmanager

from ._compat import text_type
from .connectors import KafkaProducer
from .dependencies import DependencyDescriptor, DependencyMount
from .environment import CurrentEnvironment


logger = logging.getLogger(__name__)


class Producer(DependencyDescriptor):
    scope = 'env'

    def instanciate(self, env):
        return ProducerImpl(env)


class _FastFlush(object):

    def __init__(self, producer):
        self.producer = producer

    def __aenter__(self):
        return self

    def __aexit__(self, exc_type, exc_value, tb):
        if self.producer.event_count % 1000 == 0:
            return self.producer.flush()


class ProducerImpl(DependencyMount):
    producer = KafkaProducer()
    env = CurrentEnvironment()

    def __init__(self, env):
        DependencyMount.__init__(self, parent=env)
        self.event_count = 0

    async def close_async(self):
        await self.flush()
        return DependencyMount.close(self)

    async def flush(self):
        logger.info(
            'Waiting for producer to flush %s events...', len(self.producer))
        # XXX: thread this
        self.producer.flush()

    def fast_flush(self):
        return _FastFlush(self)

    async def produce_event(self, project, event, timestamp=None):
        produce = functools.partial(
            self.producer.produce, 'events',
            json.dumps([project, event]).encode('utf-8'),
            key=text_type(project).encode('utf-8'))

        try:
            produce()
        except BufferError as e:
            logger.info(
                'Caught %r, waiting for %s events to be produced...',
                e,
                len(self.producer),
            )
            self.producer.flush()  # wait for buffer to empty
            logger.info('Done waiting, continue to generate events...')
            produce()

        self.event_count += 1

        i = self.event_count
        if i % 1000 == 0:
            if timestamp is None:
                timestamp = time.time()
            logger.info('%s events produced, current timestamp is %s.',
                        i, timestamp)
