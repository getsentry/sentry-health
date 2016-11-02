from ipaddress import ip_address, ip_network

from tervis.dependencies import DependencyMount, DependencyDescriptor
from tervis.environment import CurrentEnvironment
from tervis.projectoptions import ProjectOptions


class Filter(DependencyDescriptor):
    scope = 'operation'

    def instanciate(self, op):
        return FilterManager(op)


class FilterManager(DependencyMount):
    env = CurrentEnvironment()
    project_options = ProjectOptions()

    def __init__(self, op):
        DependencyMount.__init__(self, parent=op)

    def ip_is_system_blacklisted(self, addr):
        addr = ip_address(addr)
        for net in self.env.get_config('apiserver.whitelisted_ips'):
            try:
                net = ip_network(net, strict=False)
            except ValueError:
                continue
            if addr in net:
                return False
        for net in self.env.get_config('apiserver.blacklisted_ips'):
            try:
                net = ip_network(net, strict=False)
            except ValueError:
                continue
            if addr in net:
                return True
        return False

    async def ip_is_project_blacklisted(self, addr, project_id=None):
        opt = await self.project_options.get('sentry:blacklisted_ips',
                                             project_id=project_id)
        for net in opt or ():
            try:
                net = ip_network(net, strict=False)
            except ValueError:
                continue
            if addr in net:
                return True
        return False

    async def ip_is_blacklisted(self, addr, project_id=None):
        if self.ip_is_system_blacklisted(addr):
            return True
        if await self.ip_is_project_blacklisted(addr, project_id):
            return True
        return False
