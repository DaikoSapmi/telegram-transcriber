from config.settings import Settings


def test_authorized_usernames_are_case_insensitive():
    config = Settings(allowed_users="123,@RuneSapmi")
    assert config.is_user_allowed("123")
    assert config.is_user_allowed("999", "runesapmi")
    assert not config.is_user_allowed("999", "someone_else")
