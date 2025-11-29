
# python
import math
import logging
from app.utils import haversine, round_coord, MAX_ROUTE_ID, MAX_WAYPOINTS_PER_ROUTE
from app.course_generator.response_creator import build_course_response, calculate_path_details

METERS_PER_DEGREE_LATITUDE = 111000  # 약 11.1km

def _meters_per_degree_lng_at(lat):
    cosv = math.cos(math.radians(lat))
    return METERS_PER_DEGREE_LATITUDE * (cosv if abs(cosv) > 1e-6 else 1e-6)

def generate_loop_waypoints(center, radius, num_waypoints, routeId):
    waypoints = []
    if radius <= 0 or num_waypoints <= 0:
        return waypoints

    center_lat, center_lng = center
    meters_per_degree_lng = _meters_per_degree_lng_at(center_lat)

    start_angle = (2 * math.pi * routeId) / MAX_ROUTE_ID
    for i in range(num_waypoints):
        angle = start_angle + (2 * math.pi * i) / num_waypoints
        delta_lat = radius * math.cos(angle) / METERS_PER_DEGREE_LATITUDE
        delta_lng = radius * math.sin(angle) / meters_per_degree_lng
        wp_lat, wp_lng = center_lat + delta_lat, center_lng + delta_lng
        waypoints.append(round_coord((wp_lat, wp_lng)))

    return waypoints

def _compute_loop_center_for_segment(start, end, radius, routeId):
    # start, end: (lat, lng)
    start_lat, start_lng = start
    end_lat, end_lng = end

    mid_lat = (start_lat + end_lat) / 2.0
    mid_lng = (start_lng + end_lng) / 2.0

    meters_per_degree_lng = _meters_per_degree_lng_at((start_lat + end_lat) / 2.0)

    # vector from start to end in meters (x: lng meters, y: lat meters)
    dx = (end_lng - start_lng) * meters_per_degree_lng
    dy = (end_lat - start_lat) * METERS_PER_DEGREE_LATITUDE

    # perpendicular vector
    perp_x, perp_y = -dy, dx
    length = math.hypot(perp_x, perp_y)
    if length < 1e-6:
        # fallback: arbitrary perpendicular (east)
        perp_x, perp_y = 1.0, 0.0
        length = 1.0

    # choose side to offset based on routeId to generate different routes
    side = 1 if (routeId % 2 == 0) else -1
    # increase offset slightly for higher routeId groups to diversify
    multiplier = 1 + (routeId // 2) * 0.3
    shift_x_m = perp_x / length * radius * side * multiplier
    shift_y_m = perp_y / length * radius * side * multiplier

    shift_lat = shift_y_m / METERS_PER_DEGREE_LATITUDE
    shift_lng = shift_x_m / meters_per_degree_lng

    center_lat = mid_lat + shift_lat
    center_lng = mid_lng + shift_lng
    return (center_lat, center_lng)

def generate_loop_course(my, start, end, target_distance, tolerance):
    logging.info("Attempting to generate a 'loop' course.")

    direct_dist = haversine(start[0], start[1], end[0], end[1])
    is_start_end_same = direct_dist < 10.0

    extra_needed = target_distance - direct_dist if not is_start_end_same else target_distance

    # 최소/최대 반지름 상수 (early 사용을 위해 여기서 정의)
    MIN_RADIUS = 20.0
    MAX_RADIUS = 5000.0

    # extra_needed가 거의 0이거나 음수라도 최소 루프를 생성하도록 강제
    if extra_needed <= 1.0:
        logging.info("extra_needed is very small or negative; forcing minimal loop radius.")
        extra_needed = 2 * math.pi * MIN_RADIUS

    # desired circumference is extra_needed (approx)
    loop_radius = extra_needed / (2 * math.pi)

    # clamp radius to reasonable bounds
    loop_radius = max(MIN_RADIUS, min(MAX_RADIUS, loop_radius))

    response_array = []
    # 트라이한 후보 중 목표에 가장 근접한 것 저장
    best_diff = float('inf')
    best_response = None

    # desired waypoint spacing (meters) to decide number of waypoints
    DESIRED_SPACING = 150.0
    circumference = 2 * math.pi * loop_radius
    suggested_wp = max(4, min(MAX_WAYPOINTS_PER_ROUTE, int(circumference / DESIRED_SPACING)))
    if suggested_wp <= 0:
        suggested_wp = min(MAX_WAYPOINTS_PER_ROUTE, 8)

    for i in range(MAX_ROUTE_ID):
        routeId = i
        # compute center: if start==end, center is start; else offset midpoint perpendicular
        if is_start_end_same:
            center_point = start
        else:
            center_point = _compute_loop_center_for_segment(start, end, loop_radius, routeId)

        waypoints = generate_loop_waypoints(center_point, loop_radius, suggested_wp, routeId)

        path = [my, start] + waypoints
        if is_start_end_same:
            path.append(start)
        else:
            path.append(end)

        total_dist, needless = calculate_path_details(path)
        logging.info(f"Trying loop route {routeId}: {len(waypoints)} waypoints, radius {loop_radius:.0f}m, dist {total_dist:.0f}m")

        # 후보 기록 (목표와의 차이 기준)
        diff = abs(total_dist - target_distance)
        candidate_response = build_course_response('loop', path, target_distance, routeId)
        if candidate_response:
            if diff < best_diff:
                best_diff = diff
                best_response = candidate_response

            if target_distance * (1 - tolerance) <= total_dist <= target_distance * (1 + tolerance):
                logging.info(f"Found suitable loop course with route ID {routeId}.")
                response_array.append(candidate_response)

    if response_array:
        return {'success': True, 'course': response_array}
    elif best_response:
        logging.info("No route within tolerance; returning best available candidate anyway.")
        return {'success': True, 'course': [best_response]}
    else:
        logging.info("Could not generate any loop candidate.")
        return {'success': False, 'error': 'Could not generate a loop course.'}