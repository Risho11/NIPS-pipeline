"""Named compression locations; no hardware imports or coordinate changes."""

LEGACY_LOCATIONS = ('coupon test 1', 'coupon test 2', 'coupon test 3', 'coupon test 4')
BOTTOM_LOCATIONS = ('coupon test 2', 'coupon test 4')
# Casting starts at +X; coupon yaw changes -90 -> +91 degrees at testing.
# With a fixed probe, the start-side is reached by the larger coupon-pose X=170.
ROW_PAIRS = (BOTTOM_LOCATIONS,)
CAPABILITIES = {'compression_plan_version': 1, 'compression_row_pairs': [list(row) for row in ROW_PAIRS]}


def resolve_test_locations(locations=None):
    if locations is None:
        return LEGACY_LOCATIONS
    if not isinstance(locations, (list, tuple)) or tuple(locations) not in ROW_PAIRS:
        raise ValueError('compression_test_locations must be the casting-start pair: coupon test 2, coupon test 4')
    return tuple(locations)
