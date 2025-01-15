import re
import json
from statistics import mean
from pathlib import Path


def analyze_releases(input_data):
    """
    Analyzes movie release data to generate statistics about release groups.
    """
    # Dictionary to store release group data
    release_groups = {}

    # Regex patterns for remux detection
    remux_pattern = re.compile(r'remux', re.IGNORECASE)
    uhd_pattern = re.compile(r'2160p', re.IGNORECASE)

    # Process each movie's releases
    for movie_data in input_data:
        # First find remux sizes for this movie
        remux_releases = []

        for release in movie_data:
            if 'title' not in release or 'size' not in release:
                continue

            title = release['title']
            # Check if it's both 2160p and remux using regex
            if uhd_pattern.search(title) and remux_pattern.search(title):
                size_gb = release['size'] / (1024**3)
                remux_releases.append({
                    "remux_title": title,
                    "remux_size_gb": round(size_gb, 1)
                })

        if not remux_releases:
            continue

        avg_remux_size = mean(r["remux_size_gb"] for r in remux_releases)

        # Process encode releases
        for release in movie_data:
            if ('quality' not in release or 'title' not in release
                    or 'size' not in release or 'releaseGroup' not in release):
                continue

            if release['quality'].get('quality',
                                      {}).get('name') == "Bluray-2160p":
                group_name = release['releaseGroup']
                if not group_name:
                    continue

                size_gb = release['size'] / (1024**3)
                compression_ratio = size_gb / avg_remux_size

                if group_name not in release_groups:
                    release_groups[group_name] = {
                        "name": group_name,
                        "releases": [],
                        "sizes": [],
                        "ratios": []
                    }

                release_groups[group_name]["releases"].append({
                    "release_title":
                    release['title'],
                    "size_gb":
                    round(size_gb, 1),
                    "remux_releases":
                    remux_releases,  # Now including all remux info
                    "compression_ratio":
                    round(compression_ratio, 2)
                })

                release_groups[group_name]["sizes"].append(size_gb)
                release_groups[group_name]["ratios"].append(compression_ratio)

    # Calculate averages and format final output
    output = []
    for group_data in release_groups.values():
        if group_data["releases"]:
            output.append({
                "name":
                group_data["name"],
                "average_size_gb":
                round(mean(group_data["sizes"]), 1),
                "average_compression_ratio":
                round(mean(group_data["ratios"]), 2),
                "releases":
                group_data["releases"]
            })

    return output


def main():
    input_path = Path('input')
    if not input_path.exists():
        print("Input directory not found")
        return

    all_releases = []

    # Read all JSON files in input directory
    for file in input_path.glob('*.json'):
        with open(file, 'r') as f:
            try:
                movie_data = json.load(f)
                all_releases.append(movie_data)
            except json.JSONDecodeError:
                print(f"Error reading {file}")
                continue

    # Analyze all releases
    results = analyze_releases(all_releases)

    # Write results to file
    with open('results.json', 'w') as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
