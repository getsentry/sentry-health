import time

from tervis.exceptions import BadAuth
from tervis.dependencies import DependencyDescriptor, DependencyMount
from tervis.db import Database, meta


DSN_ACTIVE = 0
DSN_INACTIVE = 1


def parse_auth_header(header):
    tokens = header.split(None, 1)
    if len(tokens) != 2 or tokens[0].lower() != 'sentry':
        raise BadAuth('Unsupported auth header')

    d = {}
    for pair in tokens[1].split(','):
        items = pair.split('=', 1)
        if len(items) != 2:
            continue
        key = items[0].strip()
        value = items[1].strip()
        if key[:7] == 'sentry_':
            key = key[7:]
        d[key] = value
    return d


class AuthInfo(object):

    def __init__(self, project_id, client, public_key, timestamp):
        self.project_id = project_id
        self.client = client
        self.public_key = public_key
        self.timestamp = timestamp

    def __bool__(self):
        return self.is_valid

    @property
    def is_valid(self):
        return self.project_id is not None

    @staticmethod
    def from_header(header, project_id):
        return AuthInfo.from_dict(parse_auth_header(header), project_id)

    @staticmethod
    def from_dict(d, project_id):
        try:
            return AuthInfo(
                project_id=project_id,
                public_key=d['key'],
                timestamp=d['timestamp'],
                client=d['client'],
            )
        except KeyError as e:
            raise BadAuth('Missing auth parameter "%s"' % e)

INVALID_AUTH = AuthInfo(
    project_id=None,
    client=None,
    public_key=None,
    timestamp=None
)


dsns = meta.Table('sentry_projectkey',
    meta.Column('id', meta.BigInteger, primary_key=True),
    meta.Column('project_id', meta.BigInteger),
    meta.Column('public_key', meta.String),
    meta.Column('status', meta.Integer),
)


class Auth(DependencyDescriptor):
    scope = 'operation'

    def __init__(self, optional=False):
        self.optional = optional

    @property
    def key(self):
        return (self.optional,)

    def instanciate(self, op):
        return AuthManager(op, self.optional)


class AuthManager(DependencyMount):
    db = Database(config='apiserver.auth_db')

    def __init__(self, op, optional):
        DependencyMount.__init__(self, parent=op)
        self.op = op
        self.optional = optional

    def get_auth_header(self):
        if self.op.req is None:
            if self.optional:
                return INVALID_AUTH
            raise RuntimeError('Authentication information requires active '
                               'request.')

        header = self.op.req.headers.get('x-sentry-auth')
        if not header:
            if self.optional:
                return INVALID_AUTH
            raise BadAuth('No authentication header supplied')

        return header

    async def validate_auth(self):
        header = self.get_auth_header()
        ai = AuthInfo.from_header(header, self.op.project_id)

        results = await self.db.conn.execute(dsns.select()
            .where(dsns.c.project_id == ai.project_id))
        dsn = await results.fetchone()

        if dsn is None or dsn.status != DSN_ACTIVE:
            raise BadAuth('Unknown authentication')

        if dsn.public_key != ai.public_key:
            raise BadAuth('Bad public key')

        if dsn.project_id != ai.project_id:
            raise BadAuth('Project ID mismatch')

        return ai

    async def __aenter__(self):
        await DependencyMount.__aenter__(self)
        try:
            return await self.validate_auth()
        except BadAuth:
            if self.optional:
                return INVALID_AUTH
            raise
