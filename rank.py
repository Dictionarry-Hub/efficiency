#!/usr/bin/env python3

import os
import yaml
import argparse
import sys
import regex as re


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
        "-S",
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
    parser.add_argument(
        "-C",
        "--codec",
        help=
        "Filter to only include sources that have at least one release in the specified codec (h264/h265/av1).",
        type=str,
        choices=["h264", "h265", "av1"],
        default=None,
    )
    parser.add_argument(
        "-H",
        "--hdr",
        help=
        "Include HDR releases (Dolby Vision, HDR10, HDR10+). If not specified, only SDR releases are included.",
        action="store_true",
    )
    parser.add_argument(
        "-O",
        "--order",
        help=
        "Sort results by: efficiency (e), releases (r), or alphabetical (a)",
        type=str,
        choices=["e", "r", "a"],
        default="e",
    )
    args = parser.parse_args()

    output_dir = "output"
    source_data_dict = {}

    # Regex patterns for QxR or TAoE (case-insensitive)
    pattern_qxr = re.compile(r"qxr", re.IGNORECASE)
    pattern_taoe = re.compile(r"taoe", re.IGNORECASE)

    # Regex patterns for codecs
    pattern_h265_1 = re.compile(r"(?i)h\s*\.?\s*265")
    pattern_h265_2 = re.compile(
        r"^(?!.*(?i:remux))(?=.*(\b[x]\s?(\.?265)\b|HEVC|\bDS4K\b)).*$")
    pattern_av1 = re.compile(r"\bAV1\b")

    # HDR patterns
    pattern_dolby_vision = re.compile(
        r"\b(dv(?![ .](HLG|SDR))|dovi|dolby[ .]?vision)\b", re.IGNORECASE)
    pattern_hdr10 = re.compile(
        r"(?<=^(?!.*\b(HLG|PQ|SDR)(\b|\d)).*?)HDR(?!((10)?(\+|P(lus)?)))",
        re.IGNORECASE)
    pattern_hdr10_plus = re.compile(
        r"(?<=^(?!.*\b(HLG|PQ|SDR)(\b|\d)).*?)HDR10(\+|P(lus)?)",
        re.IGNORECASE)

    def detect_codec(title):
        """
        Returns 'h265' if the title matches either h265 regex,
        'av1' if it matches AV1, otherwise 'h264'.
        """
        if pattern_h265_1.search(title) or pattern_h265_2.search(title):
            return "h265"
        elif pattern_av1.search(title):
            return "av1"
        else:
            return "h264"

    def detect_hdr(title):
        """
        Returns True if the title contains any HDR format (DV, HDR10, or HDR10+),
        False otherwise.
        """
        return bool(
            pattern_dolby_vision.search(title) or pattern_hdr10.search(title)
            or pattern_hdr10_plus.search(title))

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

                    # If we haven't seen this source before, initialize
                    if s_name not in source_data_dict:
                        source_data_dict[s_name] = {
                            "efficiencies": [],
                            "releases": []
                        }

                    # Handle normal sources
                    if s_name.upper() != "UNKNOWN":
                        # Save top-level efficiency
                        source_data_dict[s_name]["efficiencies"].append(
                            eff_value)
                        # Detect codec and HDR for each release
                        for rel in releases:
                            title = rel.get("title", "")
                            rel_codec = detect_codec(title)
                            rel_is_hdr = detect_hdr(title)
                            rel["codec"] = rel_codec
                            rel["is_hdr"] = rel_is_hdr
                        source_data_dict[s_name]["releases"].extend(releases)

                    # Handle UNKNOWN source: check for QxR or TAoE
                    else:
                        unknown_leftover_releases = []
                        for rel in releases:
                            title = rel.get("title", "")
                            # Check QxR or TAoE
                            if pattern_qxr.search(title):
                                if "QxR" not in source_data_dict:
                                    source_data_dict["QxR"] = {
                                        "efficiencies": [],
                                        "releases": []
                                    }
                                release_eff = rel.get("efficiency", 0)
                                source_data_dict["QxR"]["efficiencies"].append(
                                    release_eff)
                                # Detect codec and HDR
                                rel_codec = detect_codec(title)
                                rel_is_hdr = detect_hdr(title)
                                rel["codec"] = rel_codec
                                rel["is_hdr"] = rel_is_hdr
                                source_data_dict["QxR"]["releases"].append(rel)

                            elif pattern_taoe.search(title):
                                if "TAoE" not in source_data_dict:
                                    source_data_dict["TAoE"] = {
                                        "efficiencies": [],
                                        "releases": []
                                    }
                                release_eff = rel.get("efficiency", 0)
                                source_data_dict["TAoE"][
                                    "efficiencies"].append(release_eff)
                                rel_codec = detect_codec(title)
                                rel_is_hdr = detect_hdr(title)
                                rel["codec"] = rel_codec
                                rel["is_hdr"] = rel_is_hdr
                                source_data_dict["TAoE"]["releases"].append(
                                    rel)

                            else:
                                # Keep it in UNKNOWN
                                unknown_leftover_releases.append(rel)

                        # Now update UNKNOWN with leftover releases only
                        if unknown_leftover_releases:
                            source_data_dict[s_name]["efficiencies"].append(
                                eff_value)
                            # Detect codec for leftover releases
                            for rel in unknown_leftover_releases:
                                title = rel.get("title", "")
                                rel_codec = detect_codec(title)
                                rel_is_hdr = detect_hdr(title)
                                rel["codec"] = rel_codec
                                rel["is_hdr"] = rel_is_hdr
                            source_data_dict[s_name]["releases"].extend(
                                unknown_leftover_releases)

    # If -S/--source is used, display info and exit
    if args.source:
        s_name = args.source
        if s_name not in source_data_dict:
            print(f"Source '{s_name}' not found in collected data.")
            sys.exit(1)

        releases_list = source_data_dict[s_name]["releases"]

        # Apply codec filter if specified
        if args.codec:
            releases_list = [
                rel for rel in releases_list
                if rel.get("codec", "") == args.codec.lower() and
                (args.hdr or not rel.get("is_hdr", False)
                 )  # Include HDR only if --hdr is set
            ]

        # Calculate average efficiency from filtered releases
        avg_eff = sum(rel.get("efficiency", 0) for rel in releases_list) / len(
            releases_list) if releases_list else 0

        print(f"\nInformation for source: '{s_name}'")
        print(f"  - Average Efficiency: {avg_eff:.2f}")
        print(f"  - All Releases ({len(releases_list)}):")
        for rel in releases_list:
            title = rel.get("title", "")
            size_gb = rel.get("size_gb", "")
            eff = rel.get("efficiency", "")
            codec = rel.get("codec", "")
            is_hdr = rel.get("is_hdr", False)
            print(f"     * Title: {title}")
            print(f"       Size GB: {size_gb}")
            print(f"       Efficiency: {eff}")
            print(f"       Codec Detected: {codec}")
            print(f"       HDR: {is_hdr}")
        sys.exit(0)

    # Build initial ranking list
    ranking_list = []
    for s_name, s_info in source_data_dict.items():
        eff_list = s_info["efficiencies"]
        avg_eff = sum(eff_list) / len(eff_list) if eff_list else 0
        release_count = len(s_info["releases"])
        ranking_list.append((s_name, avg_eff, release_count))

    # Filter by codec and HDR first
    if args.codec:
        desired_codec = args.codec.lower()
        temp_list = []
        for (s_name, avg_eff, r_count) in ranking_list:
            releases_list = source_data_dict[s_name]["releases"]
            # Filter by codec and HDR status
            valid_releases = [
                rel for rel in releases_list
                if rel.get("codec", "") == desired_codec and
                (args.hdr or not rel.get("is_hdr", False)
                 )  # Include HDR only if --hdr is set
            ]
            if valid_releases:
                # Recalculate average efficiency and count based on filtered releases
                filtered_avg_eff = sum(
                    rel.get("efficiency", 0)
                    for rel in valid_releases) / len(valid_releases)
                temp_list.append(
                    (s_name, filtered_avg_eff, len(valid_releases)))
        ranking_list = temp_list

    # Now apply minimum release count filter after all other filters
    if args.lower is not None:
        ranking_list = [(s_name, avg_eff, r_count)
                        for (s_name, avg_eff, r_count) in ranking_list
                        if r_count >= args.lower]

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

    # Sort based on order parameter
    if args.order == "e":
        ranking_list.sort(key=lambda x: x[1],
                          reverse=True)  # Sort by efficiency
    elif args.order == "r":
        ranking_list.sort(key=lambda x: x[2],
                          reverse=True)  # Sort by release count
    else:  # "a" for alphabetical
        ranking_list.sort(key=lambda x: x[0].lower())  # Sort by name

    # Build the output filename based on provided flags
    filename_parts = ["ranking"]
    if args.range:
        filename_parts.append(f"R_{args.range}")
    if args.lower is not None:
        filename_parts.append(f"L_{args.lower}")
    if args.codec:
        filename_parts.append(f"C_{args.codec}")
    if args.hdr:
        filename_parts.append("HDR")
    if args.order != "e":  # Only add if not using default efficiency sort
        filename_parts.append(f"O_{args.order}")
    output_filename = "_".join(filename_parts) + ".yml"

    # Print filename being written
    print(f"\nSaving results to: {output_filename}")

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
