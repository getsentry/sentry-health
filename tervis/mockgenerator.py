import time
import random
import logging
import itertools

from collections import defaultdict

from tervis.producer import Producer
from tervis.dependencies import DependencyMount


logger = logging.getLogger(__name__)


PROJECT_POOL_INITIAL_SIZE = 10
SESSION_POOL_INITIAL_SIZE = 10

SESSION_CREATION_PROBABILITY = 0.007
SESSION_CLOSE_PROBABILITY = 0.002
SESSION_FALSE_CLOSE_PROBABILITY = 0.001
SESSION_DROP_PROBABILITY = 0.005

TICK_DURATION = 0.1
TICK_PROBABILITY = 0.1


def generate(random, timestamp):
    projects = range(1, PROJECT_POOL_INITIAL_SIZE + 1)

    session_sequences = defaultdict(lambda: itertools.count(1))
    sessions = defaultdict(lambda: itertools.count(0))

    # Initialize the session pool.
    for project in projects:
        for session in range(1, SESSION_POOL_INITIAL_SIZE + 1):
            sid = next(session_sequences[project])
            sessions[(project, sid)]  # touch

    logger.debug('Initialized session pool, %s sessions '
                 'currently active.', len(sessions))

    def create_session():
        project = random.choice(projects)
        sid = next(session_sequences[project])
        key = (project, sid)
        sessions[key]  # touch
        logger.debug('Created session %r, %s sessions currently '
                     'active.', key, len(sessions))
        return key

    while True:
        if random.random() <= TICK_PROBABILITY:
            timestamp = timestamp + TICK_DURATION

        if random.random() <= SESSION_CREATION_PROBABILITY:
            key = create_session()
        else:
            try:
                key = random.sample(sessions.keys(), 1)[0]
            except ValueError:
                key = create_session()

        project, sid = key

        # TODO: Skip or generate out-of-order operation IDs.
        oid = next(sessions[key])

        ty = 'op'

        if random.random() <= SESSION_FALSE_CLOSE_PROBABILITY:
            ty = 'cl'
        if random.random() <= SESSION_CLOSE_PROBABILITY:
            del sessions[key]
            logger.debug('Deleted session %r, %s sessions currently '
                         'active.', key, len(sessions))
            ty = 'cl'
        elif random.random() <= SESSION_DROP_PROBABILITY:
            del sessions[key]
            logger.debug('Dropped session %r, %s sessions currently '
                         'active.', key, len(sessions))

        yield timestamp, project, {
            'sid': sid,
            'oid': oid,
            'ts': timestamp + random.triangular(-5 * 60, 10 * 60, 0),
            'ty': ty,
        }


class MockGenerator(DependencyMount):
    producer = Producer()

    def __init__(self, env, seed=None, epoch=None):
        DependencyMount.__init__(self, parent=env)

        if epoch is None:
            epoch = time.time()
        if seed is None:
            seed = time.time()

        self.epoch = epoch
        self.seed = seed
        self.random = random.Random(seed)

    def run(self, count=None):
        logger.info('Using random seed: {}'.format(self.seed))

        events = generate(self.random, self.epoch)
        if count is not None:
            events = itertools.islice(events, count)

        for i, (timestamp, project, event) in enumerate(events, 1):
            self.producer.produce_event(project, event, timestamp)
