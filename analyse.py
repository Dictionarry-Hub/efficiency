import regex as re
import json
import yaml
import requests
from urllib.parse import urljoin
import os
from pathlib import Path
from datetime import datetime, timedelta


def get_streaming_patterns():
    """
    Fetch streaming service regex patterns from GitHub repository or load from local cache
    """
    # Create data directory if it doesn't exist
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)

    patterns = {}
    cache_file = data_dir / 'patterns_cache.yml'
    cache_metadata = data_dir / 'patterns_cache_metadata.yml'

    # Check if cache exists and is less than 24 hours old
    if cache_file.exists() and cache_metadata.exists():
        try:
            with open(cache_metadata, 'r') as f:
                metadata = yaml.safe_load(f)
            cache_time = datetime.fromisoformat(metadata['last_update'])

            if datetime.now() - cache_time < timedelta(hours=24):
                print("Loading streaming patterns from local cache.")
                with open(cache_file, 'r') as f:
                    return yaml.safe_load(f)
            else:
                print("Cache is older than 24 hours, refreshing from GitHub.")
        except Exception as e:
            print(f"Error reading cache: {str(e)}")

    # If we get here, we need to fetch from GitHub
    api_url = "https://api.github.com/repos/Dictionarry-Hub/database/contents/regex_patterns"
    try:
        print("Fetching patterns from GitHub...")
        response = requests.get(api_url)
        response.raise_for_status()
        files = response.json()

        # Process each YAML file
        for file in files:
            if file['name'].endswith('.yml'):
                yml_path = data_dir / file['name']
                print(f"Processing {file['name']}")

                try:
                    # Download and save the file
                    content_response = requests.get(file['download_url'])
                    content_response.raise_for_status()

                    # Save raw file
                    with open(yml_path, 'w') as f:
                        f.write(content_response.text)

                    # Parse YAML content
                    yaml_content = yaml.safe_load(content_response.text)

                    # Check if this is a streaming service pattern
                    if 'tags' in yaml_content and 'Streaming Service' in yaml_content[
                            'tags']:
                        print(
                            f"Found streaming service pattern: {yaml_content['name']}"
                        )
                        patterns[
                            yaml_content['name']] = yaml_content['pattern']

                except Exception as e:
                    print(f"Error processing {file['name']}: {str(e)}")
                    continue

        # Save patterns to cache
        print("Saving streaming patterns to cache.")
        with open(cache_file, 'w') as f:
            yaml.dump(patterns, f)

        # Save cache metadata
        with open(cache_metadata, 'w') as f:
            yaml.dump({'last_update': datetime.now().isoformat()}, f)

        print(
            f"Successfully cached {len(patterns)} streaming service patterns.")
        return patterns

    except Exception as e:
        print(f"Error fetching patterns: {str(e)}")

        # If we have a cache file, try to use it as fallback
        if cache_file.exists():
            print("Falling back to existing cache due to error.")
            try:
                with open(cache_file, 'r') as f:
                    return yaml.safe_load(f)
            except Exception as cache_e:
                print(f"Error reading cache: {str(cache_e)}")

        return {}


def get_remux_average_size(entries):
    """
    Returns the average size (in GB) of REMUX 1080p files (excluding extras).
    """
    remux_sizes = []

    pattern_1080p = re.compile(r'1080p', re.IGNORECASE)
    pattern_remux = re.compile(r'remux', re.IGNORECASE)
    pattern_extras = re.compile(r'extras', re.IGNORECASE)

    for entry in entries:
        title = entry.get('title', '')
        size = entry.get('size', 0)

        has_1080p = bool(pattern_1080p.search(title))
        has_remux = bool(pattern_remux.search(title))
        has_extras = bool(pattern_extras.search(title))

        if has_1080p and has_remux and not has_extras:
            size_gb = size / (1024 * 1024 * 1024)
            remux_sizes.append(size_gb)

    if not remux_sizes:
        return None  # or 0, or raise an exception

    return sum(remux_sizes) / len(remux_sizes)


def parse_release_groups(entries, average_remux_size):
    """
    Parse non-remux 1080p releases (excluding extras and webdl).
    Calculates relative efficiency and groups by release group.
    Returns a dictionary of results for release groups.
    """
    if average_remux_size is None:
        return {}  # can't parse if no average

    release_data = {}

    pattern_1080p = re.compile(r'1080p', re.IGNORECASE)
    pattern_remux = re.compile(r'remux', re.IGNORECASE)
    pattern_extras = re.compile(r'extras', re.IGNORECASE)

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

            if release_group not in release_data:
                release_data[release_group] = {
                    'releases': [],
                    'efficiencies': []
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

    return release_data


def parse_streaming_services(entries, average_remux_size, streaming_patterns):
    """
    Parse 1080p WEB-DL releases, match against known streaming services,
    and calculate relative efficiency.
    Returns a dictionary of streaming service data.
    """
    if average_remux_size is None:
        return {}

    streaming_data = {}

    # Pre-compile patterns
    pattern_1080p = re.compile(r'1080p', re.IGNORECASE)
    pattern_webdl = re.compile(r'web-?dl', re.IGNORECASE)
    pattern_extras = re.compile(r'extras', re.IGNORECASE)
    pattern_h265 = re.compile(r'(?i)h\s*\.?\s*265')
    x265_pattern = re.compile(
        r'^(?!.*(?i:remux))(?=.*(\b[x]\s?(\.?265)\b|HEVC|\bDS4K\b)).*$')

    # Compile streaming service patterns
    compiled_patterns = {
        name: re.compile(pattern, re.IGNORECASE)
        for name, pattern in streaming_patterns.items()
    }

    for entry in entries:
        title = entry.get('title', '')
        size = entry.get('size', 0)

        # Skip if it's an x265 encode
        if x265_pattern.search(title):
            continue

        has_1080p = bool(pattern_1080p.search(title))
        has_webdl = bool(pattern_webdl.search(title))
        has_extras = bool(pattern_extras.search(title))
        is_h265 = bool(pattern_h265.search(title))

        if has_1080p and has_webdl and not has_extras:
            size_gb = size / (1024 * 1024 * 1024)
            efficiency = (size_gb / average_remux_size) * 100

            # Check for streaming service patterns
            detected_service = None
            for service_name, service_pattern in compiled_patterns.items():
                if service_pattern.search(title):
                    # Add codec suffix to service name
                    service_key = f"{service_name} (H.265)" if is_h265 else f"{service_name} (H.264)"
                    detected_service = service_key
                    break

            if detected_service:
                if detected_service not in streaming_data:
                    streaming_data[detected_service] = {
                        'releases': [],
                        'efficiencies': []
                    }

                streaming_data[detected_service]['releases'].append({
                    'title':
                    title,
                    'size_gb':
                    round(size_gb, 2),
                    'efficiency':
                    round(efficiency, 1)
                })
                streaming_data[detected_service]['efficiencies'].append(
                    efficiency)

    return streaming_data


def analyze_releases(entries):
    """
    Main function to orchestrate analysis:
    - Fetch streaming patterns
    - Get average remux size
    - Parse release groups (non-remux encodes)
    - Parse streaming services (WEB-DL)
    - Combine and save to a dict
    """
    # Get streaming service patterns
    streaming_patterns = get_streaming_patterns()

    # 1) Get average REMUX size
    average_remux_size = get_remux_average_size(entries)
    if average_remux_size is None:
        print(
            "No valid REMUX entries found. Cannot compute average. Returning.")
        return {'average_remux_size_gb': 0, 'source': {}}

    print(f"Average REMUX size: {average_remux_size:.2f} GB")

    # 2) Parse release groups
    release_data = parse_release_groups(entries, average_remux_size)

    # 3) Parse streaming services
    streaming_data = parse_streaming_services(entries, average_remux_size,
                                              streaming_patterns)

    # Combine results
    output_data = {
        'average_remux_size_gb': round(average_remux_size, 2),
        'source': {}
    }

    # Merge both dictionaries (release_data, streaming_data) into one "source" dict
    all_sources = {}

    # Add release groups
    for group, data in release_data.items():
        efficiencies = data['efficiencies']
        avg_eff = sum(efficiencies) / len(efficiencies) if efficiencies else 0
        all_sources[group] = {
            'average_efficiency_percent': round(avg_eff, 1),
            'number_of_releases': len(data['releases']),
            'releases': sorted(data['releases'], key=lambda x: x['efficiency'])
        }

    # Add streaming services
    for service, data in streaming_data.items():
        efficiencies = data['efficiencies']
        avg_eff = sum(efficiencies) / len(efficiencies) if efficiencies else 0
        all_sources[service] = {
            'average_efficiency_percent': round(avg_eff, 1),
            'number_of_releases': len(data['releases']),
            'releases': sorted(data['releases'], key=lambda x: x['efficiency'])
        }

    # Sort combined sources by average efficiency
    sorted_sources = sorted(all_sources.items(),
                            key=lambda x: x[1]['average_efficiency_percent'])

    for source, data in sorted_sources:
        output_data['source'][source] = data

    return output_data


def main():
    """
    Main execution:
    - Iterate all .json files in `./input`
    - For each, load the JSON data, analyze, and save as .yml in `./output`
    """
    input_dir = Path('input')
    output_dir = Path('output')

    # Ensure output directory exists
    output_dir.mkdir(exist_ok=True)

    # Gather all .json files in the input directory
    json_files = list(input_dir.glob("*.json"))
    if not json_files:
        print("No JSON files found in the 'input' directory.")
        return

    for json_file in json_files:
        print(f"\nProcessing file: {json_file.name}")
        try:
            with open(json_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except FileNotFoundError:
            print(f"Error: File {json_file.name} not found.")
            continue
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON format in file {json_file.name}.")
            continue

        # Ensure data is a list
        if isinstance(data, dict):
            data = [data]

        # Analyze releases
        result = analyze_releases(data)

        # Create output filename
        output_filename = json_file.stem + '.yml'
        output_path = output_dir / output_filename

        # Save analysis to .yml
        with open(output_path, 'w', encoding='utf-8') as out_file:
            yaml.dump(result,
                      out_file,
                      sort_keys=False,
                      default_flow_style=False)

        print(f"Analysis has been saved to {output_path}")


if __name__ == "__main__":
    main()
