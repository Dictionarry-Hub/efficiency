import argparse
import re
import json
import statistics
import math
import numpy as np
from pathlib import Path
from statistics import mean


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description=
        'Analyze release group efficiency and generate tier rankings.')
    parser.add_argument('--target',
                        type=float,
                        default=0.55,
                        help='Target efficiency ratio (default: 0.55)')
    return parser.parse_args()


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

# Blacklisted groups
BLACKLISTED_GROUPS = {'HONE', 'BHDStudio', 'hallowed'}


def normalize_group_name(name):
    """Normalize group name for case-insensitive matching"""
    if not name:
        return name
    normalized = name.lower()
    return GROUP_MAPPINGS.get(normalized, name)


def analyze_releases(input_data):
    """Analyzes movie release data to generate statistics about release groups."""
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
                if not group_name or group_name in BLACKLISTED_GROUPS:  # Check blacklist here
                    continue

                size_gb = release['size'] / (1024**3)
                compression_ratio = size_gb / avg_remux_size

                # Skip releases with extreme compression ratios
                if compression_ratio < 0.10 or compression_ratio > 0.90:
                    continue

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
            avg_ratio = mean(group_data["ratios"])
            # Double-check the average ratio is within bounds
            if 0.10 <= avg_ratio <= 0.90:
                output.append({
                    "name":
                    group_data["name"],
                    "average_size_gb":
                    round(mean(group_data["sizes"]), 1),
                    "average_compression_ratio":
                    round(avg_ratio, 2),
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
    """Scoring system with strict volume requirements AND efficiency thresholds"""
    efficiency = group_data["average_compression_ratio"]
    releases = len(group_data["releases"])
    ratios = [r["compression_ratio"] for r in group_data["releases"]]

    # Calculate efficiency delta
    efficiency_delta = abs(efficiency - target_efficiency)
    delta_percent = efficiency_delta * 100

    # First apply hard efficiency-based tier restrictions
    if delta_percent > 12:  # More than 12% off target
        max_possible_score = 45  # Cannot reach above Tier 4
    elif delta_percent > 8:  # More than 8% off target
        max_possible_score = 65  # Cannot reach above Tier 3
    elif delta_percent > 5:  # More than 5% off target
        max_possible_score = 75  # Cannot reach above Tier 2
    else:
        max_possible_score = 100

    # Then apply volume-based restrictions (take the more restrictive of the two)
    if releases < 5:
        max_possible_score = min(max_possible_score,
                                 65)  # Cannot reach above Tier 3
    elif releases < 10:
        max_possible_score = min(max_possible_score,
                                 75)  # Cannot reach above Tier 2
    elif releases < 15:
        max_possible_score = min(max_possible_score,
                                 85)  # Must be Tier 2 or lower

    # Base efficiency score (0-70 points)
    base_score = 70 * math.exp(-3.0 * efficiency_delta)

    # Volume bonus (0-20 points)
    volume_bonus = min(20, 4 * math.log2(releases + 1))

    # Consistency bonus (0-10 points)
    if len(ratios) > 1:
        std_dev = statistics.stdev(ratios)
        consistency_bonus = 10 * math.exp(-3 * std_dev)
    else:
        consistency_bonus = 0

    # Heavy penalties for small sample sizes
    if releases < 5:
        confidence_penalty = 25 - (4 * releases)
    elif releases < 10:
        confidence_penalty = 10
    else:
        confidence_penalty = 0

    # Additional efficiency penalty for severe deviations
    if delta_percent > 12:
        efficiency_penalty = 20
    elif delta_percent > 8:
        efficiency_penalty = 15
    elif delta_percent > 5:
        efficiency_penalty = 10
    else:
        efficiency_penalty = 0

    # Calculate preliminary score
    preliminary_score = (base_score + volume_bonus + consistency_bonus -
                         confidence_penalty - efficiency_penalty)

    # Apply hard cap
    final_score = min(preliminary_score, max_possible_score)

    return round(max(0, min(100, final_score)), 2)


def calculate_tier_thresholds(scores, num_tiers):
    """Calculate tier thresholds with strict efficiency and volume minimums"""
    if not scores:
        return []

    # Define minimum scores required for each tier
    min_tier_scores = {
        1: 85,  # Tier 1: Excellent efficiency (<5% delta) and 15+ releases
        2: 75,  # Tier 2: Good efficiency (<8% delta) and 10+ releases
        3: 65,  # Tier 3: Decent efficiency (<12% delta) and 5+ releases
        4: 55,  # Tier 4: Everything else
    }

    sorted_scores = sorted(scores, reverse=True)
    thresholds = []

    for tier in range(1, num_tiers):
        if tier in min_tier_scores:
            threshold = max(
                min_tier_scores[tier],
                np.percentile(sorted_scores, 100 - (tier * (100 / num_tiers))))
        else:
            threshold = np.percentile(sorted_scores,
                                      100 - (tier * (100 / num_tiers)))
        thresholds.append(threshold)

    return thresholds


def analyze_tiers_enhanced(results, target_efficiency=0.55):
    """Enhanced tiering analysis with strict volume and efficiency requirements"""
    # Calculate scores and collect group data
    groups_data = []
    for group in results:
        releases = len(group["releases"])
        efficiency = group["average_compression_ratio"]
        efficiency_delta = abs(
            efficiency - target_efficiency) * 100  # Convert to percentage

        # Determine tier cap based on BOTH volume and efficiency
        if efficiency_delta > 12 or releases < 5:
            tier_cap = 4  # Must be Tier 4 or lower
        elif efficiency_delta > 8 or releases < 10:
            tier_cap = 3  # Must be Tier 3 or lower
        elif efficiency_delta > 5 or releases < 15:
            tier_cap = 2  # Must be Tier 2 or lower
        else:
            tier_cap = 1  # Can be any tier

        score = calculate_group_score(group, target_efficiency)

        ratios = [r["compression_ratio"] for r in group["releases"]]
        std_dev = statistics.stdev(ratios) if len(ratios) > 1 else 0

        groups_data.append({
            "name": group["name"],
            "score": score,
            "efficiency": round(efficiency * 100, 2),
            "efficiency_delta": efficiency_delta,
            "releases": releases,
            "std_dev": round(std_dev, 3),
            "tier_cap": tier_cap,
            "raw_data": group
        })

    # Sort groups by score
    groups_data.sort(key=lambda x: x["score"], reverse=True)

    # Calculate optimal number of tiers
    total_groups = len(groups_data)
    k = calculate_k(total_groups)

    # Calculate tier thresholds
    scores = [g["score"] for g in groups_data]
    tier_boundaries = calculate_tier_thresholds(scores, k)

    # Assign tiers with volume and efficiency restrictions
    tiered_results = []
    tier_stats = {}

    for group in groups_data:
        # Determine initial tier based on score
        tier = k
        for i, boundary in enumerate(tier_boundaries):
            if group["score"] >= boundary:
                tier = i + 1
                break

        # Apply tier cap based on both volume and efficiency
        tier = max(tier, group["tier_cap"])

        group_result = {
            "tier": tier,
            "name": group["name"],
            "score": group["score"],
            "efficiency": group["efficiency"],
            "releases": group["releases"],
            "std_dev": group["std_dev"],
            "efficiency_delta": group["efficiency_delta"]
        }

        tiered_results.append(group_result)

        # Update tier statistics
        if tier not in tier_stats:
            tier_stats[tier] = {
                "groups": 0,
                "total_releases": 0,
                "avg_score": 0,
                "avg_efficiency": 0,
                "avg_std_dev": 0
            }

        stats = tier_stats[tier]
        stats["groups"] += 1
        stats["total_releases"] += group["releases"]
        stats["avg_score"] += group["score"]
        stats["avg_efficiency"] += group["efficiency"]
        stats["avg_std_dev"] += group["std_dev"]

    # Calculate tier averages
    for tier in tier_stats:
        groups = tier_stats[tier]["groups"]
        stats = tier_stats[tier]
        stats["avg_score"] = round(stats["avg_score"] / groups, 2)
        stats["avg_efficiency"] = round(stats["avg_efficiency"] / groups, 2)
        stats["avg_std_dev"] = round(stats["avg_std_dev"] / groups, 3)

    return {
        "tiered_groups": tiered_results,
        "tier_stats": tier_stats,
        "total_tiers": k,
        "total_groups": total_groups,
        "target_efficiency": target_efficiency,
        "tier_boundaries": tier_boundaries
    }


def print_enhanced_tiering(tiering):
    """Print enhanced tiering results with detailed statistics"""
    print("\n" + "=" * 100)
    print(f"{'ENHANCED TIERED RANKINGS':^100}")
    print(
        f"{'Target: ' + str(int(tiering['target_efficiency'] * 100)) + '% efficiency with progressive volume scaling':^100}"
    )
    print(
        f"{'Groups: ' + str(tiering['total_groups']) + ' | Tiers: ' + str(tiering['total_tiers']):^100}"
    )
    print("=" * 100)

    unique_tiers = sorted(
        set(group['tier'] for group in tiering['tiered_groups']))

    for tier in unique_tiers:
        tier_groups = [
            g for g in tiering['tiered_groups'] if g['tier'] == tier
        ]
        tier_stats = tiering['tier_stats'][tier]

        print(f"\n{f'TIER {tier}':=^100}")
        print(f"Groups: {tier_stats['groups']} | "
              f"Avg Score: {tier_stats['avg_score']:.1f} | "
              f"Avg Efficiency: {tier_stats['avg_efficiency']}% | "
              f"Avg StdDev: {tier_stats['avg_std_dev']:.3f} | "
              f"Total Releases: {tier_stats['total_releases']}")
        print("-" * 100)

        # Column headers
        print(
            f"{'Group':<25} {'Score':>8} {'Efficiency':>10} {'Delta%':>8} {'StdDev':>8} {'Releases':>8}"
        )
        print("-" * 100)

        # Sort groups within tier by score
        for group in sorted(tier_groups,
                            key=lambda x: x['score'],
                            reverse=True):
            print(
                f"{group['name']:<25} "
                f"{group['score']:>8.1f} "
                f"{group['efficiency']:>9}% "
                f"{abs(group['efficiency'] - (tiering['target_efficiency'] * 100)):>8.1f} "  # Fixed delta calculation
                f"{group['std_dev']:>8.3f} "
                f"{group['releases']:>8}")


def main():
    # Parse command line arguments
    args = parse_args()
    target_efficiency = args.target

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
    enhanced_tiering = analyze_tiers_enhanced(
        results, target_efficiency=target_efficiency)

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
            "total_tiers": enhanced_tiering["total_tiers"]
        },
        "tier_statistics": enhanced_tiering["tier_stats"],
        "tiered_groups": enhanced_tiering["tiered_groups"],
        "tier_boundaries": enhanced_tiering["tier_boundaries"]
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
