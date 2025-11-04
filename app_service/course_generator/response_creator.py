import math
from app_service.utils import haversine


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

    # path_array가 여러 경로를 담고 있다면 첫 번째 경로 사용
    # 또는 모든 경로를 반환하려면 리스트로 반환
    if not path:
        return None #추가적인 에외 처리 해야
    start_lng, start_lat, end_lng, end_lat = path[0][0], path[0][1], path[-1][0], path[-1][1]
    waypoints = []
    # 경로 상세 정보 계산

    total_distance, segments = calculate_path_details(path)

    for i in range(1, len(path)-1):
        p_lat, p_lng = path[i][0], path[i][1]
        waypoints.append({'from': p_lat, 'to': p_lng})
    # waypoints 형식 변환 (lat, lng 딕셔너리로)

    # 예상 시간 계산 (분 단위, 평균 속도 10km/h)
    estimated_time = int((total_distance / 10) * 60)  # 분 단위

    # 난이도 결정 추가적인 요소 반영해야
    #일단 길이 기반으로 설정했지만, 더 바뀔 수 있음
    if total_distance < 3000:
        difficulty = 'easy'
    elif total_distance < 5000:
        difficulty = 'medium'
    else:
        difficulty = 'hard'

    response = {
        'routeId': f'route_{str(course_number)}',#route1, rout2... 이건 번호 어떻게 지정 할 것인가 따라 다름
        'routeName': f'서울 러닝 코스 {str(course_number)}', #임의의 숫자 부여
        'startPoint': {
            'lat': start_lat,
            'lng': start_lng
        },
        'endPoint': {
            'lat': end_lat,
            'lng': end_lng
        },
        'waypoints': waypoints,
        'distance': round(total_distance, 1),
        'estimatedTime': estimated_time,
        'difficulty': difficulty,
        'description': f'서울 도심을 따라 테스트 코스{total_distance}km 입니다'
        #'description': kwargs.get('description', f'약 {round(total_distance / 1000, 1)}km 코스입니다.')
    }

    return response





