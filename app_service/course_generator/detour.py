import math
import logging

from flask import json

from app_service.utils import haversine, round_coord
from app_service.course_generator.response_creator import build_course_response, calculate_path_details


#기본적인 동작은 loop와 같음->loop 참고
#삼각형과 비슷한 코스 생성될 예정(시작 -> 중간점 -> 끝)
def generate_detour_course(start, end, target_distance, tolerance):
    logging.info("Attempting to generate a 'detour' course.")

    direct_dist = haversine(start[0], start[1], end[0], end[1])
    extra_needed = target_distance - direct_dist
    mid_lat, mid_lng = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
    delta_lat, delta_lng = end[0] - start[0], end[1] - start[1]
    
    path_length = math.sqrt(delta_lat**2 + delta_lng**2)

    #10m 이내의 거리일 경우 loop로 넘어감
    if direct_dist < 10:
        return {'success': False, 'error': 'Detour strategy requires different start and end points.', 'suggestion': "Try the 'loop' strategy."}

    offset_dist_meters = extra_needed / 2
    total_dist = 0

    METERS_PER_DEGREE_LATITUDE = 111000
    #거리가 너무 차이가 날 경우, 오차 범위를 벗어남
    #억지로 offset과의 거리를 조절하여 적절한 값이 있는지 확인
    route_number = 0 # 생성된 루트가 몇 번 째 것이 몇 번 째 코스인지 표시
    response_array = []

    for multiplier in [1.0, 0.75, 1.25, 0.5, 1.5]:
        adjusted_offset_dist = offset_dist_meters * multiplier
        offset_lat_degrees = adjusted_offset_dist / METERS_PER_DEGREE_LATITUDE
        meters_per_degree_lng = METERS_PER_DEGREE_LATITUDE * math.cos(math.radians(mid_lat))
        offset_lng_degrees = adjusted_offset_dist / meters_per_degree_lng if meters_per_degree_lng > 0 else 0


        #시작 -> 끝으로 가는 중간 지점(multiplier로 비율이 정해짐. 항상 정 중앙은 아님)
        # 중간 지점에서 법선을 그어서 offset 거리 만큼의 지점으로 이동 할 수 있도록 해줌
        perp_dir_len = math.sqrt(delta_lng**2 + delta_lat**2)
        wp_lat = mid_lat - (delta_lng / perp_dir_len) * offset_lat_degrees
        wp_lng = mid_lng + (delta_lat / perp_dir_len) * offset_lng_degrees

        #여기서는 waypoint가 하나만 생성됨
        waypoint = round_coord((wp_lat, wp_lng))
        path = [start, waypoint, end]
        total_dist, segment = calculate_path_details(path)

        logging.info(f"Rout Number {route_number} -> Trying waypoint {waypoint} -> Total distance: {total_dist:.0f}m")

        if target_distance * (1 - tolerance) <= total_dist <= target_distance * (1 + tolerance):
            logging.info(f"Found suitable detour course with waypoint {waypoint}.")
            # json형식 배열로 정리 해 두기
            response_array.append(build_course_response('detour', path, target_distance, route_number ))
            route_number += 1
            #return build_course_response('detour', path, total_dist, target_distance, [waypoint])

    if response_array:
        return {
            'success': True,
            'course': response_array}
    else:
        logging.info("Could not find a suitable detour course within tolerance.")
        return {'success': False, 'error': 'Could not generate a detour course within the specified tolerance.'}
