import logging
import asyncio

from concurrent.futures import ThreadPoolExecutor
from libtervis.producer import Producer as SyncProducer

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
    env = CurrentEnvironment()

    def __init__(self, env):
        DependencyMount.__init__(self, parent=env)
        self.producer = SyncProducer(env.get_config('kafka'))

    async def __aexit__(self, exc_type, exc_value, tb):
        await self.flush()
        return await DependencyMount.__aexit__(self, exc_type, exc_value, tb)

    @property
    def event_count(self):
        return self.producer.event_count

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
        return await submit(lambda: self.producer.produce_event(
            project, event, timestamp))
