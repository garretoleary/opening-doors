from opening_doors import config


def test_invented_notice_present():
    assert "invented" in config.INVENTED_DATA_NOTICE.lower()


def test_caps_are_positive():
    assert config.SPEND_CAP_GBP > 0 and config.RUNS_PER_DAY > 0
