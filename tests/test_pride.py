from commands.cogs.pride import resolveFlag


def test_flag_names_are_normalized() -> None:
    assert resolveFlag(" Pride ") == "pride"
    assert resolveFlag("MLM (older)") == "mlm_old"


def test_unknown_flag_returns_none() -> None:
    assert resolveFlag("not-a-real-flag") is None
