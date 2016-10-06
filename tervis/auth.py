import time

from .exceptions import BadAuth


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
        value = items[0].strip()
        if key[:7] == 'sentry_':
            key = key[7:]
        d[key] = value
    return d


class AuthInfo(object):

    def __init__(self, project, client, public_key, timestamp):
        self.project = project
        self.client = client
        self.public_key = public_key
        self.timestamp = timestamp

    @staticmethod
    def from_header(header, project):
        return AuthInfo.from_dict(parse_auth_header(header), project)

    @staticmethod
    def from_dict(d, project):
        try:
            return AuthInfo(
                project=project,
                public_key=d['key'],
                timestamp=d['timestamp'],
                client=d['client'],
            )
        except KeyError as e:
            raise BadAuth('Missing auth parameter "%s"' % e)


class AuthManager(object):

    def __init__(self, env):
        self.env = env

    async def auth_from_request(self, request, project):
        header = request.headers.get('x-sentry-auth')
        return AuthInfo.from_header(header, project)
