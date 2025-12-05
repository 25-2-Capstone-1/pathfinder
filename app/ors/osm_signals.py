import requests
import logging
from typing import List, Tuple, Optional
from app.utils import haversine

logger = logging.getLogger(__name__)

def get_traffic_signals_from_osm(bbox: Tuple[float, float, float, float],
                                  radius_m: float = 50.0) -> List[dict]:
    """
    Overpass API를 통해 OSM에서 신호등 데이터 추출.

    Args:
        bbox: (south, west, north, east) 경계 좌표
        radius_m: 경로 주변 검색 반경(미터)

    Returns:
        신호등 위치 정보 리스트: [{'lat': float, 'lng': float, 'id': str}, ...]
    """
    south, west, north, east = bbox

    # Overpass API 쿼리
    overpass_query = f"""
    [bbox:{south},{west},{north},{east}];
    (
        node["highway"="traffic_signals"];
        way["highway"="traffic_signals"];
    );
    out center;
    """

    try:
        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=overpass_query,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        signals = []
        for element in data.get('elements', []):
            if element['type'] == 'node':
                signals.append({
                    'lat': element['lat'],
                    'lng': element['lon'],
                    'id': element['id']
                })
            elif element['type'] == 'way' and 'center' in element:
                signals.append({
                    'lat': element['center']['lat'],
                    'lng': element['center']['lon'],
                    'id': element['id']
                })

        logger.info(f"✔ Found {len(signals)} traffic signals from OSM")
        return signals

    except Exception as e:
        logger.error(f"❌ Error fetching OSM signals: {e}")
        return []


def count_signals_near_path(path: List[Tuple[float, float]],
                            buffer_distance_m: float = 100.0) -> int:
    """
    경로 주변의 신호등 개수 계산.

    Args:
        path: [(lat, lng), ...] 형식의 경로
        buffer_distance_m: 경로로부터의 거리 버퍼(미터)

    Returns:
        신호등 개수
    """
    if not path or len(path) < 2:
        return 0

    # 경로의 바운딩박스 계산
    lats = [p[0] for p in path]
    lngs = [p[1] for p in path]

    buffer_deg = buffer_distance_m / 111000.0
    bbox = (
        min(lats) - buffer_deg,
        min(lngs) - buffer_deg,
        max(lats) + buffer_deg,
        max(lngs) + buffer_deg
    )

    # OSM에서 신호등 가져오기
    signals = get_traffic_signals_from_osm(bbox)

    # 경로 주변 신호등만 카운팅
    count = 0
    for signal in signals:
        for i in range(len(path) - 1):
            lat1, lng1 = path[i]
            lat2, lng2 = path[i + 1]

            # 선분까지의 최단 거리 계산
            dist_to_segment = _point_to_segment_distance(
                signal['lat'], signal['lng'],
                lat1, lng1, lat2, lng2
            )

            if dist_to_segment <= buffer_distance_m:
                count += 1
                break

    return count


def _point_to_segment_distance(px: float, py: float,
                               x1: float, y1: float,
                               x2: float, y2: float) -> float:
    """
    점에서 선분까지의 최단 거리(미터 단위).
    """
    # 간단한 근사: 점과 두 끝점까지의 거리 중 최솟값
    dist_to_p1 = haversine(px, py, x1, y1)
    dist_to_p2 = haversine(px, py, x2, y2)

    # 더 정확한 계산을 위해 선분의 중점도 고려
    mid_x = (x1 + x2) / 2
    mid_y = (y1 + y2) / 2
    dist_to_mid = haversine(px, py, mid_x, mid_y)

    return min(dist_to_p1, dist_to_p2, dist_to_mid)