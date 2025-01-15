import re
import json
from statistics import mean
from pathlib import Path

# Define regex patterns globally since they're used in multiple functions
remux_pattern = re.compile(r'remux', re.IGNORECASE)
uhd_pattern = re.compile(r'2160p', re.IGNORECASE)


def analyze_releases(input_data):
    """
    Analyzes movie release data to generate statistics about release groups.
    """
    # Dictionary to store release group data
    release_groups = {}

    # Process each movie's releases
    for movie_data in input_data:
        # First find remux sizes for this movie
        remux_sizes = []

        for release in movie_data:
            if 'title' not in release or 'size' not in release:
                continue

            title = release['title']
            # Check if it's both 2160p and remux
            if uhd_pattern.search(title) and remux_pattern.search(title):
                size_gb = release['size'] / (1024**3)
                remux_sizes.append(size_gb)

        avg_remux_size = mean(remux_sizes) if remux_sizes else None
        if not avg_remux_size:
            continue

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
                    "remux_size_gb":
                    round(avg_remux_size, 1),
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


def analyze_results(results):
    """
    Analyze the generated results to provide statistics about each release group.
    """
    # Create analytics for each group
    analysis = []

    for group in results:
        stats = {
            "name": group["name"],
            "total_releases": len(group["releases"]),
            "average_size_gb": group["average_size_gb"],
            "average_compression_ratio": group["average_compression_ratio"]
        }
        analysis.append(stats)

    # Sort groups by number of releases
    analysis.sort(key=lambda x: x["total_releases"], reverse=True)

    # Calculate overall statistics
    total_releases = sum(g["total_releases"] for g in analysis)
    all_compression_ratios = [g["average_compression_ratio"] for g in analysis]

    overall_stats = {
        "total_groups":
        len(analysis),
        "total_releases":
        total_releases,
        "average_compression_across_all_groups":
        round(mean(all_compression_ratios), 2)
        if all_compression_ratios else 0,
        "most_efficient_group":
        min(analysis, key=lambda x: x["average_compression_ratio"])["name"]
        if analysis else None,
        "largest_group":
        max(analysis, key=lambda x: x["total_releases"])["name"]
        if analysis else None
    }

    return {"group_analysis": analysis, "overall_stats": overall_stats}


def analyze_tiers(results, target_efficiency=0.60):
    """
    Analyze release groups and assign them to tiers based on their delta from target efficiency.
    Uses k-means clustering to determine tiers.
    
    Args:
        results: List of dictionaries containing release group data
        target_efficiency: Target compression ratio (default 0.60 or 60%)
        
    Returns:
        Dictionary containing tiered results and statistics
    """
    from sklearn.cluster import KMeans
    import numpy as np

    # Extract relevant data
    groups_data = []
    for group in results:
        efficiency = group["average_compression_ratio"]
        delta = abs(efficiency - target_efficiency)

        groups_data.append({
            "name": group["name"],
            "efficiency": efficiency,
            "delta": delta,
            "releases": len(group["releases"])
        })

    # Prepare data for k-means
    deltas = np.array([g["delta"] for g in groups_data]).reshape(-1, 1)

    # Calculate number of tiers (k)
    k = max(2, len(groups_data) // 10)  # At least 2 tiers

    # Perform k-means clustering
    kmeans = KMeans(n_clusters=k, random_state=42)
    clusters = kmeans.fit_predict(deltas)

    # Sort clusters by centroids
    # Lower delta = better tier
    centroid_order = np.argsort(kmeans.cluster_centers_.flatten())
    tier_mapping = {
        cluster: tier + 1
        for tier, cluster in enumerate(centroid_order)
    }

    # Assign tiers and format results
    tiered_results = []
    for group, cluster in zip(groups_data, clusters):
        tiered_results.append({
            "tier": tier_mapping[cluster],
            "name": group["name"],
            "efficiency": round(group["efficiency"] * 100,
                                2),  # Convert to percentage
            "delta": round(group["delta"] * 100, 2),  # Convert to percentage
            "releases": group["releases"]
        })

    # Sort by tier, then by delta within tiers
    tiered_results.sort(key=lambda x: (x["tier"], x["delta"]))

    # Calculate tier statistics
    tier_stats = {}
    for group in tiered_results:
        tier = group["tier"]
        if tier not in tier_stats:
            tier_stats[tier] = {
                "groups": 0,
                "total_releases": 0,
                "avg_efficiency": 0,
                "avg_delta": 0
            }

        tier_stats[tier]["groups"] += 1
        tier_stats[tier]["total_releases"] += group["releases"]
        tier_stats[tier]["avg_efficiency"] += group["efficiency"]
        tier_stats[tier]["avg_delta"] += group["delta"]

    # Calculate averages for tier statistics
    for tier in tier_stats:
        groups = tier_stats[tier]["groups"]
        tier_stats[tier]["avg_efficiency"] = round(
            tier_stats[tier]["avg_efficiency"] / groups, 2)
        tier_stats[tier]["avg_delta"] = round(
            tier_stats[tier]["avg_delta"] / groups, 2)

    return {
        "tiered_groups": tiered_results,
        "tier_stats": tier_stats,
        "total_tiers": k,
        "target_efficiency": target_efficiency
    }


def main():
    input_path = Path('input')
    if not input_path.exists():
        print("Input directory not found")
        return

    all_releases = []
    movies_processed = 0
    movies_with_2160p = 0

    # Read all JSON files in input directory
    for file in input_path.glob('*.json'):
        with open(file, 'r') as f:
            try:
                movie_data = json.load(f)
                all_releases.append(movie_data)
                movies_processed += 1

                # Track if movie has any 2160p release
                has_2160p = False
                for release in movie_data:
                    if 'title' in release and uhd_pattern.search(
                            release['title']):
                        has_2160p = True
                        break

                if has_2160p:
                    movies_with_2160p += 1

            except json.JSONDecodeError:
                print(f"Error reading {file}")
                continue

    print(f"\nProcessing Summary:")
    print(f"Movies Processed: {movies_processed}")
    print(f"Movies with 2160p: {movies_with_2160p}")
    print(f"Movies without 2160p: {movies_processed - movies_with_2160p}")

    # Analyze all releases
    results = analyze_releases(all_releases)
    analysis = analyze_results(results)
    tiering = analyze_tiers(results)

    # Write original results and analysis
    with open('results.json', 'w') as f:
        json.dump(results, f, indent=2)

    with open('analysis.json', 'w') as f:
        json.dump(analysis, f, indent=2)

    # Write tiering results
    tiering_output = {
        "metadata": {
            "total_movies_processed": movies_processed,
            "movies_with_2160p": movies_with_2160p,
            "target_efficiency": tiering["target_efficiency"],
            "total_tiers": tiering["total_tiers"]
        },
        "tier_statistics": tiering["tier_stats"],
        "tiered_groups": tiering["tiered_groups"]
    }

    with open('tiers.json', 'w') as f:
        json.dump(tiering_output, f, indent=2)

    # Print analysis summary
    print("\nAnalysis Summary:")
    print(f"Total Release Groups: {analysis['overall_stats']['total_groups']}")
    print(f"Total Releases: {analysis['overall_stats']['total_releases']}")
    print(
        f"Average Compression Ratio: {analysis['overall_stats']['average_compression_across_all_groups']}"
    )
    print(
        f"Most Efficient Group: {analysis['overall_stats']['most_efficient_group']}"
    )
    print(f"Largest Group: {analysis['overall_stats']['largest_group']}")

    # Print tiered results
    print("\n" + "=" * 80)
    print(f"{'TIERED RANKINGS':^80}")
    print(f"{'Target: 60% efficiency':^80}")
    print("=" * 80)

    # First, get all unique tiers and sort them
    unique_tiers = sorted(
        set(group['tier'] for group in tiering['tiered_groups']))

    for tier in unique_tiers:
        tier_groups = [
            g for g in tiering['tiered_groups'] if g['tier'] == tier
        ]
        tier_stats = tiering['tier_stats'][tier]

        print(f"\n{f'TIER {tier}':=^80}")
        print(f"Groups: {tier_stats['groups']} | "
              f"Avg Efficiency: {tier_stats['avg_efficiency']}% | "
              f"Avg Δ: {tier_stats['avg_delta']}% | "
              f"Total Releases: {tier_stats['total_releases']}")
        print("-" * 80)

        # Column headers
        print(
            f"{'Group':<30} {'Efficiency':>10} {'Delta':>10} {'Releases':>10}")
        print("-" * 80)

        # Sort groups within tier by delta
        for group in sorted(tier_groups, key=lambda x: x['delta']):
            print(f"{group['name']:<30} "
                  f"{group['efficiency']:>9}% "
                  f"{f'Δ{group['delta']}%':>10} "
                  f"{group['releases']:>10}")

    print("\n" + "=" * 80)
    print(f"{'OUTPUT FILES':^80}")
    print("-" * 80)
    print(f"{'results.json':<20} Raw release data")
    print(f"{'analysis.json':<20} Group statistics")
    print(f"{'tiers.json':<20} Tiered rankings")
    print("=" * 80)


if __name__ == "__main__":
    main()
