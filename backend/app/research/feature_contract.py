"""Explicit feature contract for the reference-trained IDH research model."""
import hashlib
import json
import numpy as np

PROTOCOL = {
    'id': 'waw_selected20_minmax_v1',
    'input_scaling': 'whole-volume minmax to [0,1], float64; verified on five reference cases',
    'scaling_evidence': 'inferred from published statistics, not explicitly documented by publisher',
    'regions': ['1', '2', '3'],
    'sequences': ['t1c', 't1n', 't2w', 't2f'],
    'radiomics_settings': {'binWidth': .02, 'normalize': False, 'resampledPixelSpacing': None,
                          'distances': [1], 'force2D': False, 'minimumROIDimensions': 2,
                          'additionalInfo': False},
    'image_type': 'Original',
    'empty_regions': 'null selected features; fitted training imputer handles absent regions',
    'feature_scope': 'only selected model features; unused features filled with NaN before fixed independent preprocessing',
}


def selected_features(bundle):
    names = [f'{label}:{name}' for label in ('1', '2', '3') for name in bundle['feature_names']]
    selected = bundle['models']['reference_mask_radiomics'].named_steps['selectkbest'].get_support(indices=True)
    return [names[i] for i in selected]


def contract_hash(bundle):
    payload = {'protocol': PROTOCOL, 'selected_features': selected_features(bundle)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def feature_matrix(bundle, features):
    expected = selected_features(bundle)
    if set(features) != set(expected):
        raise ValueError('Extracted features differ from the selected model contract')
    result = np.full((1, len(bundle['feature_names']) * 3), np.nan)
    names = [f'{label}:{name}' for label in ('1', '2', '3') for name in bundle['feature_names']]
    for key, value in features.items():
        if value is not None:
            value = float(value)
            if not np.isfinite(value):
                raise ValueError('Nonfinite extracted feature')
            result[0, names.index(key)] = value
    return result
