# geocode_cli.py
import argparse
from helpers import geocode_location

def main():
    parser = argparse.ArgumentParser(
        description="Lookup lat/lon for a place via geocode_location()"
    )
    parser.add_argument("location", nargs="+", help="Location name to geocode")
    parser.add_argument(
        "--type",
        choices=["exposure", "location"],
        default="exposure",
        help="Which candidate generation logic to use"
    )
    args = parser.parse_args()

    query = " ".join(args.location)
    lat, lon = geocode_location(query, agent_type=args.type)
    if lat is None or lon is None:
        print(f"No coordinates found for “{query}”")
    else:
        print(f"{query} → lat: {lat:.6f}, lon: {lon:.6f}")

if __name__ == "__main__":
    main()
