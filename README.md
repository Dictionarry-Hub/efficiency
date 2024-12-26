# Release Efficiency Analyzer Test

Analyzes and ranks release groups based on their encoding efficiency.

## Usage

```bash
python rank.py [options]
```

## Parameters

| Parameter        | Description                   | Values        | Default | Example    |
| ---------------- | ----------------------------- | ------------- | ------- | ---------- |
| `-R`, `--range`  | Filter sources by efficiency  | `x:y` format  | None    | `-R 20:80` |
| `-S`, `--source` | Show detailed info for source | source name   | None    | `-s DON`   |
| `-L`, `--lower`  | Minimum releases required     | number        | None    | `-L 5`     |
| `-C`, `--codec`  | Filter by codec               | h264/h265/av1 | None    | `-C h265`  |
| `-H`, `--hdr`    | Include HDR releases          | flag          | False   | `-H`       |
| `-O`, `--order`  | Sort order                    | e/r/a         | e       | `-O r`     |

### Sort Options

- `e`: Sort by efficiency (default)
- `r`: Sort by number of releases
- `a`: Sort alphabetically by source name

## Examples

Show all h265 sources with 5+ releases, efficiency between 0-70:

```bash
python rank.py -L 5 -R 0:70 -C h265
```

Show detailed info for DON's h265 releases including HDR:

```bash
python rank.py -C h265 -H -s DON
```

Rank sources by number of releases:

```bash
python rank.py -L 5 -O r
```
