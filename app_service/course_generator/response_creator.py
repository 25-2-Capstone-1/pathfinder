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
"""**kwargs는 파이썬 함수에서 임의의 키워드 인자(이름이 있는 인자)를 딕셔너리 형태로 받아오는 문법입니다.
예를 들어, def func(**kwargs):로 정의하면, func(a=1, b=2)처럼 호출할 때 kwargs는 {'a': 1, 'b': 2}가 됩니다.
이렇게 하면 함수에 전달할 인자의 개수나 이름을 유동적으로 처리할"""

def build_course_response(strategy, path, total_distance, target_distance, waypoints, **kwargs):
    """응답용 json 생성"""
    deviation = abs(total_distance - target_distance)
    if target_distance > 0:
        deviation_percent = (deviation / target_distance) * 100
    else:
        deviation_percent = 0
    total_distance, segments = calculate_path_details(path)

    response = {
        'success': True,
        #'strategy': strategy,
        'coordinate': path, #경로 전체 좌표 /기존에는 'path': path
        'total_distance': total_distance,
        #'target_distance': target_distance,
        #'deviation': deviation,
        #'deviation_percent': deviation_percent,
        #'waypoints': waypoints,
        #'segments': segments,
    }
    #api 통일성을 위해 일단 kwargs 차단
    #response.update(kwargs)
    return response
