import pytest

from config.settings import Settings


def test_authorized_usernames_are_case_insensitive():
    config = Settings(allowed_users="123,@RuneSapmi")
    assert config.is_user_allowed("123")
    assert config.is_user_allowed("999", "runesapmi")
    assert not config.is_user_allowed("999", "someone_else")


def test_short_whisper_segment_profile_is_the_default():
    config = Settings()
    assert config.whisper_segment_seconds == 10
    assert config.sami_num_beams == 1


@pytest.mark.parametrize("seconds", [4, 31])
def test_whisper_segment_length_must_stay_in_short_form(seconds: int):
    config = Settings(telegram_bot_token="token", whisper_segment_seconds=seconds)
    with pytest.raises(ValueError, match="WHISPER_SEGMENT_SECONDS"):
        config.validate()
