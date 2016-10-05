class AuthManager(object):

    def __init__(self, env):
        self.env = env

    async def auth_from_request(self, request):
        return None

    def validate_token(self, project_id, token):
        return True
