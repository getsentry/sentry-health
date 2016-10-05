import time


class AuthInfo(object):

    def __init__(self, project, public_key, timestamp):
        self.project = project
        self.public_key = public_key
        self.timestamp = timestamp


class AuthManager(object):

    def __init__(self, env):
        self.env = env

    async def auth_from_request(self, request):
        return AuthInfo(1, None, time.time())
