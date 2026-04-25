from interface.web.main import read_root


def test_read_root() -> None:
    assert read_root() == "Tomatempo is running"
