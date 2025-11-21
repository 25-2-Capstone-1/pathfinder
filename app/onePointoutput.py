import os
import requests
import math
from collections import deque
import app
import findIsochrone

if __name__ == "__main__":
    origin = (37.5665, 126.9780)  # Seoul City Hall
    radius_m = 3000  # 3 km


    print("\nMethod 2: Using straight-line distance (fast but approximate)")
    points_fast = findIsochrone.expand_by_straight_line(origin, radius_m, step_m=500, max_points=50)
    print(f"\nFound {len(points_fast)} points within {radius_m}m")
    for p in points_fast[:10]:
        print(p)