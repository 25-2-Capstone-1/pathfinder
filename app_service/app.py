import os
import sys

# Add the project root directory to the Python path to resolve import errors
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from flask import Flask, request, jsonify
import math
import logging
from dotenv import load_dotenv

# Local application imports
from utils import haversine, round_coord
from findIsochrone import get_distances_batch
from course_generator.detour import generate_detour_course
from course_generator.loop import generate_loop_course
#from course_generator.scenic import generate_scenic_course

# --- Setup ---
load_dotenv()
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Core Functions ---

def _parse_location(location):
    if isinstance(location, tuple) and len(location) == 2:
        return round_coord(location)
    logging.warning(f"Geocoding for '{location}' is not implemented.")
    return None

def _calculate_distance(use_google_api, point1, point2):
    if use_google_api:
        dist = get_distances_batch(point1, [point2]).get(point2)
        if dist is not None:
            return dist
    return haversine(point1[0], point1[1], point2[0], point2[1])

def _verify_with_google(course, use_google_api):
    if not course.get('success') or not use_google_api:
        return course
    
    logging.info("Verifying course with Google API.")
    path = course['path']
    total_verified_dist = 0
    for i in range(len(path) - 1):
        dist = _calculate_distance(use_google_api, path[i], path[i+1])
        if dist is not None:
            total_verified_dist += dist
    
    course['verified_distance'] = total_verified_dist
    logging.info(f"Verified distance: {total_verified_dist:.0f}m (Estimated: {course['total_distance']:.0f}m)")
    return course

def create_course(start, end, target_distance, use_google_api, tolerance=0.1, strategy='auto'):
    start_coord = _parse_location(start)
    end_coord = _parse_location(end)

    if not start_coord or not end_coord:
        return {'success': False, 'error': 'Could not parse start or end coordinates.'}

    logging.info(f"Generating course from {start_coord} to {end_coord} for {target_distance}m.")
    direct_dist = _calculate_distance(use_google_api, start_coord, end_coord)
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

    course_generators = {
        'detour': generate_detour_course,
        'loop': generate_loop_course,
        #'scenic': generate_scenic_course,
    }
    generator_func = course_generators.get(strategy)
    if not generator_func:
        return {'success': False, 'error': f'Unknown strategy: {strategy}'}

    course = generator_func(start_coord, end_coord, target_distance, tolerance)

    return _verify_with_google(course, use_google_api)

# --- API Endpoint ---

@app.route('/api/course', methods=['POST'])
def suggest_course_endpoint():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON payload.'}), 400

    required_fields = ['start', 'end', 'target_distance']
    if not all(field in data for field in required_fields):
        return jsonify({'success': False, 'error': 'Missing required fields (start, end, target_distance).'}), 400

    try:
        start_point = (data['start']['lat'], data['start']['lng'])
        end_point = (data['end']['lat'], data['end']['lng'])
        target_dist = int(data['target_distance'])
        
        if 'current_location' in data:
            current_loc = (data['current_location']['lat'], data['current_location']['lng'])
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)