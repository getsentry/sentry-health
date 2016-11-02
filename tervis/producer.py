import time
import json
import threading
import logging
import asyncio
import functools

from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor

from tervis.connectors import KafkaProducer
from tervis.dependencies import DependencyDescriptor, DependencyMount
from tervis.environment import CurrentEnvironment


logger = logging.getLogger(__name__)


# We spawn a background thread where the producer will run, then we use
# the threadsafe loop methods to schedule work there.
producer_executor = ThreadPoolExecutor(max_workers=1)


def submit(func):
    return asyncio.get_event_loop().run_in_executor(producer_executor, func)


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
        return await DependencyMount.close_async(self)

    async def flush(self):
        def flush():
            logger.info(
                'Waiting for producer to flush %s events...',
                len(self.producer))
            self.producer.flush()
        return await submit(flush)

    def fast_flush(self):
        return _FastFlush(self)

    async def produce_event(self, project, event, timestamp=None):
        produce = functools.partial(
            self.producer.produce, 'events',
            json.dumps([project, event]).encode('utf-8'),
            key=str(project).encode('utf-8'))

        def produce():
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

        return await submit(produce)
