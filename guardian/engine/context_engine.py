"""Context engine managing spatial zones, room calibrations, and environmental context."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class ZoneType(str, Enum):
    """Semantic zone classifications."""
    BED = "BED"
    SOFA = "SOFA"
    SAFE = "SAFE"
    RESTRICTED = "RESTRICTED"
    EXIT_DOOR = "EXIT_DOOR"
    STAIRS = "STAIRS"
    FLOOR = "FLOOR"


@dataclass
class ZoneDefinition:
    """Normalized spatial bounding zone or polygon [0.0 - 1.0]."""
    name: str
    zone_type: ZoneType
    # Bounding box [ymin, xmin, ymax, xmax] in normalized coordinates
    bounds: Tuple[float, float, float, float]
    description: str = ""

    def contains_point(self, x: float, y: float) -> bool:
        """Check if normalized point (x, y) falls inside bounding box."""
        ymin, xmin, ymax, xmax = self.bounds
        return xmin <= x <= xmax and ymin <= y <= ymax


@dataclass
class RoomCalibration:
    """Room layout and environmental calibration."""
    room_id: str
    room_type: str = "GENERAL"  # "BEDROOM", "LIVING_ROOM", "BATHROOM", "CORRIDOR"
    floor_level_y: float = 0.85  # Normalized y coordinate representing floor plane
    zones: Dict[str, ZoneDefinition] = field(default_factory=dict)
    night_start_hour: int = 22
    night_end_hour: int = 6

    def add_zone(self, zone: ZoneDefinition) -> None:
        """Register a zone."""
        self.zones[zone.name] = zone

    def get_zone_at_point(self, x: float, y: float) -> Optional[ZoneDefinition]:
        """Find matching zone for coordinate."""
        for zone in self.zones.values():
            if zone.contains_point(x, y):
                return zone
        return None

    def calculate_floor_proximity(self, foot_y: float) -> float:
        """Compute normalized distance to floor plane [0.0 = on floor, 1.0 = far above floor]."""
        diff = abs(self.floor_level_y - foot_y)
        return min(1.0, max(0.0, diff))
