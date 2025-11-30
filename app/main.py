import logging
import os
import sys

from flask import Flask, jsonify, request

# 프로젝트 루트 설정
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 기존 Import 유지
from app.utils import haversine, round_coord
from app.findIsochrone import get_distances_batch
from app.course_generator.detour import generate_detour_course
from app.course_generator.loop import generate_loop_course
from app.ors.routefinder import start2end, my2start

app = Flask(__name__)


# --- 1. Helper Functions ---

def calculate_path_details(path):
    """경로의 총 거리와 구간별 거리를 계산합니다."""
    total_dist = 0
    segments = []
    if not path or len(path) < 2:
        return 0, []

    for i in range(len(path) - 1):
        # ✅ FIXED: path는 [lat, lng] 순서로 가정
        p1_lat, p1_lng = path[i][0], path[i][1]
        p2_lat, p2_lng = path[i + 1][0], path[i + 1][1]
        dist = haversine(p1_lat, p1_lng, p2_lat, p2_lng)
        total_dist += dist
        segments.append(dist)
    return total_dist, segments


def build_course_response(strategy, path, target_distance, course_number, **kwargs):
    """경로 데이터를 받아 프론트엔드 요구사항에 맞는 JSON 구조로 변환합니다."""
    if not path or len(path) < 2:
        return None

    # ✅ FIXED: path는 [lat, lng] 순서로 가정
    my_lat, my_lng = path[0][0], path[0][1]
    start_lat, start_lng = path[1][0], path[1][1]
    end_lat, end_lng = path[-1][0], path[-1][1]

    # 경로 상세 정보 계산
    total_distance, segments = calculate_path_details(path)

    # Waypoints 구성
    waypoints = []
    for i in range(2, len(path) - 1):
        # ✅ FIXED: path는 [lat, lng] 순서로 가정
        p_lat, p_lng = path[i][0], path[i][1]
        waypoints.append({'lat': p_lat, 'lng': p_lng})

    # 예상 시간 및 난이도
    estimated_time = int((total_distance / 10) * 60)  # 분 단위

    if total_distance < 3000:
        difficulty = 'easy'
    elif total_distance < 5000:
        difficulty = 'medium'
    else:
        difficulty = 'hard'

    # 응답 딕셔너리 구성
    response = {
        "myPoint_lat": my_lat,
        "myPoint_lng": my_lng,
        "course": [
            {
                "description": f"생성된 러닝 코스 {total_distance:.1f}m 입니다",
                "difficulty": difficulty,
                "distance": round(total_distance, 1),
                "endPoint": {"lat": end_lat, "lng": end_lng},
                "estimatedTime": estimated_time,
                "routeId": f"route_{course_number}",
                "routeName": f"러닝 코스 {course_number}",
                "startPoint": {"lat": start_lat, "lng": start_lng},
                "waypoints": waypoints
            }
        ]
    }
    return response


# --- Core Functions ---

def parse_location(location):
    if isinstance(location, tuple) and len(location) == 2:
        return round_coord(location)
    if isinstance(location, dict):
        return round_coord((location.get('lat'), location.get('lng')))
    logging.warning(f"Geocoding for '{location}' is not implemented.")
    return None


def calculate_distance(use_google_api, point1, point2):
    if use_google_api:
        dist = get_distances_batch(point1, [point2]).get(point2)
        if dist is not None:
            return dist
    return haversine(point1[0], point1[1], point2[0], point2[1])


def verify_with_google(course, use_google_api):
    # course가 실패했거나 내용이 없으면 그대로 반환
    if not course or (isinstance(course, dict) and 'course' not in course):
        return course
    return course


def create_course(my, start, end, target_distance, use_google_api, tolerance=1.0, strategy='auto'):
    my_coord = parse_location(my)
    start_coord = parse_location(start)
    end_coord = parse_location(end)

    if not start_coord or not end_coord:
        return {'success': False, 'error': 'Could not parse start or end coordinates.'}

    direct_dist = calculate_distance(use_google_api, start_coord, end_coord)

    if target_distance < direct_dist * (1 - tolerance):
        return {
            'success': False,
            'error': f'Target distance ({target_distance}m) is shorter than direct distance.',
        }

    if strategy == 'auto':
        extra_ratio = (target_distance - direct_dist) / direct_dist if direct_dist > 0 else float('inf')
        strategy = 'detour' if extra_ratio < 0.5 else 'loop'

    course_generators = {
        'detour': generate_detour_course,
        'loop': generate_loop_course,
    }
    generator_func = course_generators.get(strategy)

    course_result = generator_func(my_coord, start_coord, end_coord, target_distance, tolerance)
    return verify_with_google(course_result, use_google_api)


# --- API Endpoints ---

@app.route('/routes/findway', methods=['POST'])
def find_ways():
    info_input = request.get_json()
    if not info_input:
        return jsonify({'success': False, 'error': 'No JSON data'}), 400

    try:
        # 1. 입력 파싱
        my_data = info_input.get('myPoint', {})
        start_data = info_input.get('startPoint', {})
        end_data = info_input.get('endPoint', {})

        if not (my_data and start_data and end_data):
            return jsonify({'success': False, 'error': 'Missing point data'}), 400

        my = (my_data['lat'], my_data['lng'])
        start = (start_data['lat'], start_data['lng'])
        end = (end_data['lat'], end_data['lng'])
        target_distance = (info_input.get('targetDistance'))*0.9  # 80%로 조정

        # 2. 코스 생성
        data = create_course(my, start, end, target_distance, use_google_api=False)

        # 3. 에러 체크
        if not data or (isinstance(data, dict) and 'error' in data):
            return jsonify(data if data else {'success': False, 'error': 'Course generation failed'}), 400

        direction_response = []

        # data 구조: { 'success': True, 'course': [ {build_course_response 결과}, ... ] }
        # build_course_response 결과: { "myPoint_lat":..., "course": [ {실제 코스} ] }
        if not data.get('course'):
            return jsonify({'success': False, 'error': 'No course data generated'}), 400

        for response_wrapper in data['course']:
            # response_wrapper: { "myPoint_lat":..., "course": [ {실제 코스 정보} ] }
            #각각의 요소를 탐색함
            if not response_wrapper.get('course'):
                continue

            #실제 응답의 첫 번째 요소-> 실제 코스
            actual_course_info = response_wrapper['course'][0]

            # 🔍 디버깅 로그
            logging.info(f"🔍 actual_course_info keys: {actual_course_info.keys()}")
            logging.info(f"🔍 startPoint: {actual_course_info.get('startPoint')}")

            #myPoint를 lat, lng 형태로 get으로 받았기 때문에 순서 반대로 lng, lat이 되도록 넣기
            my2start_route = my2start(my[1], my[0], actual_course_info)
            start2end_route = start2end(actual_course_info)
            if start2end_route and isinstance(start2end_route.get('distance'), (int, float)):
                try:
                    actual_course_info['distance'] = round(start2end_route['distance'], 1)
                except Exception as e:
                    logging.warning(f"Could not overwrite course distance: {e}")

            directions = {
                'my2start': my2start_route,
                'start2end': start2end_route,
                # 프론트엔드에서 렌더링할 코스 정보
                'course_info': actual_course_info
            }
            direction_response.append(directions)

        return jsonify({
            'success': True,
            'route': direction_response
        }), 200

    except KeyError as e:
        logging.error(f"KeyError in find_ways: {e}")
        return jsonify({'success': False, 'error': f'Missing required key: {str(e)}'}), 400
    except Exception as e:
        logging.error(f"Error in find_ways: {e}")
        # 디버깅을 위해 상세 에러 로깅
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)