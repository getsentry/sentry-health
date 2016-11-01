import time
import json
import logging

from collections import defaultdict
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor

from confluent_kafka import KafkaError, TopicPartition

from tervis.connectors import KafkaConsumer, Redis
from tervis.dependencies import DependencyMount
from tervis.environment import CurrentEnvironment


logger = logging.getLogger(__name__)


def batch(consumer, func, size=10000):
    start = time.time()

    # XXX: This is not currently partition aware for the sake of simplicity --
    # it should process and commit partitions independently.
    messages = []

    while True:
        message = consumer.poll(timeout=0.1)
        if message is None:
            continue

        error = message.error()
        if error is not None:
            if error.code() == KafkaError._PARTITION_EOF:
                continue
            else:
                raise Exception(error)

        messages.append(message)
        if len(messages) != size:
            continue

        func(messages)
        offsets = [TopicPartition(message.topic(), message.partition(),
                                  message.offset() + 1)]
        consumer.commit(offsets=offsets, async=False)
        duration = time.time() - start
        logger.info('Processed %s events in %0.2f seconds (%0.2f '
                    'messages/sec), committed offsets: %r',
                    len(messages), duration, len(messages) / duration,
                    offsets)
        start = time.time()
        messages = []


class Recorder(DependencyMount):
    redis = Redis()
    env = CurrentEnvironment()
    consumer = KafkaConsumer(topics=['events'])

    def __init__(self, env):
        DependencyMount.__init__(self, parent=env)
        self.ttl = self.env.get_config('recorder.ttl')
        self.resolutions = self.env.get_config('recorder.resolutions')
        self.batch_size = self.env.get_config('recorder.batch_size')

    def format_session_key(self, key):
        project, session = key
        return 's:{}:{}'.format(project, session)

    def dump_session_data(self, value):
        return json.dumps(value).encode('utf-8')

    def load_session_data(self, value):
        return json.loads(value.decode('utf-8')) if value is not None else None

    def load_message(self, message):
        return json.loads(message.value().decode('utf-8'))

    def process_session_events(self, session, events):
        for event in events:
            if session is None:
                session = {
                    'start': event['ts'],
                    'watermark': event['ts'],
                    'stop': None,
                }
            else:
                if session['stop'] is not None:
                    break

                if event['ts'] < session['start']:
                    session['start'] = event['ts']

                if event['ts'] > session['watermark']:
                    session['watermark'] = event['ts']

            if event['ty'] == 'cl':
                session['stop'] = max(
                    event['ts'],
                    session['watermark'],
                )

        return session

    def buckets(self, start, stop=None):
        if stop is None:
            stop = start
        results = set()
        for resolution in self.resolutions:
            for index in range(int(start // resolution),
                               int((stop // resolution) + 1)):
                results.add((resolution, index))
        return results

    def process(self, messages):
        # Batch together all of events by session.
        sessions = defaultdict(list)
        for message in messages:
            project, event = self.load_message(message)
            sessions[(project, event['sid'])].append(event)

        # Fetch the session state for all affected sessions.
        keys = list(sessions.keys())
        data = self.redis.mget(map(self.format_session_key, keys))

        # Update the sessions.
        results = {}
        counters = defaultdict(set)
        touched = set()
        closed = set()

        for key, session in zip(keys, map(self.load_session_data, data)):
            updated = self.process_session_events(
                session.copy() if session is not None else None,
                sessions[key],
            )

            if updated['stop'] is None:
                touched.add(key)

            def changed(key, callback):
                prev = session and session.get(key) or None
                curr = updated and updated.get(key) or None
                if prev != curr:
                    return callback(prev, curr)

            results[self.format_session_key(key)] = self.dump_session_data(updated)

            update_buckets = set()

            def handle_start_change(previous, current):
                if previous is not None:
                    assert current < previous
                    update_buckets.update(self.buckets(current, previous))
                else:
                    update_buckets.update(self.buckets(current))

            def handle_watermark_change(previous, current):
                if previous is not None:
                    assert current > previous
                    update_buckets.update(self.buckets(previous, current))

            def handle_stop_change(previous, current):
                assert previous is None
                closed.add(key)

            changed('start', handle_start_change)
            changed('watermark', handle_watermark_change)
            changed('stop', handle_stop_change)

            project, session = key
            for bucket in update_buckets:
                counters[bucket + (project,)].add(session)

        now = time.time()

        pipeline = self.redis.pipeline()
        pipeline.mset(results)
        for key in results.keys():
            pipeline.expire(key, self.ttl)
        if touched:
            pipeline.zadd('s:schedule', **{'%s:%s' % x: now for x in touched})
        if closed:
            pipeline.zrem('s:schedule', *['%s:%s' % x for x in closed])
        for (resolution, index, project), sessions in counters.items():
            pipeline.pfadd(
                's:ts:{}:{}:{}'.format(resolution, index, project),
                *sessions
            )
        pipeline.execute()

    def run(self):
        try:
            batch(self.consumer, self.process, size=self.batch_size)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.exception(e)
