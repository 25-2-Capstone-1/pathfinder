from app.utils import haversine


def calculate_path_details(path):
    """Calculates total distance and segments for a given path."""
    total_distance = 0
    waypoints = []
    for i in range(len(path) - 1):
        p1, p2 = path[i], path[i + 1]
        dist = haversine(p1[0], p1[1], p2[0], p2[1])
        total_distance += dist
        waypoints.append({'from': p1, 'to': p2, 'distance': dist})
    return total_distance, waypoints

"""**kwargs는 파이썬 함수에서 임의의 키워드 인자(이름이 있는 인자)를 딕셔너리 형태로 받아오는 문법입니다.
예를 들어, def func(**kwargs):로 정의하면, func(a=1, b=2)처럼 호출할 때 kwargs는 {'a': 1, 'b': 2}가 됩니다.
이렇게 하면 함수에 전달할 인자의 개수나 이름을 유동적으로 처리할"""

def build_course_response(strategy, path, target_distance, course_number, **kwargs):
    # path가 비어있거나 유효하지 않은 경우 예외 처리
    if not path or len(path) < 2:
        return None
    my_lng, my_lat = path[0][0], path[0][1]
    start_lng, start_lat = path[1][0], path[1][1]
    end_lng, end_lat = path[-1][0], path[-1][1]


    total_distance, segments = calculate_path_details(path)
    waypoints = []
    for i in range(2, len(path) - 1): # 시작점(1)과 끝점(-1) 사이의 경로만 waypoints로 넣을 경우 index 2부터 시작
        p_lng, p_lat = path[i][0], path[i][1] # [lng, lat] 순서 유지
        waypoints.append({'lat': p_lat, 'lng': p_lng})


    estimated_time = int((total_distance / 10) * 60)  # 분 단위 (속도 10km/h 가정)

    if total_distance < 3000:
        difficulty = 'easy'
    elif total_distance < 5000:
        difficulty = 'medium'
    else:
        difficulty = 'hard'

    # 5. Response 딕셔너리 생성
    response = {
        "myPoint_lat": my_lat,
        "myPoint_lng": my_lng,
        "course": [
            {
                "description": f"서울 도심을 따라 테스트 코스{total_distance:.1f}m 입니다",
                "difficulty": difficulty,
                "distance": round(total_distance, 1),
                "endPoint": {
                    "lat": end_lat,
                    "lng": end_lng
                },
                "estimatedTime": estimated_time,
                "routeId": f"route_{course_number}",
                "routeName": f"서울 러닝 코스 {course_number}",
                "startPoint": {
                    "lat": start_lat,
                    "lng": start_lng
                },
                "waypoints": waypoints
            }
        ]
    }

    return response




