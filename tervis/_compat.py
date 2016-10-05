import sys


PY2 = sys.version_info[0] == 2


if PY2:
    iteritems = lambda x: x.iteritems()
    iterkeys = lambda x: x.iterkeys()
    itervalues = lambda x: x.itervalues()
    text_type = unicode
    string_types = (str, unicode)
    int_types = (int, long)
    number_types = (float,) + int_types

    def implements_to_string(x):
        x.__unicode__ = x.__str__
        x.__str__ = lambda x: unicode(x).encode('utf-8')
        return x

else:
    iteritems = lambda x: x.items()
    iterkeys = lambda x: x.ikeys()
    itervalues = lambda x: x.values()
    text_type = str
    string_types = (str,)
    int_types = (int,)
    implements_to_string = lambda x: x


number_types = (float,) + int_types
scalar_types = string_types + int_types
