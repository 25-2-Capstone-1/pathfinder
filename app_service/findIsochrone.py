import math
import requests
from collections import deque
import os
from dotenv import load_dotenv
import time


load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")



def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in meters."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def round_coord(point, precision=5):
    """Round coordinates to a consistent precision."""
    return round(point[0], precision), round(point[1], precision)

def get_distances_batch(origin, destinations):
    """
    Get distances from one origin to multiple destinations using batch API.
    Returns dict {destination: distance_in_meters}
    """
    if not destinations:
        return {}

    # Google API allows up to 25 destinations per request
    chunk_size = 25
    all_distances = {}

    for i in range(0, len(destinations), chunk_size):
        chunk = destinations[i:i + chunk_size]

        # Format destinations as "lat1,lng1|lat2,lng2|..."
        dest_str = "|".join([f"{lat},{lng}" for lat, lng in chunk])

        url = (
            "https://maps.googleapis.com/maps/api/distancematrix/json"
            f"?origins={origin[0]},{origin[1]}"
            f"&destinations={dest_str}"
            f"&mode=walking&key={GOOGLE_API_KEY}"
        )

        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()

            if data.get("status") != "OK":
                print(f"API Error: {data.get('status')}")
                continue

            elements = data["rows"][0]["elements"]
            for dest, element in zip(chunk, elements):
                if element["status"] == "OK":
                    all_distances[dest] = element["distance"]["value"]

            # Rate limiting: avoid hitting API limits
            time.sleep(0.1)

        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            continue

    return all_distances


def generate_neighbors(point, step_m=100):
    """
    Generate 4 neighboring coordinates (N, S, E, W) at step_m meters distance.
    """
    lat, lng = point
    delta_lat = step_m / 111_000  # ~111km per degree latitude
    delta_lng = step_m / (111_000 * math.cos(math.radians(lat)))

    neighbors = [
        (lat + delta_lat, lng),  # North
        (lat - delta_lat, lng),  # South
        (lat, lng + delta_lng),  # East
        (lat, lng - delta_lng),  # West
    ]

    print(f"Generated neighbors for {point}: {neighbors}")
    return [round_coord(n) for n in neighbors]


def expand_by_distance(origin, max_distance, step_m=100, max_points=200):
    """
    Expand from origin using BFS, finding all points within max_distance.
    Uses batch API calls for efficiency.
    """
    origin = round_coord(origin)
    visited = {origin}
    reachable = []
    queue = deque([origin])

    # Cache to avoid redundant API calls
    distance_cache = {origin: 0}

    while queue and len(reachable) < max_points:
        # Process multiple points in batch
        batch_size = min(10, len(queue))  # Process 10 points at a time
        current_batch = [queue.popleft() for _ in range(batch_size)]

        # Collect all unique neighbors from this batch
        all_neighbors = []
        neighbor_to_source = {}  # Track which point generated each neighbor

        for current in current_batch:
            neighbors = generate_neighbors(current, step_m)
            for neighbor in neighbors:
                if neighbor not in visited:
                    all_neighbors.append(neighbor)
                    neighbor_to_source[neighbor] = current
                    visited.add(neighbor)

        if not all_neighbors:
            continue

        # Get distances from origin to all neighbors in batch
        distances = get_distances_batch(origin, all_neighbors)

        # Process results
        for neighbor, distance in distances.items():
            if distance <= max_distance:
                reachable.append(neighbor)
                distance_cache[neighbor] = distance
                queue.append(neighbor)

                if len(reachable) >= max_points:
                    break

        print(f"Progress: {len(reachable)}/{max_points} points found, "
              f"{len(queue)} in queue, {len(visited)} visited")

    return reachable, distance_cache


def expand_by_straight_line(origin, max_distance, step_m=100, max_points=200):
    """
    Alternative: expand using straight-line distance (no API calls).
    Much faster but less accurate for walking routes.
    """
    origin = round_coord(origin)
    visited = {origin}
    reachable = []
    queue = deque([origin])

    while queue and len(reachable) < max_points:
        current = queue.popleft()

        for neighbor in generate_neighbors(current, step_m):
            if neighbor in visited:
                continue

            visited.add(neighbor)

            # Calculate straight-line distance using haversine
            lat1, lng1 = origin
            lat2, lng2 = neighbor
            distance = haversine(lat1, lng1, lat2, lng2)

            if distance <= max_distance:
                reachable.append(neighbor)
                queue.append(neighbor)
    print(f"Progress: {len(reachable)}/{max_points} points found, ")

    return reachable

# if __name__ == "__main__":
    #     # 사용자 입력 받기
    #     radius_m = int(input("Enter the radius in meters: "))
    #     origin_lat = float(input("Enter the origin latitude: "))
    #     origin_lng = float(input("Enter the origin longitude: "))
    #     step_m = int(input("Enter the step in meters: "))
    #
    #     origin = (origin_lat, origin_lng)
    #
    #     # 입력값으로 함수 호출
    #     reachable_points, _ = expand_by_distance(origin, radius_m, step_m)
    #
    #     # 결과 출력
    #     print("\nReachable points:")
    #     for point in reachable_points:
    #         print(point)