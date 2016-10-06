import time
import json
import logging
import functools

from contextlib import contextmanager

from ._compat import text_type
from .connectors import KafkaProducer
from .depmgr import Dependency


logger = logging.getLogger(__name__)


class Producer(Dependency):
    scope = 'env'

    def __resolve_dependency__(self, env):
        return ProducerImpl(env)


class ProducerImpl(object):
    producer = KafkaProducer()

    def __init__(self, env):
        self.env = env
        self.event_count = 0
        self._depth = 0

    @contextmanager
    def full_guard(self):
        start = time.time()
        with self:
            try:
                yield
            except KeyboardInterrupt:
                pass
        stop = time.time()
        duration = stop - start
        i = self.event_count
        logger.info('%s total events produced in %0.2f seconds '
                    '(%0.2f events/sec.)', i, duration, (i / duration))

    def flush(self):
        logger.info(
            'Waiting for producer to flush %s events...', len(self.producer))
        self.producer.flush()

    def __enter__(self):
        self._depth += 1
        return self

    def __exit__(self, exc_type, exc_value, tb):
        self._depth -= 1
        if self._depth == 0:
            self.flush()

    @contextmanager
    def partial_guard(self):
        try:
            yield
        finally:
            if self.event_count % 1000 == 0:
                self.flush()

    def produce_event(self, project, event, timestamp=None):
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
