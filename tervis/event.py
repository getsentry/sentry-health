from ipaddress import ip_address
from functools import partial

from tervis.exceptions import ApiError


string_types = (str,)
int_types = (int,)
number_types = (float,) + int_types
scalar_types = string_types + int_types


def expect_type(data, key, ty, allow_none=False, validate=None,
                convert=None):
    rv = data.get(key)
    if rv is None:
        if not allow_none:
            raise ApiError('Missing parameter "%s"' % key)
        return None
    if not isinstance(rv, ty):
        raise ApiError('Invalid value for "%s"' % key)
    try:
        if validate is not None:
            validate(rv)
        if convert is not None:
            rv = convert(rv)
    except ValueError:
        raise ApiError('Invalid value for "%s"' % key)
    return rv


expect_string = partial(expect_type, ty=string_types)
expect_scalar = partial(expect_type, ty=scalar_types)
expect_number = partial(expect_type, ty=number_types)
expect_object = partial(expect_type, ty=dict)


def normalize_event(event):
    return {
        'ty': expect_string(event, 'ty'),
        'ts': expect_number(event, 'ts', convert=float),
        'ip': expect_type(event, 'ip', ty=string_types,
                          convert=lambda x: str(ip_address(x)),
                          allow_none=True),
        'dt': expect_number(event, 'dt', allow_none=True),
        'dev': expect_object(event, 'dev', allow_none=True) or {},
        'oid': expect_scalar(event, 'oid'),
        'sid': expect_scalar(event, 'sid'),
        'env': expect_string(event, 'env', allow_none=True),
        'rel': expect_string(event, 'rel', allow_none=True),
        'user': expect_object(event, 'user', allow_none=True) or {},
        'data': expect_object(event, 'data', allow_none=True) or {},
    }
