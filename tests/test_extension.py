from mopidy_jamendo import Extension


def test_get_default_config():
    ext = Extension()

    config = ext.get_default_config()

    assert "[jamendo]" in config
    assert "enabled = true" in config


def test_get_config_schema():
    ext = Extension()

    schema = ext.get_config_schema()

    assert "client_id" in schema


# TODO Write more tests
