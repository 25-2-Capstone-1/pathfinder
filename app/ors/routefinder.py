from collections import OrderedDict
import requests
import os
import logging
from flask.cli import load_dotenv
#from app.utils import haversine #로컬에서는 절대 경로이든 상대 경로이든 알아서 수정을 해 주지만,
#도커에서는 상대 경로롤 인식해야 하기 떄문에 import 과정에서 도커에선 module not found error가 발생할 수 있음
from app.utils import haversine #도커 배포용

load_dotenv()
#GRAPHHOPPER_URL = "http://localhost:8989" #로컬 테스트용
GRAPHHOPPER_URL = os.getenv("GRAPHHOPPER_URL") #graphhopper 서버테스트/ 실배포
#GRAPHHOPPER_URL = os.getenv("GRAPHHOPPER_EC2_URL") #배포 전 도커 테스트용
VEHICLE = "car"
LOCALE = "ko"


def extract_coords_arr(course):
    # ✅ FIXED: [lng, lat] → [lat, lng]
    coords = [[course['startPoint']['lat'], course['startPoint']['lng']]]
    for wp in course['waypoints']:
        coords.append([wp['lat'], wp['lng']])
    coords.append([course['endPoint']['lat'], course['endPoint']['lng']])
    return coords


def calc_slope(points):
    """
    points: [[lng, lat, ele], ...]
    return: list of dict {distance, ele_diff, slope_percent}
    """

    slopes = []
    for i in range(len(points)-1):
        lng1, lat1, ele1 = points[i]
        lng2, lat2, ele2 = points[i+1]

        dist = haversine(lat1, lng1, lat2, lng2)
        ele_diff = ele2 - ele1
        slope = (ele_diff / dist * 100) if dist > 0 else 0

        slopes.append({
            "index": i,
            "distance_m": round(dist, 2),
            "ele_diff_m": round(ele_diff, 2),
            "slope_percent": round(slope, 2)
        })

    return slopes
#myPoint->startPoint
def my2start(my_lat, my_lng, course):
    logging.info("📡 Fetching GraphHopper directions for myPoint to startPoint...")


    # 2. 'course' 배열의 첫 번째 요소에서 'startPoint'를 가져옵니다.

    start_lng = course['startPoint']['lng']
    start_lat = course['startPoint']['lat']

    coords = [[my_lat, my_lng],
              [start_lat, start_lng]]  # [myPoint]에서 [startPoint]로 가는 경로

    payload = {
        "points": coords,
        "profile": VEHICLE,
        "locale": LOCALE,
        "instructions": True,
        "points_encoded": False,
        "elevation": True
    }

    response = requests.post(f"{GRAPHHOPPER_URL}/route", json=payload)
    try:
        response.raise_for_status()
        data = response.json()
        path = data['paths'][0]

        return OrderedDict([
            ("distance", round(path['distance'], 2)),
            ("instructions", path.get('instructions', [])),
            ("rawGraphhopper", data)
        ])

    except Exception as e:
        logging.error(f"❌ Error in myToStart: {e}")
        logging.error(f"GraphHopper response: {response.text}")
        return None
#my2start, start2end 통합하여 한번의 response로 반환하는 함수 불필요: 결국에는 내부적으로 두번 호출해야 하므로

#startPoint -> endPoint
def start2end(course):
    logging.info("📡 Fetching GraphHopper directions for startPoint to endPoint...")

    coords = extract_coords_arr(course)

    payload = {
        "points": coords,
        "profile": VEHICLE,
        "locale": LOCALE,
        "instructions": True,
        "points_encoded": False,
        "elevation": True
    }

    response = requests.post(f"{GRAPHHOPPER_URL}/route", json=payload)
    try:
        response.raise_for_status()
        data = response.json()
        path = data['paths'][0]

        # 신호등 개수 계산
        traffic_signal_count = count_traffic_signals(path.get('instructions', []))

        return OrderedDict([
            ("distance", round(path['distance'], 2)),
            ("instructions", path.get('instructions', [])),
            ("traffic_signals", traffic_signal_count),
            ("rawGraphhopper", data)
        ])

    except Exception as e:
        logging.error(f"❌ Error in startToEnd: {e}")
        logging.error(f"GraphHopper response: {response.text}")
        return None


#전체적인 응답을 반환해야
def get_directions(my_lat, my_lng, course_arr):
    logging.info("📡 Fetching GraphHopper directions...")

    results = []
    for course in course_arr:
        coords = extract_coords_arr(course)
        # ✅ FIXED: [lng, lat] → [lat, lng]
        coords.insert(0, [my_lat, my_lng])

        payload = {
            "points": coords,
            "profile": VEHICLE,
            "locale": LOCALE,
            "instructions": True,
            "points_encoded": False,
            "elevation": True
        }

        response = requests.post(f"{GRAPHHOPPER_URL}/route", json=payload)
        try:
            response.raise_for_status()
            data = response.json()
            path = data['paths'][0]

            # GET POINTS w/ ELEVATION
            """
            points: {
            "coordinates": [[lng, lat, ele], ...]
            }
            """
            gh_points = path['points']['coordinates']  # [lng,lat,ele]

            # CALC SLOPE
            #slope_data = calc_slope(gh_points)
            # 여기서 difficulty 계산을 수행

            results.append(OrderedDict([
                ("routeId", course["routeId"]),
                #("routeName", course["routeName"]),
                ("distance", round(path['distance'], 2)),
                #("estimatedTime", round(path['time'] / 1000 / 60, 1)),
                ("difficulty", course.get("difficulty", "")),
                ("description", course.get("description", "")),
                ("startPoint", {"lat": my_lat, "lng": my_lng}),
                ("endPoint", {"lat": gh_points[-1][1], "lng": gh_points[-1][0]}),
                ("instructions", path.get('instructions', [])),
                #("elevationPoints", [{"lat": p[1], "lng": p[0], "ele": p[2]} for p in gh_points]),
                #("slope", slope_data),   # 🚀 추가됨
                ("rawGraphhopper", data)
            ]))

            logging.info(f"✔ Route '{course['routeId']}' processed successfully.")

        except Exception as e:
            logging.error(f"❌ Error '{course['routeId']}': {e}")
            logging.error(f"GraphHopper response: {response.text}")

    return results

def count_traffic_signals(instructions):
    """
    GraphHopper instructions에서 신호등 개수를 세기.
    sign 값: -98 = 신호등 관련 지시
    """
    if not instructions:
        return 0

    signal_count = 0
    for instruction in instructions:
        # GraphHopper에서 신호등은 sign: -98로 표현될 수 있음
        if instruction.get('sign') == -98:
            signal_count += 1
    return signal_count