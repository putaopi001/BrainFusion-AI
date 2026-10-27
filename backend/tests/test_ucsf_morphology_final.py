import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.analyze_ucsf_morphology_final import MORPH_FEATURES, morphology_from_counts


def test_reference_label_semantics_and_physical_morphology():
    # Counts represent 1 mm isotropic voxels: WT=14, TC=5, ET=3.
    got = morphology_from_counts({"0": 86, "1": 2, "2": 9, "4": 3}, [1, 1, 1])
    assert set(MORPH_FEATURES).issubset(got)
    assert {"WT_volume_ml", "TC_volume_ml", "ET_volume_ml"}.issubset(got)
    assert got["WT_volume_ml"] == pytest.approx(0.014)
    assert got["TC_volume_ml"] == pytest.approx(0.005)
    assert got["ET_volume_ml"] == pytest.approx(0.003)
    assert got["log1p_WT_volume_ml"] == pytest.approx(math.log1p(0.014))
    assert got["log1p_TC_volume_ml"] == pytest.approx(math.log1p(0.005))
    assert got["log1p_ET_volume_ml"] == pytest.approx(math.log1p(0.003))
    assert got["edema_fraction_WT"] == pytest.approx(9 / 14)
    assert got["ET_fraction_TC"] == pytest.approx(3 / 5)


def test_morphology_rejects_zero_ratio_denominator_and_unknown_label():
    with pytest.raises(ValueError, match="denominator"):
        morphology_from_counts({"0": 10, "1": 0, "2": 0, "4": 0}, [1, 1, 1])
    with pytest.raises(ValueError, match="unsupported labels"):
        morphology_from_counts({"0": 9, "7": 1}, [1, 1, 1])


def test_morphology_rejects_invalid_spacing():
    with pytest.raises(ValueError, match="voxel volume"):
        morphology_from_counts({"0": 9, "2": 1}, [1, 0, 1])
