import math

METERS_PER_DEGREE_LATITUDE = 111000

def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in meters."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def round_coord(point, precision=5):
    """Round coordinates to a consistent precision."""
    return round(point[0], precision), round(point[1], precision)
