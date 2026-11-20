"""Named compression locations; no hardware imports or coordinate changes."""

LEGACY_LOCATIONS = ('coupon test 1', 'coupon test 2', 'coupon test 3', 'coupon test 4')
# Operator-confirmed bottom pair (November 17); no coordinates changed.
BOTTOM_LOCATIONS = ('coupon test 1', 'coupon test 3')
OPPOSITE_LOCATIONS = ('coupon test 2', 'coupon test 4')
# Preserve capability order and support for the historically used pair.
ROW_PAIRS = (OPPOSITE_LOCATIONS, BOTTOM_LOCATIONS)
CAPABILITIES = {'compression_plan_version': 1, 'compression_row_pairs': [list(row) for row in ROW_PAIRS]}


def resolve_test_locations(locations=None):
    if locations is None:
        return LEGACY_LOCATIONS
    if not isinstance(locations, (list, tuple)) or tuple(locations) not in ROW_PAIRS:
        raise ValueError('compression_test_locations must be coupon test 2, coupon test 4 or coupon test 1, coupon test 3')
    return tuple(locations)
