# python
import logging
from typing import List, Optional, Sequence, Dict, Any

from app.utils import haversine, round_coord, MAX_ROUTE_ID, MAX_WAYPOINTS_PER_ROUTE

logger = logging.getLogger(__name__)

def _extract_elevations(gh_points: Sequence) -> List[float]:
    """
    다양한 포맷에서 고도 배열을 추출:
      - dict-like with "coordinates": [[lng, lat, ele], ...]
      - list of [lng, lat, ele] or [lat, lng, ele]
      - list of tuples
    반환: 고도(float) 리스트(충분한 고도 데이터가 없으면 빈 리스트)
    """
    pts = gh_points
    if not pts:
        return []

    # dict 형태에서 coordinates 추출
    if isinstance(pts, dict):
        coords = pts.get("coordinates") or pts.get("points") or pts.get("coordinates_list")
        if isinstance(coords, Sequence):
            pts = coords
        else:
            return []

    ele_list = []
    for p in pts:
        if not p or len(p) < 3:
            # 고도 정보가 없으면 skip
            ele_list.append(None)
            continue
        try:
            ele = float(p[2])
            ele_list.append(ele)
        except Exception:
            ele_list.append(None)

    # 모두 None 이면 고도 없음
    if not any(e is not None for e in ele_list):
        return []

    # None 포함 시 일관성을 위해 전체 무효화(선택적으로 보간할 수 있음)
    if any(e is None for e in ele_list):
        return []

    return [float(e) for e in ele_list]


def _smooth(elevations: List[float], window: int) -> List[float]:
    """
    단순 중앙 이동평균 스무딩. window는 홀수 권장(>=1).
    가장자리에서는 가능한 범위만 사용.
    """
    if window <= 1 or not elevations:
        return elevations[:]
    n = len(elevations)
    half = window // 2
    out = []
    for i in range(n):
        start = max(0, i - half)
        end = min(n, i + half + 1)
        segment = elevations[start:end]
        out.append(sum(segment) / len(segment))
    return out


def cal_elevation_diff_arr(gh_points: Sequence,
                           smoothing_window: int = 1,
                           noise_threshold: float = 0.0) -> Dict[str, Any]:
    """
    개선된 고도 변화 계산 함수.

    인자:
      - gh_points: GraphHopper 형식 또는 포인트 리스트 / dict with "coordinates"
      - smoothing_window: 스무딩 윈도우 크기(1이면 스무딩 없음)
      - noise_threshold: 절대값이 이보다 작은 구간 변화는 노이즈로 간주해 0 처리 (단위: m)

    반환 딕셔너리:
      {
        "has_elevation": bool,
        "elevation_diffs": [ ... ],   # 각 구간의 고도 변화 (m), 소수점 2자리
        "total_gain": float,          # 양수 변화 총합 (m)
        "total_loss": float,          # 하강 총합 (m)
        "max_segment_gain": float     # 구간별 최대 상승 (m)
      }

    동작:
      1. 다양한 입력 포맷에서 고도 리스트 추출
      2. 선택적 스무딩 적용
      3. 인접 점 차이를 계산하고 noise_threshold 이하인 변화는 0으로 처리
      4. 총상승/총하강/최대구간상승 계산
    """
    ele_list = _extract_elevations(gh_points)
    if not ele_list or len(ele_list) < 2:
        logger.debug("No valid elevation data found or insufficient points.")
        return {
            "has_elevation": False,
            "elevation_diffs": [],
            "total_gain": 0.0,
            "total_loss": 0.0,
            "max_segment_gain": 0.0
        }

    if smoothing_window and smoothing_window > 1:
        ele_proc = _smooth(ele_list, smoothing_window)
    else:
        ele_proc = ele_list

    diffs = []
    total_gain = 0.0
    total_loss = 0.0
    max_seg_gain = 0.0

    for i in range(1, len(ele_proc)):
        raw_delta = ele_proc[i] - ele_proc[i - 1]
        # 노이즈 임계값 적용
        if abs(raw_delta) <= noise_threshold:
            delta = 0.0
        else:
            delta = raw_delta

        delta_rounded = round(delta, 2)
        diffs.append(delta_rounded)

        if delta > 0:
            total_gain += delta
            if delta > max_seg_gain:
                max_seg_gain = delta
        elif delta < 0:
            total_loss += -delta

    return {
        "has_elevation": True,
        "elevation_diffs": diffs,
        "total_gain": round(total_gain, 2),
        "total_loss": round(total_loss, 2),
        "max_segment_gain": round(max_seg_gain, 2)
    }


def _point_to_lat_lng(p) -> Optional[tuple]:
    """
    간단한 포인트->(lat, lng) 변환:
    - 지원 포맷: [lng, lat, ...] 또는 [lat, lng, ...] 또는 (lng, lat, ...)
    - 실패 시 None 반환
    """
    if not p or len(p) < 2:
        return None
    try:
        a = float(p[0])
        b = float(p[1])
    except Exception:
        return None

    # a가 위도 범위이면 (lat, lng) = (a, b)로 간주
    if -90.0 <= a <= 90.0 and -180.0 <= b <= 180.0:
        return (a, b)
    # b가 위도 범위이면 (lat, lng) = (b, a)
    if -90.0 <= b <= 90.0 and -180.0 <= a <= 180.0:
        return (b, a)
    return None


def compute_score_0_10(gh_points: Sequence = None,
                      total_distance_m: Optional[float] = None,
                      smoothing_window: int = 1,
                      noise_threshold: float = 0.0) -> int:
    """
    0..10 점수 반환.

    인자:
      - gh_points: 좌표 리스트 또는 GraphHopper 스타일 입력(옵션)
      - total_distance_m: 미리 계산된 총거리(m). 제공되지 않으면 gh_points로 계산 시도
      - smoothing_window, noise_threshold: cal_elevation_diff_arr에 전달

    반환: int (0..10)
    """
    # 1) 엘리베이션 통계 얻기
    elev_stats = cal_elevation_diff_arr(gh_points, smoothing_window=smoothing_window, noise_threshold=noise_threshold)
    has_elev = bool(elev_stats.get("has_elevation"))
    elev_gain = float(elev_stats.get("total_gain", 0.0)) if has_elev else 0.0
    max_seg_gain = float(elev_stats.get("max_segment_gain", 0.0)) if has_elev else 0.0

    # 2) 총거리 계산(없으면 gh_points로 시도)
    total_dist = 0.0
    if total_distance_m is not None:
        try:
            total_dist = float(total_distance_m)
        except Exception:
            total_dist = 0.0
    else:
        if gh_points:
            prev = None
            for p in gh_points:
                latlng = _point_to_lat_lng(p)
                if latlng is None:
                    prev = None
                    continue
                if prev is not None:
                    total_dist += haversine(prev[0], prev[1], latlng[0], latlng[1])
                prev = latlng

    # 3) ITRA/Naismith 보정 적용: 상승 1m -> +10m 평지 등가
    effective_distance = total_dist + (elev_gain * 10.0) if has_elev else total_dist

    # 4) 유효거리 기반 기본 점수(0..10) — 계층적 임계값
    thresholds = [500, 1000, 2000, 3000, 5000, 7000, 10000, 15000, 20000, 30000]
    base_score = 0
    for i, t in enumerate(thresholds):
        if effective_distance >= t:
            base_score = i + 1
        else:
            break

    # 5) 엘리베이션 보너스 (총상승 / 최대구간상승에 따라 최대 +2)
    elev_bonus = 0
    if has_elev:
        if elev_gain >= 1000:
            elev_bonus += 2
        elif elev_gain >= 300:
            elev_bonus += 1

        # 급격한 구간상승이 있으면 추가 +1 (중복 보정을 억제하려면 조건을 조정)
        if max_seg_gain >= 100:
            elev_bonus += 1
        elif max_seg_gain >= 50 and elev_bonus == 0:
            # 총상승이 작아도 큰 구간 상승이 있으면 소폭 보정
            elev_bonus += 1

    score = int(min(10, base_score + elev_bonus))

    # 안전망: 음수 또는 NaN 방지
    if score < 0:
        score = 0

    return score