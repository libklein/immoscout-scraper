# immoscout-scraper

[![Release](https://img.shields.io/github/v/release/libklein/immoscout-scraper)](https://img.shields.io/github/v/release/libklein/immoscout-scraper)
[![Build status](https://img.shields.io/github/actions/workflow/status/libklein/immoscout-scraper/main.yml?branch=main)](https://github.com/libklein/immoscout-scraper/actions/workflows/main.yml?query=branch%3Amain)
[![License](https://img.shields.io/github/license/libklein/immoscout-scraper)](https://img.shields.io/github/license/libklein/immoscout-scraper)

Scrapes rental properties listed on <www.immoscout24.de>

- **Github repository**: <https://github.com/libklein/immoscout-scraper/>

## Installation

### Using uv (recommended)

```bash
git clone https://github.com/libklein/immoscout-scraper.git
cd immoscout-scraper
uv sync
```

### Using pip

```bash
pip install immoscout-scraper
```

## Usage

### Command Line Interface

The scraper provides a command-line interface with support for arguments and environment variables.

#### Basic Usage

```bash
# Using uv
uv run immoscout-scraper "https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten"

# If installed via pip
immoscout-scraper "https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten"
```

#### With Options

```bash
immoscout-scraper \
  "https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten" \
  --output-path ./my-properties.db \
  --max-requests-per-second 10 \
  --max-pages 5
```

### Environment Variables

All CLI arguments can be configured using environment variables with the `IMMOSCOUT_SCRAPER_` prefix:

| Environment Variable | CLI Argument | Default | Description |
|---------------------|--------------|---------|-------------|
| `IMMOSCOUT_SCRAPER_SEARCH_URL` | `search_url` | *required* | ImmoScout24 search URL to scrape |
| `IMMOSCOUT_SCRAPER_OUTPUT_PATH` | `--output-path` | `properties.db` | Path to SQLite database file |
| `IMMOSCOUT_SCRAPER_MAX_REQUESTS_PER_SECOND` | `--max-requests-per-second` | `16` | Rate limit for API requests |
| `IMMOSCOUT_SCRAPER_MAX_PAGES` | `--max-pages` | `unlimited` | Maximum number of pages to scrape |
| `IMMOSCOUT_SCRAPER_CHUNKSIZE` | `--chunksize` | 100 | Save eagerly after scraping this many properties |

## Docker Usage

```bash
docker run --rm \
  -v $(pwd)/data:/out \
  libklein/immoscout-scraper \
  "https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten"
```

### Using Environment Variables

```bash
docker run --rm \
  -v $(pwd)/data:/out \
  -e IMMOSCOUT_SCRAPER_SEARCH_URL="https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten" \
  -e IMMOSCOUT_SCRAPER_MAX_PAGES="20" \
  libklein/immoscout-scraper
```

### Docker Compose Example

```yaml
version: '3.8'
services:
  scraper:
    image: libklein/immoscout-scraper
    environment:
      - IMMOSCOUT_SCRAPER_SEARCH_URL=https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten
      - IMMOSCOUT_SCRAPER_MAX_REQUESTS_PER_SECOND=16
      - IMMOSCOUT_SCRAPER_MAX_PAGES=20
    volumes:
      - ./data:/out
```

### Docker Environment Variables

The Docker container comes with the following pre-configured environment variables:

- `IMMOSCOUT_SCRAPER_OUTPUT_PATH=/out/properties.db` - Saves database to mounted volume
- `IMMOSCOUT_SCRAPER_MAX_REQUESTS_PER_SECOND=16` - Conservative rate limiting

## Development

### Setting Up Development Environment

1. Clone the repository:

```bash
git clone https://github.com/libklein/immoscout-scraper.git
cd immoscout-scraper
```

2. Install dependencies and pre-commit hooks:

```bash
make install
```

3. Run pre-commit hooks:

```bash
uv run pre-commit run -a
```

### Running Tests

```bash
uv run pytest
```

### Code Formatting

```bash
uv run ruff format
uv run ruff check --fix
```

## URL Requirements

- The scraper only accepts URLs from `www.immobilienscout24.de` domain
- URLs from `api.mobile.immobilienscout24.de` are not accepted (these are converted automatically)
- Search URLs should be in the format: `https://www.immobilienscout24.de/Suche/de/...`
