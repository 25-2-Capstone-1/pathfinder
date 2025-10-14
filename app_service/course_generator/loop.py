import math
import logging
from app_service.utils import haversine, round_coord, METERS_PER_DEGREE_LATITUDE
from app_service.course_generator.base import build_course_response, calculate_path_details

def generate_loop_waypoints(center, radius, num_waypoints):
    waypoints = []
    center_lat = center[0]
    meters_per_degree_lng = METERS_PER_DEGREE_LATITUDE * math.cos(math.radians(center_lat))
    for i in range(num_waypoints):
        angle = (2 * math.pi * i) / num_waypoints
        offset_lat = radius * math.cos(angle) / METERS_PER_DEGREE_LATITUDE
        offset_lng = radius * math.sin(angle) / meters_per_degree_lng if meters_per_degree_lng > 0 else 0
        wp_lat, wp_lng = center_lat + offset_lat, center[1] + offset_lng
        waypoints.append(round_coord((wp_lat, wp_lng)))
    return waypoints

def generate_loop_course(start, end, target_distance, tolerance):
    logging.info("Attempting to generate a 'loop' course.")
    direct_dist = haversine(start[0], start[1], end[0], end[1])
    is_pure_loop = direct_dist < 10
    extra_needed = target_distance - direct_dist if not is_pure_loop else target_distance
    center_point = start
    loop_radius = (extra_needed / (2 * math.pi)) * 1.1 if extra_needed > 0 else 0
    num_waypoints = max(4, min(8, int(loop_radius / 200)))

    waypoints = generate_loop_waypoints(center_point, loop_radius, num_waypoints)
    path = [start] + waypoints + ([start] if is_pure_loop else [end])
    total_dist, _ = calculate_path_details(path)
    
    logging.info(f"Initial loop: {num_waypoints} waypoints, radius {loop_radius:.0f}m, dist {total_dist:.0f}m")

    if not (target_distance * (1 - tolerance) <= total_dist <= target_distance * (1 + tolerance)) and total_dist > 0:
        adjustment_factor = target_distance / total_dist
        loop_radius *= adjustment_factor
        waypoints = generate_loop_waypoints(center_point, loop_radius, num_waypoints)
        path = [start] + waypoints + ([start] if is_pure_loop else [end])
        total_dist, _ = calculate_path_details(path)
        logging.info(f"Adjusted loop: radius {loop_radius:.0f}m, dist {total_dist:.0f}m")

    return build_course_response('loop', path, total_dist, target_distance, waypoints, loop_radius=loop_radius)
