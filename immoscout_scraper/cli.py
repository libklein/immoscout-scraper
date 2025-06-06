import asyncio
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from furl import furl
from rnet import Client, Impersonate

from immoscout_scraper.db import PropertyDatabase
from immoscout_scraper.scrape import ImmoscoutScraper
from immoscout_scraper.url_conversion import convert_web_to_mobile
from immoscout_scraper.models import RawListing, PropertyModel, parse_property

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
        Optional[Path],
        typer.Option(
            "--output-path",
            "-o",
            help="Path to the SQLite database file",
            envvar="IMMOSCOUT_SCRAPER_OUTPUT_PATH",
        ),
    ] = None,
    max_requests_per_second: Annotated[
        int,
        typer.Option(
            "--max-requests-per-second",
            "-r",
            help="Maximum number of requests per second",
            envvar="IMMOSCOUT_SCRAPER_MAX_REQUESTS_PER_SECOND",
            min=1,
        ),
    ] = 16,
    max_pages: Annotated[
        int,
        typer.Option(
            "--max-pages",
            "-m",
            help="Maximum number of pages to scrape",
            envvar="IMMOSCOUT_SCRAPER_MAX_PAGES",
            min=1,
        ),
    ] = sys.maxsize,
) -> None:
    """Scrape rental properties from ImmoScout24 using the provided search URL."""

    # Set default output path if not provided
    if output_path is None:
        output_path = Path("properties.db")

    asyncio.run(_async_scrape(search_url, output_path, max_requests_per_second, max_pages))


async def _async_scrape(search_url: str, output_path: Path, max_requests_per_second: int, max_pages: int) -> None:
    """Async wrapper for the scraping logic."""

    typer.echo("Starting scraper with:")
    typer.echo(f"  Search URL: {search_url}")
    typer.echo(f"  Output path: {output_path}")
    typer.echo(f"  Max requests per second: {max_requests_per_second}")
    typer.echo(f"  Max pages: {max_pages}")
    # Initialize database and get existing IDs
    db = PropertyDatabase(output_path)
    existing_ids = db.fetch_saved_listing_ids()
    typer.echo(f"Already scraped {len(existing_ids)} listings.")

    # Create client and scraper
    client = create_client()
    scraper = ImmoscoutScraper(client, existing_ids, max_requests_per_second=max_requests_per_second)

    # Convert URL and start scraping
    mobile_url = convert_web_to_mobile(search_url)
    typer.echo(f"Converted URL to mobile format: {mobile_url}")

    try:
        new_properties = await scraper.scrape_listings(mobile_url, max_pages)

        # Save results
        db.save_listings(new_properties)
        typer.echo(f"Successfully scraped and saved {len(new_properties)} new properties!")

        for i in new_properties:
            property_data = parse_property(i.data)
            typer.echo(
                f"Property ID: {property_data.listing_id}, Title: {property_data.listing_title}, Address: {property_data.address}"
            )

    except Exception as e:
        typer.echo(f"Error during scraping: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
