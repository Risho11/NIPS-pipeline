"""Persistent volume accounting for OT-2 stock bottles."""
import json
import os
import tempfile


class BottleInventory:
    """Track usable bottle volumes in uL and persist them after every deduction."""

    def __init__(self, path, initial_volumes_uL, dead_volumes_uL=None):
        self.path = os.path.abspath(path)
        self.initial_volumes_uL = self._validate_map(initial_volumes_uL, "initial")
        self.dead_volumes_uL = self._validate_map(
            dead_volumes_uL or {name: 0.0 for name in self.initial_volumes_uL}, "dead")
        if set(self.initial_volumes_uL) != set(self.dead_volumes_uL):
            raise ValueError("Initial-volume and dead-volume bottle names must match.")
        self.remaining_uL = self._load_or_initialize()

    @staticmethod
    def _validate_map(values, label):
        validated = {}
        for name, value in values.items():
            value = float(value)
            if value < 0:
                raise ValueError("{} volume for {} cannot be negative.".format(label, name))
            validated[str(name)] = value
        return validated

    def _load_or_initialize(self):
        if not os.path.exists(self.path):
            remaining = dict(self.initial_volumes_uL)
            self._save(remaining)
            return remaining
        with open(self.path, "r") as inventory_file:
            payload = json.load(inventory_file)
        remaining = self._validate_map(payload["remaining_uL"], "remaining")
        missing = set(self.initial_volumes_uL) - set(remaining)
        extra = set(remaining) - set(self.initial_volumes_uL)
        if missing or extra:
            raise ValueError("Inventory bottle names do not match configuration; missing={}, extra={}."
                             .format(sorted(missing), sorted(extra)))
        return remaining

    def _save(self, remaining=None):
        remaining = self.remaining_uL if remaining is None else remaining
        directory = os.path.dirname(self.path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        payload = {
            "remaining_uL": remaining,
            "dead_volumes_uL": self.dead_volumes_uL,
        }
        descriptor, temporary_path = tempfile.mkstemp(prefix="bottle_inventory_", suffix=".json",
                                                       dir=directory or None)
        try:
            with os.fdopen(descriptor, "w") as inventory_file:
                json.dump(payload, inventory_file, indent=2, sort_keys=True)
                inventory_file.write("\n")
            os.replace(temporary_path, self.path)
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)

    def available_uL(self, bottle):
        self._require_bottle(bottle)
        return max(0.0, self.remaining_uL[bottle] - self.dead_volumes_uL[bottle])

    def require(self, requested_uL):
        """Raise before a run if any requested amount exceeds aspiratable volume."""
        shortages = []
        for bottle, requested in requested_uL.items():
            self._require_bottle(bottle)
            requested = float(requested)
            if requested < 0:
                raise ValueError("Requested volume cannot be negative.")
            available = self.available_uL(bottle)
            if requested > available + 1e-6:
                shortages.append("{} needs {:.2f} uL but only {:.2f} uL is usable"
                                 .format(bottle, requested, available))
        if shortages:
            raise RuntimeError("Insufficient bottle inventory: " + "; ".join(shortages))

    def consume(self, bottle, volume_uL):
        """Deduct and persist a transfer after it completes successfully."""
        self.require({bottle: volume_uL})
        self.remaining_uL[bottle] -= float(volume_uL)
        self._save()

    def set_remaining(self, bottle, volume_uL):
        """Reconcile a bottle after refilling, replacement, or manual measurement."""
        self._require_bottle(bottle)
        volume_uL = float(volume_uL)
        if volume_uL < 0:
            raise ValueError("Remaining volume cannot be negative.")
        self.remaining_uL[bottle] = volume_uL
        self._save()

    def snapshot(self):
        return {
            name: {
                "remaining_uL": self.remaining_uL[name],
                "dead_volume_uL": self.dead_volumes_uL[name],
                "available_uL": self.available_uL(name),
            }
            for name in self.remaining_uL
        }

    def _require_bottle(self, bottle):
        if bottle not in self.remaining_uL:
            raise KeyError("Unknown inventory bottle: {}".format(bottle))
