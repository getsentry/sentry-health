import sys


PY2 = sys.version_info[0] == 2


if PY2:
    iteritems = lambda x: x.iteritems()
    iterkeys = lambda x: x.iterkeys()
    itervalues = lambda x: x.itervalues()
    text_type = unicode
else:
    iteritems = lambda x: x.items()
    iterkeys = lambda x: x.ikeys()
    itervalues = lambda x: x.values()
    text_type = str
