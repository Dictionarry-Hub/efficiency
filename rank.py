#!/usr/bin/env python3

import os
import yaml


def main():
    output_dir = "output"
    source_efficiencies = {}  # {source_name: [eff1, eff2, ...], ...}

    for filename in os.listdir(output_dir):
        if filename.endswith(".yml"):
            filepath = os.path.join(output_dir, filename)

            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if not data:
                    continue

            sources_dict = data.get("source", {})
            for source_name, source_data in sources_dict.items():
                eff_value = source_data.get("average_efficiency_percent", 0)

                # Store it for later averaging
                if source_name not in source_efficiencies:
                    source_efficiencies[source_name] = []
                source_efficiencies[source_name].append(eff_value)

    ranking_list = []
    for source_name, eff_list in source_efficiencies.items():
        if eff_list:
            avg_eff = sum(eff_list) / len(eff_list)
        else:
            avg_eff = 0
        ranking_list.append((source_name, avg_eff))

    ranking_list.sort(key=lambda x: x[1], reverse=True)

    ranking_dict = {}
    for source_name, eff_val in ranking_list:
        ranking_dict[source_name] = round(eff_val, 2)

    with open("ranking.yml", "w", encoding="utf-8") as f:
        yaml.safe_dump({"ranking": ranking_dict},
                       f,
                       sort_keys=False,
                       default_flow_style=False)

    # 8. Print the results to the console in a simple numbered list
    print("\nOverall Ranking (Most Efficient to Least Efficient):\n")
    for i, (source_name, eff_val) in enumerate(ranking_list, start=1):
        print(f"{i}. {source_name}: {eff_val:.2f}")


if __name__ == "__main__":
    main()
