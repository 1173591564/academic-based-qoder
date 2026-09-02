import pytest

from scholar.commands import core_ops


@pytest.mark.parametrize(
    ("frozen", "source_tree", "expected"),
    [
        (True, True, "frozen (.exe)"),
        (False, True, "development (source)"),
        (False, False, "installed package"),
    ],
)
def test_runtime_mode_distinguishes_installed_wheels(
    monkeypatch, frozen, source_tree, expected
):
    monkeypatch.setattr(core_ops.config, "IS_FROZEN", frozen)
    monkeypatch.setattr(core_ops.config, "IS_SOURCE_TREE", source_tree)
    assert core_ops._runtime_mode() == expected
