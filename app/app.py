import os
# Add the project root directory to the Python path to resolve import errors
#project_root = os.path.abspath(os.path.dirname(__file__))

from flask import Flask, request, jsonify
import logging

# Local application imports
# 로컬과 도커에서의 import 과정에 따라 오류가 생길 수 있음
from .utils import haversine, round_coord #도커용. 로컬에서는 다르게
from .findIsochrone import get_distances_batch #도커용. 로컬에서는 다르게
from .course_generator.detour import generate_detour_course
from .course_generator.loop import generate_loop_course
from ors.routefinder import start2end, my2start, get_directions

app = Flask(__name__) #Dockerfile에 명시 해야 함
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Core Functions ---

def parse_location(location):
    if isinstance(location, tuple) and len(location) == 2:
        return round_coord(location)
    logging.warning(f"Geocoding for '{location}' is not implemented.")
    return None

def calculate_distance(use_google_api, point1, point2):
    if use_google_api:
        dist = get_distances_batch(point1, [point2]).get(point2)
        if dist is not None:
            return dist
    return haversine(point1[0], point1[1], point2[0], point2[1])

def verify_with_google(course, use_google_api):
    if not course.get('success') or not use_google_api:
        return course
    
    logging.info("Verifying course with Google API.")
    path = course['path']
    total_verified_dist = 0
    for i in range(len(path) - 1):
        dist = calculate_distance(use_google_api, path[i], path[i + 1])
        if dist is not None:
            total_verified_dist += dist
    
    course['verified_distance'] = total_verified_dist
    logging.info(f"Verified distance: {total_verified_dist:.0f}m (Estimated: {course['total_distance']:.0f}m)")
    return course

#어떤 전략 사용할 지 정하는 함수
def create_course(start, end, target_distance, use_google_api, tolerance=0.3, strategy='auto'):
    start_coord = parse_location(start)
    end_coord = parse_location(end)

    if not start_coord or not end_coord:
        return {'success': False, 'error': 'Could not parse start or end coordinates.'}

    logging.info(f"Generating course from {start_coord} to {end_coord} for {target_distance}m.")
    direct_dist = calculate_distance(use_google_api, start_coord, end_coord)
    logging.info(f"Direct haversine distance: {direct_dist:.0f}m.")

    if target_distance < direct_dist * (1 - tolerance):
        return {
            'success': False,
            'error': f'Target distance ({target_distance}m) is shorter than the direct distance ({direct_dist:.0f}m).',
            'suggestion': f'Please set the target distance to at least {direct_dist:.0f}m.',
            'direct_distance': direct_dist
        }

    if strategy == 'auto':
        extra_ratio = (target_distance - direct_dist) / direct_dist if direct_dist > 0 else float('inf')
        strategy = 'detour' if extra_ratio < 0.5 else 'loop'
    
    logging.info(f"Selected strategy: {strategy.upper()}")
    #전략을 다르게 짜기 위한 스크립트
    course_generators = {
        'detour': generate_detour_course,
        'loop': generate_loop_course,
        #'scenic': generate_scenic_course,
    }
    generator_func = course_generators.get(strategy)
    if not generator_func:
        return {'success': False, 'error': f'Unknown strategy: {strategy}'}

    course = generator_func(start_coord, end_coord, target_distance, tolerance)

    return verify_with_google(course, use_google_api)

# --- API Endpoint ---

@app.route('/api/route/recommend', methods=['POST'])
def suggest_course_endpoint():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON payload.'}), 400

    #required_fields = ['start', 'end', 'target_distance']
    required_fields = ['myPoint_lat', 'myPoint_long',
    'startPoint_lat', 'startPoint_long',
    'endPoint_lat', 'endPoint_long',
    'target_distance',
    'slope',
    'traffic_lights',
    'traffic_congestion']

    if not all(field in data for field in required_fields):
        missing_field = [field for field in required_fields if field not in data]
        return jsonify({'success': False, 'error': f'Missing required fields: {missing_field}'}), 400

    try:
        start_point = (data['startPoint_lat'], data['startPoint_long'])
        end_point = (data['endPoint_lat'], data['endPoint_long'])
        target_dist = int(data['target_distance'])
        
        if 'myPoint_lat' in data and 'myPoint_long' in data:
            current_loc = (data['myPoint_lat'], data['myPoint_long'])
            logging.info(f"Received current location (unused): {current_loc}")

    except (TypeError, KeyError, ValueError):
        return jsonify({'success': False, 'error': 'Invalid data format for start/end points or target_distance.'}), 400

    use_google = request.args.get('use_google', 'false').lower() == 'true'
    
    course_result = create_course(
        start=start_point,
        end=end_point,
        target_distance=target_dist,
        use_google_api=use_google
    )

    if not course_result.get('success'):
        return jsonify(course_result), 422

    return jsonify(course_result)
@app.route('/api/route/directions', methods=['POST'])
def get_directions_endpoint():
    data = request.get_json()

    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON payload.'}), 400

    # 필수 필드 확인
    required_fields = ['myPoint_lat', 'myPoint_lng', 'course']
    if not all(k in data for k in required_fields):
        missing = [k for k in required_fields if k not in data]
        return jsonify({'success': False, 'error': f'Missing required fields: {missing}'}), 400

    origin_lat = data['myPoint_lat']
    origin_lng = data['myPoint_lng']
    course_arr = data['course']   # multiple course list

    # ORS Directions Request ors/routefinder.py의 get_directions_array 함수 사용
    directions = get_directions(origin_lat, origin_lng, course_arr)

    if not directions:
        return jsonify({'success': False, 'error': 'Failed to retrieve directions from Graphhopper.'}), 500

    return jsonify({
        'success': True,
        'count': len(directions),
        'routes': directions
    }), 200

#mypoint -> startpoint // startpoint -> endpoint
@app.route('/routes/findway', methods=['POST'])
def find_ways():
    data = request.get_json()
    direction_response = []
    my_lng = data['myPoint_lng']
    my_lat = data['myPoint_lat']
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON payload.'}), 400

    for course in data['course']:
        logging.info(f"Course received: {course}")
    # ORS Directions Request ors/routefinder.py의 my2start 함수 사용
        #mys2start_route는 최상단 요소인 mypoint를 활용하므로 반드시 data 전체를 넘겨줘야 함
        my2start_route = my2start(my_lat, my_lng,course)
        logging.info(f"my2start route: {my2start_route}")

        start2end_route = start2end( course)
        logging.info(f"start2end route: {start2end_route}")

        directions = {'my2start': my2start_route, 'start2end': start2end_route}
        # 필수 필드 확인
        if not directions:
            return jsonify({'success': False, 'error': 'Failed to retrieve directions from Graphhopper.'}), 500
        direction_response.append(directions)

    return jsonify({
        'success': True,
        'route': direction_response  # 첫 번째 경로 반환
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)