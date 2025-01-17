import re
import json
import statistics
import math
import numpy as np
from pathlib import Path
from statistics import mean

# Define regex patterns globally since they're used in multiple functions
remux_pattern = re.compile(r'remux', re.IGNORECASE)
uhd_pattern = re.compile(r'2160p', re.IGNORECASE)

# Release group mapping dictionary - keys should be lowercase
GROUP_MAPPINGS = {
    'beyondhd': 'W4NK3R',
    'b0mbardiers': 'b0mbardiers',
    'terminal': 'TERMiNAL',
    '10bit-hds': "HDS"
}


def normalize_group_name(name):
    """Normalize group name for case-insensitive matching"""
    if not name:
        return name
    normalized = name.lower()
    return GROUP_MAPPINGS.get(normalized, name)


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
                group_name = normalize_group_name(release['releaseGroup'])
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
    """Basic analysis of release group statistics"""
    analysis = []
    for group in results:
        stats = {
            "name": group["name"],
            "total_releases": len(group["releases"]),
            "average_size_gb": group["average_size_gb"],
            "average_compression_ratio": group["average_compression_ratio"]
        }
        analysis.append(stats)

    analysis.sort(key=lambda x: x["total_releases"], reverse=True)

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


def calculate_k(total_groups):
    """Calculate number of tiers based on total groups"""
    if total_groups < 15:
        return 3
    elif total_groups < 30:
        return 4
    elif total_groups < 50:
        return 5
    else:
        return 6


def get_k_explanation(total_groups):
    """Helper function to explain k calculation"""
    if total_groups < 15:
        return f"<15 groups → 3 tiers"
    elif total_groups < 30:
        return f"15-30 groups → 4 tiers"
    elif total_groups < 50:
        return f"31-50 groups → 5 tiers"
    else:
        return f">50 groups → 6 tiers"


def calculate_group_score(group_data, target_efficiency=0.55):
    """
    Calculate a comprehensive score for a release group based on:
    - Proximity to target efficiency (primary factor)
    - Release consistency/jitter (secondary factor)
    - Number of releases (minor factor, capped at 5)
    """
    efficiency = group_data["average_compression_ratio"]
    releases = len(group_data["releases"])
    ratios = [r["compression_ratio"] for r in group_data["releases"]]

    # Calculate efficiency score (0-100)
    efficiency_delta = abs(efficiency - target_efficiency)
    base_score = max(0, 100 - (efficiency_delta * 100))

    # Calculate jitter penalty if multiple releases
    if len(ratios) > 1:
        ratio_range = max(ratios) - min(ratios)
        # More reasonable jitter penalty (10 points per 10% spread)
        jitter_penalty = (ratio_range * 100) / 10
    else:
        jitter_penalty = 0

    # Small volume bonus (capped at 5 releases)
    volume_bonus = min(releases,
                       5) * 2  # +2 points per release up to 5 releases

    # Calculate final score
    final_score = base_score + volume_bonus - jitter_penalty

    # Ensure score stays within 0-100 range
    return round(max(0, min(100, final_score)), 2)


def analyze_tiers_enhanced(results, target_efficiency=0.60):
    """
    Enhanced version of tier analysis using the new scoring system
    """
    # Calculate scores for all groups
    groups_data = []
    for group in results:
        score = calculate_group_score(group, target_efficiency)

        groups_data.append({
            "name":
            group["name"],
            "efficiency":
            round(group["average_compression_ratio"] * 100, 2),
            "releases":
            len(group["releases"]),
            "score":
            score,
            "raw_data":
            group
        })

    # Sort groups by score
    groups_data.sort(key=lambda x: x["score"], reverse=True)

    # Calculate tier boundaries based on scores
    total_groups = len(groups_data)
    k = calculate_k(total_groups)

    # Use score percentiles to determine tier boundaries
    scores = [g["score"] for g in groups_data]
    tier_boundaries = []
    for i in range(1, k):
        percentile = 100 - (i * (100 / k))
        boundary = np.percentile(scores, percentile)
        tier_boundaries.append(boundary)

    # Assign tiers based on boundaries
    tiered_results = []
    for group in groups_data:
        # Determine tier based on score
        tier = k
        for i, boundary in enumerate(tier_boundaries):
            if group["score"] >= boundary:
                tier = i + 1
                break

        tiered_results.append({
            "tier": tier,
            "name": group["name"],
            "efficiency": group["efficiency"],
            "releases": group["releases"],
            "score": group["score"]
        })

    # Calculate tier statistics
    tier_stats = {}
    for group in tiered_results:
        tier = group["tier"]
        if tier not in tier_stats:
            tier_stats[tier] = {
                "groups": 0,
                "total_releases": 0,
                "avg_score": 0,
                "avg_efficiency": 0
            }

        tier_stats[tier]["groups"] += 1
        tier_stats[tier]["total_releases"] += group["releases"]
        tier_stats[tier]["avg_score"] += group["score"]
        tier_stats[tier]["avg_efficiency"] += group["efficiency"]

    # Calculate averages
    for tier in tier_stats:
        groups = tier_stats[tier]["groups"]
        tier_stats[tier]["avg_score"] = round(
            tier_stats[tier]["avg_score"] / groups, 2)
        tier_stats[tier]["avg_efficiency"] = round(
            tier_stats[tier]["avg_efficiency"] / groups, 2)

    return {
        "tiered_groups": tiered_results,
        "tier_stats": tier_stats,
        "total_tiers": k,
        "total_groups": total_groups,
        "target_efficiency": target_efficiency,
        "scoring_method": "comprehensive",
        "tier_boundaries": tier_boundaries
    }


def print_enhanced_tiering(tiering):
    """Print enhanced tiering results"""
    print("\n" + "=" * 80)
    print(f"{'ENHANCED TIERED RANKINGS':^80}")
    print(
        f"{'Target: 55% efficiency with volume and consistency weighting':^80}"
    )
    print(
        f"{'Groups: ' + str(tiering['total_groups']) + ' | Tiers: ' + str(tiering['total_tiers']) + ' (' + get_k_explanation(tiering['total_groups']) + ')':^80}"
    )
    print("=" * 80)

    unique_tiers = sorted(
        set(group['tier'] for group in tiering['tiered_groups']))

    for tier in unique_tiers:
        tier_groups = [
            g for g in tiering['tiered_groups'] if g['tier'] == tier
        ]
        tier_stats = tiering['tier_stats'][tier]

        print(f"\n{f'TIER {tier}':=^80}")
        print(f"Groups: {tier_stats['groups']} | "
              f"Avg Score: {tier_stats['avg_score']:.1f} | "
              f"Avg Efficiency: {tier_stats['avg_efficiency']}% | "
              f"Total Releases: {tier_stats['total_releases']}")
        print("-" * 80)

        # Column headers
        print(
            f"{'Group':<30} {'Score':>10} {'Efficiency':>10} {'Releases':>10}")
        print("-" * 80)

        # Sort groups within tier by score
        for group in sorted(tier_groups,
                            key=lambda x: x['score'],
                            reverse=True):
            print(f"{group['name']:<30} "
                  f"{group['score']:>9.1f} "
                  f"{group['efficiency']:>9}% "
                  f"{group['releases']:>10}")


def main():
    input_path = Path('input')
    if not input_path.exists():
        print("Input directory not found")
        return

    all_releases = []
    movies_processed = 0
    movies_with_2160p = 0
    movies_without_2160p = []

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
                else:
                    movies_without_2160p.append(file.stem)

            except json.JSONDecodeError:
                print(f"Error reading {file}")
                continue

    # Process and analyze releases
    results = analyze_releases(all_releases)
    analysis = analyze_results(results)
    enhanced_tiering = analyze_tiers_enhanced(results)

    # Save results
    with open('results.json', 'w') as f:
        json.dump(results, f, indent=2)

    with open('analysis.json', 'w') as f:
        json.dump(analysis, f, indent=2)

    # Save enhanced tiering results
    tiering_output = {
        "metadata": {
            "total_movies_processed": movies_processed,
            "movies_with_2160p": movies_with_2160p,
            "target_efficiency": enhanced_tiering["target_efficiency"],
            "total_tiers": enhanced_tiering["total_tiers"],
            "scoring_method": enhanced_tiering["scoring_method"]
        },
        "tier_statistics": enhanced_tiering["tier_stats"],
        "tiered_groups": enhanced_tiering["tiered_groups"],
        "scoring_details": {
            "tier_boundaries": enhanced_tiering["tier_boundaries"]
        }
    }

    with open('tiers.json', 'w') as f:
        json.dump(tiering_output, f, indent=2)

    # Print summaries
    print(f"\nProcessing Summary:")
    print(f"Movies Processed: {movies_processed}")
    print(f"Movies with 2160p: {movies_with_2160p}")
    print(f"Movies without 2160p: {movies_processed - movies_with_2160p}")

    if movies_without_2160p:
        print("\nMovies missing 4K releases:")
        for movie in sorted(movies_without_2160p):
            print(f"  - {movie}")

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

    # Print enhanced tiering results
    print_enhanced_tiering(enhanced_tiering)

    print("\n" + "=" * 80)
    print(f"{'OUTPUT FILES':^80}")
    print("-" * 80)
    print(f"{'results.json':<20} Raw release data")
    print(f"{'analysis.json':<20} Group statistics")
    print(f"{'tiers.json':<20} Enhanced tiered rankings")
    print("=" * 80)


if __name__ == "__main__":
    main()
