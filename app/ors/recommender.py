# File: `app/ors/recommender.py`
# python
from typing import Optional, Sequence, Dict, Any

from app.ors.elevationcal import compute_score_0_10


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))

def _norm_1_10_to_0_1(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    try:
        v = float(v)
    except Exception:
        return None
    return _clamp((v - 1.0) / 9.0, 0.0, 1.0)

def score_route(distance_m: float,
                target_distance_m: Optional[float] = None,
                elev_points: Optional[Sequence] = None,
                slope_rating: Optional[float] = None,
                signals_rating: Optional[float] = None,               # legacy
                traffic_lights_rating: Optional[float] = None,
                traffic_congestion_rating: Optional[float] = None,
                weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    경로 점수 계산 (0..10).
    Accepts user preferences:
      - slope_rating (or 'slope' from input)
      - traffic_lights_rating (or 'trafficLights')
      - traffic_congestion_rating (or 'trafficCongestion')
    """

    # 기본 가중치: 합이 1.0 이 되어야 함
    if weights is None:
        weights = {
            "distance": 0.40,
            "elevation": 0.05,
            "slope": 0.3,
            "trafficLights": 0.2,
            "trafficCongestion": 0.05
        }

    # 1) distance score: 목표와 가까울수록 1.0
    if target_distance_m and target_distance_m > 0:
        diff_ratio = abs(distance_m - target_distance_m) / target_distance_m
        distance_score = _clamp(1.0 - diff_ratio)
    else:
        distance_score = 0.5

    # 2) elevation score: 0..10 -> 0..1
    if elev_points:
        try:
            elev10 = compute_score_0_10(gh_points=elev_points, total_distance_m=distance_m)
            elevation_score = _clamp(float(elev10) / 10.0)
        except Exception:
            elevation_score = 0.5
    else:
        elevation_score = 0.5

    # 3) slope: 1..10 (클수록 가파름=나쁨) -> 0..1 (클수록 좋음)
    s_input = slope_rating
    if s_input is None:
        # no slope pref provided -> neutral
        slope_score = 0.5
    else:
        s_n = _norm_1_10_to_0_1(s_input)
        slope_score = 1.0 - s_n if s_n is not None else 0.5

    # 4) traffic_lights: 신호등 개수 -> 1..10으로 매핑
    if traffic_lights_rating is None:
        traffic_lights_score = 0.5
    else:
        # 신호등 0~30개 기준으로 1..10으로 변환 (많을수록 낮은 점수)
        signal_count = float(traffic_lights_rating)
        normalized_signal = _clamp(signal_count / 30.0)
        traffic_lights_score = 1.0 - normalized_signal

    tl_n = _norm_1_10_to_0_1(traffic_lights_rating)
    tc_n = _norm_1_10_to_0_1(traffic_congestion_rating)

    traffic_lights_score = 1.0 - tl_n if tl_n is not None else 0.5
    traffic_congestion_score = 1.0 - tc_n if tc_n is not None else 0.5

    # 결합 (weights 키와 일치하도록)
    total = (
        distance_score * weights.get("distance", 0.0) +
        elevation_score * weights.get("elevation", 0.0) +
        slope_score * weights.get("slope", 0.0) +
        traffic_lights_score * weights.get("trafficLights", 0.0) +
        traffic_congestion_score * weights.get("trafficCongestion", 0.0)
    )

    score_0_10 = int(round(_clamp(total) * 10))

    return {
        "score_0_10": score_0_10,
        "score_components": {
            "distance": round(distance_score, 3),
            "elevation": round(elevation_score, 3),
            "slope": round(slope_score, 3),
            "trafficLights": round(traffic_lights_score, 3),
            "trafficCongestion": round(traffic_congestion_score, 3)
        },
        "weighted_total_0_1": round(total, 4)
    }

