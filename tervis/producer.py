import time
import json
import logging
import functools

from contextlib import contextmanager

from ._compat import text_type


logger = logging.getLogger(__name__)


class Producer(object):

    def __init__(self, env):
        self.env = env
        self.producer = env.connector.get_kafka_producer()
        self.event_count = 0

    @contextmanager
    def guarded_section(self):
        start = time.time()
        try:
            yield self
        except KeyboardInterrupt:
            logger.info(
                'Waiting for producer to flush %s events before exiting...',
                len(self.producer),
            )
        self.producer.flush()
        stop = time.time()
        duration = stop - start
        i = self.event_count
        logger.info('%s total events produced in %0.2f seconds '
                    '(%0.2f events/sec.)', i, duration, (i / duration))

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
