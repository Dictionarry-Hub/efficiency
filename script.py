import regex as re
import json
import yaml
import requests
from urllib.parse import urljoin


def get_streaming_patterns():
    """
    Fetch streaming service regex patterns from GitHub repository or load from local cache
    """
    import os
    from datetime import datetime, timedelta
    from pathlib import Path

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
                print("Loading patterns from local cache")
                with open(cache_file, 'r') as f:
                    return yaml.safe_load(f)
            else:
                print("Cache is older than 24 hours, refreshing from GitHub")
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
        print("Saving patterns to cache")
        with open(cache_file, 'w') as f:
            yaml.dump(patterns, f)

        # Save cache metadata
        with open(cache_metadata, 'w') as f:
            yaml.dump({'last_update': datetime.now().isoformat()}, f)

        print(
            f"Successfully cached {len(patterns)} streaming service patterns")
        return patterns

    except Exception as e:
        print(f"Error fetching patterns: {str(e)}")

        # If we have a cache file, try to use it as fallback
        if cache_file.exists():
            print("Falling back to existing cache due to error")
            try:
                with open(cache_file, 'r') as f:
                    return yaml.safe_load(f)
            except Exception as cache_e:
                print(f"Error reading cache: {str(cache_e)}")

        return {}


def analyze_releases(entries):
    # First pass - get average remux size
    remux_sizes = []
    release_data = {}
    streaming_data = {}

    pattern_1080p = re.compile(r'1080p', re.IGNORECASE)
    pattern_remux = re.compile(r'remux', re.IGNORECASE)
    pattern_extras = re.compile(r'extras', re.IGNORECASE)
    pattern_webdl = re.compile(r'web-?dl', re.IGNORECASE)
    pattern_h265 = re.compile(r'(?i)h\s*\.?\s*265')

    # Get streaming service patterns
    streaming_patterns = get_streaming_patterns()
    compiled_patterns = {
        name: re.compile(pattern, re.IGNORECASE)
        for name, pattern in streaming_patterns.items()
    }

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

    x265_pattern = re.compile(
        r'^(?!.*(?i:remux))(?=.*(\b[x]\s?(\.?265)\b|HEVC|\bDS4K\b)).*$')

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
            for service_name, pattern in compiled_patterns.items():
                if pattern.search(title):
                    # Add codec suffix to service name
                    service_key = f"{service_name} (H.265)" if is_h265 else f"{service_name} (H.264)"
                    detected_service = service_key
                    break

            if detected_service:
                if detected_service not in streaming_data:
                    streaming_data[detected_service] = {
                        'releases': [],
                        'efficiencies': [],
                        'average_efficiency': 0
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

    # Calculate averages and prepare output data
    output_data = {
        'average_remux_size_gb': round(average_remux_size, 2),
        'source': {}  # Single dictionary for all sources
    }

    # Process and combine both release groups and streaming services
    all_sources = {}

    # Add release groups
    for group, data in release_data.items():
        efficiencies = data['efficiencies']
        avg_efficiency = sum(efficiencies) / len(efficiencies)
        all_sources[group] = {
            'average_efficiency_percent': round(avg_efficiency, 1),
            'number_of_releases': len(data['releases']),
            'releases': sorted(data['releases'], key=lambda x: x['efficiency'])
        }

    # Add streaming services
    for service, data in streaming_data.items():
        efficiencies = data['efficiencies']
        avg_efficiency = sum(efficiencies) / len(efficiencies)
        all_sources[service] = {
            'average_efficiency_percent': round(avg_efficiency, 1),
            'number_of_releases': len(data['releases']),
            'releases': sorted(data['releases'], key=lambda x: x['efficiency'])
        }

    # Sort all sources by average efficiency
    sorted_sources = sorted(all_sources.items(),
                            key=lambda x: x[1]['average_efficiency_percent'])

    # Add to output data
    for source, data in sorted_sources:
        output_data['source'][source] = data

    # Save to YAML file
    with open('release_analysis.yml', 'w') as file:
        yaml.dump(output_data, file, sort_keys=False, default_flow_style=False)


# Read the JSON file
if __name__ == "__main__":
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
