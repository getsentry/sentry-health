from tervis.web import is_allowed_origin


def test_is_allowed_origin():
    assert is_allowed_origin('http://foo', ['http://foo'])
    assert is_allowed_origin('http://foo', ['*'])
    assert not is_allowed_origin('http://foo', ['http://bar'])
