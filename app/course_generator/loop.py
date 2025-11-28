import math
import logging
from app.utils import haversine, round_coord, MAX_ROUTE_ID, MAX_WAYPOINTS_PER_ROUTE
from app.course_generator.response_creator import build_course_response, calculate_path_details

#center: (lat, lng)를 중심으로 radius 미터 반경의 원형 경로를 생성
# waypoints 수에 따라 원형 경로의 점들을 생성
# 세부적인 조정에 따라서 num_waypoints 조절 할 수 있도록(프런트, CentralServer와 협력)
def generate_loop_waypoints(center, radius, num_waypoints, routeId):
    waypoints = []
    center_lat = center[0]
    center_lng = center[1]

    #위도당 미터 변환
    METERS_PER_DEGREE_LATITUDE = 111000 #11km
    #경도당 미터 변환(일단 이 정도로 구현)

    # 위도에 따른 경도 미터 변환 값 계산
    # 그냥 알려진 공식 사용한 것이니 mechanism 걱정 ㄴㄴ
    meters_per_degree_lng = METERS_PER_DEGREE_LATITUDE * math.cos(math.radians(center_lat))

    #num_waypoints도 거리 관계 없이 고정할 것인지 아니면 거리 비례로 할 것인지 결정 필요
    #경로를 여러 개 만들려면 angle의 시작 점을 다르게 해서 조정 필요
    #ex: 시작을 0, π/4, π/2, 3π/4 ... 등으로 조정
    start_angle = (2 * math.pi * routeId) / 5  # 5는 최대 경로 수에 따라 조정 필요

    for i in range(num_waypoints):
        angle = start_angle+(2 * math.pi * i) / num_waypoints #2π는 원 전체, i/num_waypoints는 분할된 각도->ex: 4등분이면 0, π/2, π, 3π/2
        delta_lat = radius * math.cos(angle) / METERS_PER_DEGREE_LATITUDE

        #wp_lat = r*cos(angle) -> 위도는 그냥 평면과 같이 계산해도 무방함

        #경도는 위도에 따라 미터당 경도 값이 달라지므로 보정 필요
        #sin값에 따라 음수가 나올 수 있으나, (-)미터는 원치 않으므로 0 이라는 그냥 0으로 처리
        delta_lng = radius * math.sin(angle) / meters_per_degree_lng if meters_per_degree_lng > 0 else 0
        #중심 값에서 위도, 경도를 추가해서 웨어포인트 하나 생성
        wp_lat, wp_lng = center_lat + delta_lat, center_lng + delta_lng

        waypoints.append(round_coord((wp_lat, wp_lng)))

    return waypoints

#num_waypoints = 10으로 일단 통일, 생성 루트 수는 3개로 제한
def generate_loop_course(my, start, end, target_distance, tolerance):
    logging.info("Attempting to generate a 'loop' course.")

    direct_dist = haversine(start[0], start[1], end[0], end[1])

    #만약 시작점과 끝 지점 사이의 거리가 10m 이내라면 시작과 끝이 동일한 코스라고 간주
    #이럴 경우 시작과 끝이 같은 원형으로 제작을 해야함
    is_start_end_same = direct_dist < 10

    #extra_needed: 직선 거리 외에도 추가로 더 만들어야 하는 거리
    extra_needed = target_distance - direct_dist if not is_start_end_same else target_distance
    #시작점을 기준으로 한 바퀴 돌며 원형으로 경로 생성하기
    center_point = start

    #1.1은 임의의 값
    loop_radius = (extra_needed / (2 * math.pi)) * 1.0 if extra_needed > 0 else 0

    #num_waypoints = max(4, min(8, int(loop_radius / 200)))
    #waypoint 수 도 조정을 해야함

    response_array = []
    for i in range(MAX_ROUTE_ID):
        routeId = i
        waypoints = generate_loop_waypoints(center_point, loop_radius, MAX_WAYPOINTS_PER_ROUTE, routeId)
        path = [my, start] + waypoints
        if is_start_end_same:
            path.append(start)
        else:
            path.append(end)
        total_dist, needless = calculate_path_details(path)

        logging.info(f"Trying loop route {routeId}: {MAX_WAYPOINTS_PER_ROUTE} waypoints, radius {loop_radius:.0f}m, dist {total_dist:.0f}m")
        if target_distance * (1 - tolerance) <= total_dist <= target_distance * (1 + tolerance):
            logging.info(f"Found suitable loop course with route ID {routeId}.")
            response_array.append(build_course_response('loop', path, target_distance, routeId))

    if response_array:
        return {
            'success': True,
            'course': response_array}
    else:
        logging.info("Could not find a suitable loop course within tolerance.")
        return {'success': False, 'error': 'Could not generate a loop course within the specified tolerance.'}

