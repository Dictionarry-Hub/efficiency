import regex as re
import json
import yaml


def analyze_releases(entries):
    # First pass - get average remux size
    remux_sizes = []
    release_data = {}  # Dictionary to store all release information

    # First pass for remux sizes
    for entry in entries:
        title = entry.get('title', '')
        size = entry.get('size', 0)

        # Check quality source
        quality_info = entry.get('quality', {}).get('quality', {})
        source = quality_info.get('source', '').lower()

        pattern_1080p = re.compile(r'1080p', re.IGNORECASE)
        pattern_remux = re.compile(r'remux', re.IGNORECASE)
        pattern_extras = re.compile(r'extras', re.IGNORECASE)

        has_1080p = bool(pattern_1080p.search(title))
        has_remux = bool(pattern_remux.search(title))
        has_extras = bool(pattern_extras.search(title))

        if has_1080p and has_remux and not has_extras:
            size_gb = size / (1024 * 1024 * 1024)
            remux_sizes.append(size_gb)

    if not remux_sizes:
        print("No remux files found for comparison")
        return

    average_remux_size = sum(remux_sizes) / len(remux_sizes)
    print(f"Average remux size: {average_remux_size:.2f} GB")

    # Second pass - analyze non-remux releases
    for entry in entries:
        title = entry.get('title', '')
        size = entry.get('size', 0)
        release_group = entry.get('releaseGroup', 'UNKNOWN')

        # Check quality source
        quality_info = entry.get('quality', {}).get('quality', {})
        source = quality_info.get('source', '').lower()

        has_1080p = bool(pattern_1080p.search(title))
        has_remux = bool(pattern_remux.search(title))
        has_extras = bool(pattern_extras.search(title))

        # Look for non-remux, non-extras, non-webdl 1080p releases
        if has_1080p and not has_remux and not has_extras and source != 'webdl':
            size_gb = size / (1024 * 1024 * 1024)
            efficiency = (size_gb / average_remux_size) * 100

            # Store release information
            if release_group not in release_data:
                release_data[release_group] = {
                    'releases': [],
                    'efficiencies': [],
                    'average_efficiency': 0
                }

            release_data[release_group]['releases'].append({
                'title':
                title,
                'size_gb':
                round(size_gb, 2),
                'efficiency':
                round(efficiency, 1)
            })
            release_data[release_group]['efficiencies'].append(efficiency)

    # Calculate averages and prepare output data
    output_data = {
        'average_remux_size_gb': round(average_remux_size, 2),
        'release_groups': {}
    }

    # Sort release groups by average efficiency
    for group in release_data:
        efficiencies = release_data[group]['efficiencies']
        release_data[group]['average_efficiency'] = sum(efficiencies) / len(
            efficiencies)

    sorted_groups = sorted(release_data.items(),
                           key=lambda x: x[1]['average_efficiency'])

    # Prepare and display sorted data
    for group, data in sorted_groups:
        avg_efficiency = data['average_efficiency']
        output_data['release_groups'][group] = {
            'average_efficiency_percent': round(avg_efficiency, 1),
            'number_of_releases': len(data['releases']),
            'releases': sorted(data['releases'], key=lambda x: x['efficiency'])
        }

        # Print to console
        print(f"\n{group}:")
        print(
            f"Average efficiency: {avg_efficiency:.1f}% from {len(data['releases'])} releases"
        )
        print("Releases:")
        for release in data['releases']:
            print(f"  - {release['title']}")
            print(f"    Size: {release['size_gb']:.2f} GB")
            print(f"    Efficiency: {release['efficiency']:.1f}%")

    # Save to YAML file
    with open('release_analysis.yml', 'w') as file:
        yaml.dump(output_data, file, sort_keys=False, default_flow_style=False)


# Read the JSON file
try:
    with open('Barbie.json', 'r') as file:
        data = json.load(file)

    if isinstance(data, dict):
        data = [data]

    analyze_releases(data)
    print("\nAnalysis has been saved to release_analysis.yml")

except FileNotFoundError:
    print("Error: JSON file not found")
except json.JSONDecodeError:
    print("Error: Invalid JSON format")
