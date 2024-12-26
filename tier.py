#!/usr/bin/env python3

import sys
import yaml
import numpy as np
from sklearn.cluster import KMeans
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Create tiered rankings based on desired efficiency")
    parser.add_argument("desired_efficiency",
                        type=float,
                        help="The target efficiency value")
    parser.add_argument("-k",
                        "--tiers",
                        type=int,
                        default=5,
                        help="Number of tiers to create (default: 5)")
    args = parser.parse_args()

    if args.tiers < 2:
        print("Number of tiers must be at least 2")
        sys.exit(1)

    # Read YAML from stdin
    data = yaml.safe_load(sys.stdin)

    # Extract groups and efficiencies, skipping the 'ranking' key
    groups = []
    efficiencies = []
    for group, efficiency in data['ranking'].items():
        groups.append(group)
        efficiencies.append(efficiency)

    # Calculate distances from desired efficiency
    distances = np.abs(np.array(efficiencies) - args.desired_efficiency)
    X = distances.reshape(-1, 1)

    # Perform k-means clustering on the distances
    kmeans = KMeans(n_clusters=args.tiers, random_state=42)
    labels = kmeans.fit_predict(X)

    # Get cluster centers (these are distance centers)
    centers = kmeans.cluster_centers_.flatten()

    # Order clusters by distance from desired efficiency (smallest to largest)
    cluster_order = np.argsort(centers)

    # Create dictionary of tiers
    tiers = {}
    for tier_idx, cluster_idx in enumerate(cluster_order):
        tier_groups = []
        avg_distance = centers[cluster_idx]

        # Find all groups in this cluster
        for group, efficiency, distance, label in zip(groups, efficiencies,
                                                      distances, labels):
            if label == cluster_idx:
                tier_groups.append((group, efficiency, distance))

        # Sort groups within tier by distance (closest to desired_efficiency first)
        tier_groups.sort(key=lambda x: x[2])

        # Store in tiers dictionary
        tier_num = tier_idx + 1
        tiers[tier_num] = {
            'average_distance': float(avg_distance),
            'groups': [(group, eff) for group, eff, _ in tier_groups]
        }

    # Print results
    print(
        f"\nTiers (ordered by closeness to desired efficiency {args.desired_efficiency}):\n"
    )
    for tier_num, tier_data in tiers.items():
        print(
            f"Tier {tier_num} (avg distance from target: {tier_data['average_distance']:.2f}):"
        )
        for group, eff in tier_data['groups']:
            print(
                f"    {group}: {eff:.2f} ({abs(eff - args.desired_efficiency):.2f} away)"
            )
        print()


if __name__ == "__main__":
    main()
