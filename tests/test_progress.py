import pytest

from adw.progress import (
    LINE_CAP,
    ProgressCapExceeded,
    append_entry,
    assert_under_cap,
    is_over_cap,
    line_count,
)


def test_line_count_missing_file_is_zero(tmp_path):
    assert line_count(tmp_path / "progress.txt") == 0


def test_append_entry_appends_with_trailing_newline(tmp_path):
    path = tmp_path / "progress.txt"
    append_entry(path, "first learning")
    append_entry(path, "second learning")
    assert path.read_text(encoding="utf-8") == "first learning\nsecond learning\n"
    assert line_count(path) == 2


def test_cap_enforcement(tmp_path):
    path = tmp_path / "progress.txt"
    path.write_text("\n".join(f"line {i}" for i in range(LINE_CAP)), encoding="utf-8")
    assert not is_over_cap(path)
    assert_under_cap(path)
    append_entry(path, "one too many")
    assert is_over_cap(path)
    with pytest.raises(ProgressCapExceeded, match="Prune"):
        assert_under_cap(path)
