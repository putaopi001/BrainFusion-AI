import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "analyze_ucsf_pdgm_pilot.py"
SPEC = importlib.util.spec_from_file_location("analyze_ucsf_pdgm_pilot", SCRIPT)
PILOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PILOT)


def test_official_reference_encoding_maps_only_enhancing_4_to_model_label_3():
    source = np.array([0, 1, 2, 4, 4, 2, 1], dtype=np.uint8)
    original = source.copy()
    result = PILOT.recode_reference_labels(source)
    assert result.tolist() == [0, 1, 2, 3, 3, 2, 1]
    assert np.array_equal(source, original)
    assert set(np.unique(result)) == {0, 1, 2, 3}


def test_reference_label_mapping_rejects_unreviewed_integer_codes():
    with pytest.raises(ValueError, match="subset of 0/1/2/4"):
        PILOT.recode_reference_labels(np.array([0, 1, 3], dtype=np.uint8))


@pytest.mark.parametrize(("value", "expected"), [
    ("UCSF-PDGM-035", 35),
    ("UCSF-PDGM-0035", 35),
    ("UCSF-PDGM-035_FU001d", 35),
])
def test_metadata_and_image_ids_normalize_by_numeric_suffix(value, expected):
    from scripts.download_ucsf_pdgm_subset import normalized_id
    assert normalized_id(value) == expected


def test_unrecognized_patient_id_is_rejected():
    from scripts.download_ucsf_pdgm_subset import normalized_id
    with pytest.raises(ValueError):
        normalized_id("sub-002")


def test_pilot_selection_is_deterministic_baseline_only_and_event_stratified(tmp_path, monkeypatch):
    import csv
    import hashlib
    from scripts import download_ucsf_pdgm_subset as downloader

    source = tmp_path / "official-shape-test.csv"
    fields = ["ID", "Final pathologic diagnosis (WHO 2021)", "IDH", "OS", "1-dead 0-alive", "BraTS21 ID"]
    rows = []
    for patient in range(1, 13):
        rows.append({"ID": f"UCSF-PDGM-{patient:03d}",
                     "Final pathologic diagnosis (WHO 2021)": "Glioblastoma, IDH-wildtype",
                     "IDH": "Wildtype", "OS": str(500 + patient),
                     "1-dead 0-alive": str(patient % 2), "BraTS21 ID": ""})
    rows.append({**rows[0], "ID": "UCSF-PDGM-001_FU001d"})
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    monkeypatch.setattr(downloader, "METADATA_SHA256", hashlib.sha256(source.read_bytes()).hexdigest())

    first = downloader.choose_cases(source, 10)
    second = downloader.choose_cases(source, 10)
    assert [row["_numeric_id"] for row in first] == [row["_numeric_id"] for row in second]
    assert len({row["_numeric_id"] for row in first}) == 10
    assert sum(row["_event"] == "1" for row in first) == 5
    assert sum(row["_event"] == "0" for row in first) == 5
    assert all("_FU" not in row["ID"] for row in first)
