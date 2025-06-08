import asyncio
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from furl import furl  # type: ignore[import-untyped]
from rnet import Client, Impersonate

from immoscout_scraper.db import PropertyDatabase
from immoscout_scraper.models import RawProperty, parse_property
from immoscout_scraper.scrape import ImmoscoutScraper
from immoscout_scraper.url_conversion import convert_web_to_mobile

app = typer.Typer(
    name="immoscout-scraper",
    help="Scrape rental properties from ImmoScout24",
    add_completion=False,
)


def create_client() -> Client:
    return Client(
        impersonate=Impersonate.OkHttp5,
        user_agent="ImmoScout24_1410_30_._",
        timeout=30,
    )


def validate_url(url: str) -> str:
    """Validate that the URL is from immobilienscout24.de domain."""
    parsed_url = furl(url)

    if parsed_url.host != "www.immobilienscout24.de":
        raise typer.BadParameter(f"URL must be from www.immobilienscout24.de domain, got: {parsed_url.host}")

    return url


@app.command()
def scrape(
    search_url: Annotated[
        str,
        typer.Argument(
            help="ImmoScout24 search URL to scrape",
            envvar="IMMOSCOUT_SCRAPER_SEARCH_URL",
            callback=lambda _, value: validate_url(value) if value else value,
        ),
    ],
    output_path: Annotated[
        Path,
        typer.Option(
            "--output-path",
            "-o",
            help="Path to the SQLite database file",
            envvar="IMMOSCOUT_SCRAPER_OUTPUT_PATH",
        ),
    ] = Path("properties.db"),
    max_requests_per_second: Annotated[
        int,
        typer.Option(
            "--max-requests-per-second",
            help="Maximum number of requests per second",
            envvar="IMMOSCOUT_SCRAPER_MAX_REQUESTS_PER_SECOND",
            min=1,
        ),
    ] = 16,
    max_pages: Annotated[
        Optional[int],
        typer.Option(
            "--max-pages",
            help="Maximum number of pages to scrape",
            envvar="IMMOSCOUT_SCRAPER_MAX_PAGES",
            min=1,
        ),
    ] = None,
    chunksize: Annotated[
        int,
        typer.Option(
            "--chunksize",
            help="Number of properties to save in one batch",
            envvar="IMMOSCOUT_SCRAPER_CHUNKSIZE",
            min=1,
        ),
    ] = 100,
    rescrape: Annotated[
        bool,
        typer.Option(
            "--rescrape",
            help="Ignore previously scraped properties and scrape all properties again",
            envvar="IMMOSCOUT_SCRAPER_RESCRAPE",
        ),
    ] = False,
) -> None:
    """Scrape rental properties from ImmoScout24 using the provided search URL."""

    # Set default output path if not provided
    if output_path is None:
        output_path = Path("properties.db")

    asyncio.run(
        _async_scrape(search_url, output_path, max_requests_per_second, max_pages or sys.maxsize, chunksize, rescrape)
    )


def save_properties(db: PropertyDatabase, raw_properties: list[RawProperty], upsert: bool = False) -> None:
    # Attempt to parse and save properties
    parsed_properties = []
    for raw_property in raw_properties:
        try:
            parsed_properties.append(parse_property(raw_property.data))
        except Exception as e:
            typer.echo(f"Error parsing property: {e}", err=True)

    if len(parsed_properties) != len(raw_properties):
        typer.echo(f"Failed to parse {len(raw_properties) - len(parsed_properties)} properties.", err=True)

    try:
        db.save_properties(parsed_properties, upsert=upsert)
    except Exception as e:
        typer.echo(f"Error saving parsed properties to database: {e}", err=True)

    # Finally, save raw properties. Order is important.
    try:
        db.save_raw_properties(raw_properties, upsert=upsert)
    except Exception as e:
        typer.echo(f"Error saving properties to database: {e}", err=True)


async def _async_scrape(
    search_url: str, output_path: Path, max_requests_per_second: int, max_pages: int, chunksize: int, rescrape: bool
) -> None:
    """Async wrapper for the scraping logic."""

    typer.echo("Starting scraper with:")
    typer.echo(f"  Search URL: {search_url}")
    typer.echo(f"  Output path: {output_path}")
    typer.echo(f"  Max requests per second: {max_requests_per_second}")
    typer.echo(f"  Max pages: {max_pages}")
    typer.echo(f"  Rescrape: {rescrape}")
    # Initialize database and get existing IDs
    db = PropertyDatabase(output_path)
    existing_ids = set()
    if not rescrape:
        existing_ids = db.fetch_saved_listing_ids()
        typer.echo(f"Already scraped {len(existing_ids)} listings.")
    else:
        typer.echo("Rescrape mode enabled: ignoring previously scraped listings.")

    # Create client and scraper
    client = create_client()
    scraper = ImmoscoutScraper(client, existing_ids, max_requests_per_second=max_requests_per_second)

    # Convert URL and start scraping
    mobile_url = convert_web_to_mobile(search_url)
    typer.echo(f"Converted URL to mobile format: {mobile_url}")

    try:
        listing_counts = await scraper.get_number_of_listings(mobile_url)
        number_of_pages_to_scrape = min(listing_counts.number_of_pages, max_pages)
        typer.echo(
            f"Found {listing_counts.total_listings} listings across {listing_counts.number_of_pages} pages. Scraping {number_of_pages_to_scrape} pages, estimated number of properties: {number_of_pages_to_scrape * listing_counts.page_size}."
        )

        total_scraped = 0
        raw_properties = []
        async for raw_property in scraper.scrape_listings(mobile_url, pages=number_of_pages_to_scrape):
            raw_properties.append(raw_property)
            total_scraped += 1
            if len(raw_properties) >= chunksize:
                save_properties(db, raw_properties, upsert=rescrape)
                raw_properties.clear()

        if raw_properties:
            save_properties(db, raw_properties, upsert=rescrape)

        typer.echo(f"Successfully scraped {total_scraped} new properties!")
        typer.echo(f"Results saved to {output_path}")

    except Exception as e:
        # Print stack trace
        typer.echo(f"Error during scraping: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
