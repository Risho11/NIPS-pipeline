"""Lossless numeric property context for experimental proposal prompts."""

import json
import math


PROPERTY_CONTEXT_NOTE = (
    'Numeric property measurements below take precedence over narrative reports. '
    'Null means unknown, not zero. SD is intra-sample standard deviation, not '
    'uncertainty across independent synthesis repeats. Modulus, yield strength and '
    'compression slopes are in bar; thickness is in micrometers; pore fraction, '
    'strains and CV are dimensionless; temperatures are in degrees C and humidity '
    'is in percent. Pore fraction is a compression-curve changepoint estimate, '
    'not independent porosimetry.'
)


def format_property_measurements(row, property_names=None):
    """Include every available Mean/SD column, preserving missing values as null.

    An optional property list lets the processing schema select fields explicitly;
    history routing defaults to all aggregate fields, including older CSV schemas.
    """
    allowed = None if property_names is None else set(property_names)
    measurements = {}
    for column, value in row.items():
        suffix = next((suffix for suffix in (' Mean', ' SD') if column.endswith(suffix)), None)
        if suffix is None or (allowed is not None and column[:-len(suffix)] not in allowed):
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = None
        measurements[column] = numeric if numeric is not None and math.isfinite(numeric) else None
    return json.dumps(measurements, allow_nan=False) if measurements else ''


PARAMETER_FIELDS = (
    'mixing_temp', 'bath_temp', 'pullcast_speed', 'nitrogen',
    'coupon_to_bath_wait_time', 'nips_bath_wait_time', 'polymer_wt', 'additive_wt',
    'polymer_type', 'solvent_type', 'cosolvent_type', 'nips_bath_solvent',
    'nips_bath_solvent_wt_percent',
)


def _value(value):
    """Convert CSV scalars to JSON-safe values without guessing missing context."""
    if value is None:
        return None
    if hasattr(value, 'item'):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, str):
        return value.strip() or None
    return value


def build_performance_observations(history):
    """One JSON schema for live and warm-start rows; never mutate stored reports.

    Numeric CSV fields are authoritative. Report-only legacy rows retain a labeled
    fallback so historical measurements are not silently lost during migration.
    Vision quality reports remain in the existing separate quality channel.
    """
    observations = []
    for _, row in history.iterrows():
        measurements = json.loads(format_property_measurements(row) or '{}')
        parameters = {key: _value(row.get(key)) for key in PARAMETER_FIELDS}
        # Older report-only exports may have parameters only in this explicit field.
        formatted = row.get('formatted_parameters')
        if isinstance(formatted, str):
            for part in formatted.split(';'):
                key, separator, value = part.strip().partition('=')
                if separator and key in parameters and parameters[key] is None:
                    value = value.split(' [', 1)[0].strip()
                    try:
                        parsed = json.loads(value.lower() if value.lower() in {'true', 'false'} else value)
                    except (ValueError, TypeError):
                        parsed = value
                    parameters[key] = _value(parsed)
        if isinstance(parameters['nitrogen'], str):
            state = parameters['nitrogen'].lower()
            if state in {'true', '1', 'on', 'yes'}:
                parameters['nitrogen'] = True
            elif state in {'false', '0', 'off', 'no'}:
                parameters['nitrogen'] = False
        observation = {
            'identity': {
                'condition': _value(row.get('name')),
                'source': _value(row.get('_observation_source')) or 'unknown',
                'campaign': _value(row.get('campaign')),
                'sample_time': _value(row.get('sample_time')),
                'processed_time': _value(row.get('processed_time')) or _value(row.get('date')),
                'time_source': _value(row.get('time_source')),
                'source_csv': _value(row.get('source_csv')),
                'source_name': _value(row.get('source_name')),
                'chemistry': _value(row.get('chemistry')),
            },
            'conditions': parameters,
            'measurements': measurements,
            'quality_notes': {
                'discarded_fit_reasons': _value(row.get('Discarded Fit Reasons')),
                'validation_status': _value(row.get('validation_status')),
                'pore_fraction_method': _value(row.get('pore_fraction_method')) or
                    'compression-curve changepoint estimate; not independent porosimetry',
            },
            'legacy_report': None,
            'legacy_pore_fraction_report': None,
        }
        # Only use narrative measurements when the numeric representation is absent.
        if not any(value is not None for value in measurements.values()):
            observation['legacy_report'] = _value(row.get('final_report'))
        if measurements.get('Pore Fraction Mean') is None:
            observation['legacy_pore_fraction_report'] = _value(row.get('pore_fraction_report'))
        observations.append(observation)
    return json.dumps({
        'schema': 'experimental_observations_v1',
        'measurement_conventions': PROPERTY_CONTEXT_NOTE,
        'observations': observations,
    }, allow_nan=False)
