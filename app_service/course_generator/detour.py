import math
import logging
from app_service.utils import haversine, round_coord, METERS_PER_DEGREE_LATITUDE
from app_service.course_generator.base import build_course_response, calculate_path_details

def generate_detour_course(start, end, target_distance, tolerance):
    logging.info("Attempting to generate a 'detour' course.")
    direct_dist = haversine(start[0], start[1], end[0], end[1])
    extra_needed = target_distance - direct_dist
    mid_lat, mid_lng = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
    delta_lat, delta_lng = end[0] - start[0], end[1] - start[1]
    
    path_length = math.sqrt(delta_lat**2 + delta_lng**2)
    if path_length == 0:
        return {'success': False, 'error': 'Detour strategy requires different start and end points.', 'suggestion': "Try the 'loop' strategy."}

    offset_dist_meters = extra_needed / 2
    total_dist = 0

    for multiplier in [1.0, 0.7, 1.3, 0.5, 1.5]:
        adjusted_offset_dist = offset_dist_meters * multiplier
        offset_lat_degrees = adjusted_offset_dist / METERS_PER_DEGREE_LATITUDE
        meters_per_degree_lng = METERS_PER_DEGREE_LATITUDE * math.cos(math.radians(mid_lat))
        offset_lng_degrees = adjusted_offset_dist / meters_per_degree_lng if meters_per_degree_lng > 0 else 0
        
        perp_dir_len = math.sqrt(delta_lng**2 + delta_lat**2)
        wp_lat = mid_lat - (delta_lng / perp_dir_len) * offset_lat_degrees
        wp_lng = mid_lng + (delta_lat / perp_dir_len) * offset_lng_degrees
        
        waypoint = round_coord((wp_lat, wp_lng))
        path = [start, waypoint, end]
        total_dist, _ = calculate_path_details(path)

        logging.info(f"Trying waypoint {waypoint} -> Total distance: {total_dist:.0f}m")
        if target_distance * (1 - tolerance) <= total_dist <= target_distance * (1 + tolerance):
            logging.info(f"Found suitable detour course with waypoint {waypoint}.")
            return build_course_response('detour', path, total_dist, target_distance, [waypoint])

    return {'success': False, 'error': f'Failed to meet target distance. Best attempt: {total_dist:.0f}m.', 'suggestion': "Try 'loop' strategy or increase tolerance."}
