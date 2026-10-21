"""The candidate gate must never replace a previously accepted gate."""
import json
import sys

import pytest

from tools import verify_feature_extraction as gate


def test_existing_gate_is_not_overwritten_or_extracted(tmp_path, monkeypatch):
    output = tmp_path / 'accepted'
    output.mkdir()
    filename = output / 'compatibility.json'
    original = json.dumps({'status': 'passed', 'historical': True})
    filename.write_text(original, encoding='utf-8')
    monkeypatch.setattr(sys, 'argv', ['verify_feature_extraction', '--output', str(output),
                                   '--worker', sys.executable, '--data-dir', str(tmp_path)])
    def forbidden(*args, **kwargs):
        pytest.fail('Existing gate must be rejected before any extractor starts')
    monkeypatch.setattr(gate.subprocess, 'run', forbidden)
    with pytest.raises(FileExistsError):
        gate.main()
    assert filename.read_text(encoding='utf-8') == original
    assert list(output.iterdir()) == [filename]


def test_missing_explicit_output_cannot_use_historical_default(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['verify_feature_extraction'])
    with pytest.raises(SystemExit) as error:
        gate.main()
    assert error.value.code == 2
