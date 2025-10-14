import math
from app_service.utils import haversine

def calculate_path_details(path):
    """Calculates total distance and segments for a given path."""
    total_distance = 0
    segments = []
    for i in range(len(path) - 1):
        p1, p2 = path[i], path[i+1]
        dist = haversine(p1[0], p1[1], p2[0], p2[1])
        total_distance += dist
        segments.append({'from': p1, 'to': p2, 'distance': dist})
    return total_distance, segments

def build_course_response(strategy, path, total_distance, target_distance, waypoints, **kwargs):
    """Builds the standard success dictionary for a generated course."""
    deviation = abs(total_distance - target_distance)
    deviation_percent = (deviation / target_distance) * 100 if target_distance > 0 else 0
    _, segments = calculate_path_details(path)

    response = {
        'success': True,
        'strategy': strategy,
        'path': path,
        'total_distance': total_distance,
        'target_distance': target_distance,
        'deviation': deviation,
        'deviation_percent': deviation_percent,
        'waypoints': waypoints,
        'segments': segments,
    }
    response.update(kwargs)
    return response
