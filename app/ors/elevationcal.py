import logging
from app.utils import haversine, round_coord, MAX_ROUTE_ID, MAX_WAYPOINTS_PER_ROUTE

def cal_elevation_diff_arr(gh_points):
    """
    :param gh_points:
    points: {
    "coordinates": [[lng, lat, ele], ...]
    }
    :return:
    """
    #1-0 2-1 3-1....
    elevation_diffs = []
    for i in range(1, len(gh_points)):
        prev_ele = gh_points[i - 1][2] #elevation
        curr_ele = gh_points[i][2] #elevation
        elevation_diffs.append(round(curr_ele - prev_ele, 2))
    return elevation_diffs