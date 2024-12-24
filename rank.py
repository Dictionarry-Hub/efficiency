#!/usr/bin/env python3

import os
import yaml
import argparse
import sys


def parse_range(range_string):
    try:
        lower_str, upper_str = range_string.split(":")
        lower_val = float(lower_str.strip())
        upper_val = float(upper_str.strip())
        return lower_val, upper_val
    except:
        raise ValueError(f"Invalid range format '{range_string}'. Use 'x:y'.")


def main():
    parser = argparse.ArgumentParser(
        description=
        "Gather efficiency data from YAML files and produce a ranking.")
    parser.add_argument(
        "-R",
        "--range",
        help="Filter to only sources whose average efficiency is within 'x:y'.",
        type=str,
        default=None,
    )
    parser.add_argument(
        "-s",
        "--source",
        help="Display detailed information about a specific source by name.",
        type=str,
        default=None,
    )
    parser.add_argument(
        "-L",
        "--lower",
        help=
        "Minimum number of releases a source must have to appear in the ranking.",
        type=int,
        default=None,
    )
    args = parser.parse_args()

    output_dir = "output"
    source_data_dict = {}

    # Read .yml files from the output directory
    for filename in os.listdir(output_dir):
        if filename.endswith(".yml"):
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if not data:
                    continue

                sources_dict = data.get("source", {})
                for s_name, s_info in sources_dict.items():
                    eff_value = s_info.get("average_efficiency_percent", 0)
                    releases = s_info.get("releases", [])

                    if s_name not in source_data_dict:
                        source_data_dict[s_name] = {
                            "efficiencies": [],
                            "releases": []
                        }

                    source_data_dict[s_name]["efficiencies"].append(eff_value)

                    if isinstance(releases, list):
                        # Store releases in a list
                        source_data_dict[s_name]["releases"].extend(releases)

    # If -s/--source is used, display info about that single source
    if args.source:
        s_name = args.source
        if s_name not in source_data_dict:
            print(f"Source '{s_name}' not found in collected data.")
            sys.exit(1)

        eff_list = source_data_dict[s_name]["efficiencies"]
        avg_eff = sum(eff_list) / len(eff_list) if eff_list else 0
        releases_list = source_data_dict[s_name]["releases"]

        print(f"\nInformation for source: '{s_name}'")
        print(f"  - Average Efficiency: {avg_eff:.2f}")
        print(f"  - All Releases ({len(releases_list)}):")
        for rel in releases_list:
            title = rel.get("title", "")
            size_gb = rel.get("size_gb", "")
            eff = rel.get("efficiency", "")
            print(f"     * Title: {title}")
            print(f"       Size GB: {size_gb}")
            print(f"       Efficiency: {eff}")
        sys.exit(0)

    # Otherwise, calculate and output the overall ranking
    ranking_list = []
    for s_name, s_info in source_data_dict.items():
        eff_list = s_info["efficiencies"]
        avg_eff = sum(eff_list) / len(eff_list) if eff_list else 0
        release_count = len(s_info["releases"])
        ranking_list.append((s_name, avg_eff, release_count))

    # Filter by minimum number of releases if -L/--lower is set
    if args.lower is not None:
        ranking_list = [(s_name, avg_eff, r_count)
                        for (s_name, avg_eff, r_count) in ranking_list
                        if r_count >= args.lower]

    # Sort in descending order by average efficiency
    ranking_list.sort(key=lambda x: x[1], reverse=True)

    # If a range filter is given, apply it
    if args.range:
        try:
            lower_val, upper_val = parse_range(args.range)
        except ValueError as e:
            print(e)
            sys.exit(1)
        ranking_list = [(s_name, eff, r_count)
                        for (s_name, eff, r_count) in ranking_list
                        if lower_val <= eff <= upper_val]

    # Build the output filename based on provided flags
    filename_parts = ["ranking"]
    if args.range:
        filename_parts.append(f"R_{args.range}")
    if args.lower is not None:
        filename_parts.append(f"L_{args.lower}")
    output_filename = "_".join(filename_parts) + ".yml"

    # Write final ranking to YAML
    ranking_dict = {
        s_name: round(avg_eff, 2)
        for (s_name, avg_eff, _) in ranking_list
    }
    with open(output_filename, "w", encoding="utf-8") as f:
        yaml.safe_dump({"ranking": ranking_dict},
                       f,
                       sort_keys=False,
                       default_flow_style=False)

    # Print the results to the console
    print("\nOverall Ranking (Most Efficient to Least Efficient):\n")
    if ranking_list:
        for i, (name, eff, r_count) in enumerate(ranking_list, start=1):
            print(f"{i}. {name}: {eff:.2f} (Releases: {r_count})")
    else:
        print("No sources found within the specified criteria.")


if __name__ == "__main__":
    main()
