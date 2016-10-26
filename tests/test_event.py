from tervis.event import normalize_event


def test_basic_validation():
    evt = normalize_event({
        'ty': 'basic',
        'ts': 42.0,
        'oid': 13,
        'sid': 13,
    })
    assert evt == {
        'data': {},
        'dev': {},
        'dt': None,
        'env': None,
        'ip': None,
        'oid': 13,
        'rel': None,
        'sid': 13,
        'ts': 42.0,
        'ty': 'basic',
        'user': {}
    }
