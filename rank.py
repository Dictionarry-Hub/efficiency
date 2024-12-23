#!/usr/bin/env python3

import os
import yaml


def main():
    output_dir = "output"
    source_efficiencies = {}  # {source_name: [eff1, eff2, ...], ...}

    # 1. Iterate over all .yml files in the output directory
    for filename in os.listdir(output_dir):
        if filename.endswith(".yml"):
            filepath = os.path.join(output_dir, filename)

            # 2. Load YAML data
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if not data:
                    continue

            # 3. Extract each source's average_efficiency_percent
            sources_dict = data.get("source", {})
            for source_name, source_data in sources_dict.items():
                eff_value = source_data.get("average_efficiency_percent", 0)

                # Store it for later averaging
                if source_name not in source_efficiencies:
                    source_efficiencies[source_name] = []
                source_efficiencies[source_name].append(eff_value)

    # 4. Compute overall average efficiency for each source
    ranking = []  # will store tuples of (source_name, overall_avg_eff)
    for source_name, eff_list in source_efficiencies.items():
        if eff_list:  # avoid division by zero if empty
            avg_eff = sum(eff_list) / len(eff_list)
        else:
            avg_eff = 0
        ranking.append((source_name, avg_eff))

    # 5. Sort by descending average efficiency
    ranking.sort(key=lambda x: x[1], reverse=True)

    # Prepare data for YAML
    # Example structure:
    # ranking:
    #   - source: ...
    #     average_efficiency: ...
    ranking_data = {"ranking": []}
    for source_name, eff_val in ranking:
        ranking_data["ranking"].append({
            "source": source_name,
            "average_efficiency": round(eff_val, 2)
        })

    # 6. Save ranking to ranking.yml
    with open("ranking.yml", "w", encoding="utf-8") as f:
        yaml.safe_dump(ranking_data,
                       f,
                       sort_keys=False,
                       default_flow_style=False)

    # 7. Also print the results to the console
    print("\nRanking of sources (most efficient to least efficient):\n")
    for item in ranking_data["ranking"]:
        print(f"{item['source']}: {item['average_efficiency']:.2f}")


if __name__ == "__main__":
    main()
