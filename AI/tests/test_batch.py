from __future__ import annotations

from pathlib import Path

from ftp_ai.batch import _select_spread


def test_select_spread_keeps_evenly_spaced_paths() -> None:
    paths = [Path(f"frame_{index:04d}.jpg") for index in range(10)]

    selected = _select_spread(paths, limit=4)

    assert selected == [
        Path("frame_0000.jpg"),
        Path("frame_0002.jpg"),
        Path("frame_0005.jpg"),
        Path("frame_0007.jpg"),
    ]


def test_select_spread_returns_all_paths_when_limit_is_zero() -> None:
    paths = [Path("a.jpg"), Path("b.jpg")]

    assert _select_spread(paths, limit=0) == paths
