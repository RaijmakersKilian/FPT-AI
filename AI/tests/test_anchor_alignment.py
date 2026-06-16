"""Synthetic test: the anchor pair must resolve the lengthwise mirror.

Builds an almost-symmetric synthetic bridge, transforms it with a random
similarity, and checks that the anchor-disambiguated comparison maps the
marked end to the correct model end (which blind alignment cannot guarantee).

Run with: python AI/tests/test_anchor_alignment.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ftp_ai.model_comparison import compare_reconstruction_to_model


def main() -> None:
    rng = np.random.default_rng(11)
    # Nearly symmetric bridge deck; a small asymmetric stub marks one end so
    # the test can verify which end landed where.
    deck = np.column_stack(
        [rng.uniform(-200, 200, 40_000), rng.uniform(-12, 12, 40_000), rng.uniform(0, 8, 40_000)]
    )
    stub = np.column_stack(
        [rng.uniform(195, 205, 2_000), rng.uniform(-3, 3, 2_000), rng.uniform(8, 12, 2_000)]
    )
    reference = np.vstack([deck, stub])

    angle = 2.1
    rotation = np.array(
        [[np.cos(angle), -np.sin(angle), 0.0], [np.sin(angle), np.cos(angle), 0.0], [0.0, 0.0, 1.0]]
    )
    scale, translation = 1.7, np.array([-40.0, 90.0, 5.0])
    current = (scale * (rotation @ reference.T)).T + translation

    tmp = Path(tempfile.mkdtemp())
    colors = np.full((len(reference), 4), 200, np.uint8)
    trimesh.PointCloud(reference, colors=colors).export(str(tmp / "ref.ply"))
    trimesh.PointCloud(current, colors=colors).export(str(tmp / "cur.ply"))

    # Anchor: a rough click near the +x end (where the stub is), deliberately
    # offset by ~15 units to simulate imprecise picking.
    anchor_ref = np.array([[185.0, 5.0, 4.0]])
    anchor_cur = (scale * (rotation @ np.array([[190.0, -6.0, 6.0]]).T)).T + translation
    (tmp / "anchor_ref.json").write_text(json.dumps({"points": anchor_ref.tolist()}))
    (tmp / "anchor_cur.json").write_text(json.dumps({"points": anchor_cur.tolist()}))

    summary = compare_reconstruction_to_model(
        current_ply=tmp / "cur.ply",
        final_model=tmp / "ref.ply",
        output_dir=tmp / "out",
        anchor_current=tmp / "anchor_cur.json",
        anchor_reference=tmp / "anchor_ref.json",
        icp_iterations=20,
    )
    alignment = summary["alignment"]
    print("method:", alignment["method"])
    print("chosen mirror:", alignment["chosen_mirror"])
    print("anchor distance chosen/rejected:", alignment["anchor_distance_chosen"], "/", alignment["anchor_distance_rejected"])
    print("built:", summary["progress_estimate"]["model_built_pct"], "median:", summary["distance_median"])

    assert alignment["method"] == "anchor_disambiguated"
    assert alignment["anchor_distance_chosen"] < alignment["anchor_distance_rejected"]
    assert summary["progress_estimate"]["model_built_pct"] > 99.0
    assert summary["distance_median"] < 0.01
    # The stub end must land on the stub end: with the correct mirror the
    # anchor distance is small (clicking error only), with the wrong one it
    # would be roughly the bridge length in normalized units (~2.0).
    assert alignment["anchor_distance_chosen"] < 0.3
    assert alignment["anchor_distance_rejected"] > 1.0
    print("ANCHOR ALIGNMENT TEST OK")


if __name__ == "__main__":
    main()
