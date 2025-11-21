import openrouteservice
import os
from dotenv import load_dotenv
# Example client
load_dotenv()
client = openrouteservice.Client(key=os.getenv("ORS_API_KEY"))

# ORS Seoul approximate bounds (min lon, min lat, max lon, max lat)
SEOUl_BBOX = [126.76, 37.42, 127.18, 37.70]

def in_bounds(coord, bbox):
    """Check if a single [lon, lat] is inside bbox."""
    lon, lat = coord
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]

def filter_coords(coords, bbox):
    """Keep only coordinates within bbox."""
    return [c for c in coords if in_bounds(c, bbox)]

coords = [
    [126.9647, 37.5297],  # some point
    [126.9741, 37.5356],  # some point
    [126.978, 37.5665]
]

# Filter out-of-bounds points
coords_filtered = filter_coords(coords, SEOUl_BBOX)

if len(coords_filtered) < 2:
    print("❌ Not enough valid coordinates in ORS region.")
else:
    # Make directions request
    result = client.directions(
        coordinates=coords_filtered,
        profile="foot-walking",
        format="json",
        optimize_waypoints=False,
        instructions=True
    )
    print(result['routes'][0]['summary'])