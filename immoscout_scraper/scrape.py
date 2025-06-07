import asyncio
import logging
import sys
from collections.abc import AsyncGenerator

from aiolimiter import AsyncLimiter
from rnet import Client, Response
from tenacity import retry, stop_after_attempt, wait_exponential

from immoscout_scraper.models import ListingID, RawProperty
from immoscout_scraper.url_conversion import get_expose_details_url, get_page_url

logging.basicConfig(level=logging.INFO)


def parse_listings_page(page_data: dict) -> set[ListingID]:
    results = page_data["resultListItems"]
    return {int(result_item["item"]["id"]) for result_item in results if result_item["type"] == "EXPOSE_RESULT"}


@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(5))
async def fetch_listing_page(client: Client, search_url: str, page: int) -> Response:
    return await client.post(get_page_url(search_url, page=page), json={"supportedResultListType": [], "userData": {}})


class ImmoscoutScraper:
    def __init__(
        self, client: Client, already_scraped: set[ListingID] | None = None, max_requests_per_second: int = 16
    ):
        self.client = client
        self.already_scraped = already_scraped or set()
        self.limiter = AsyncLimiter(max_requests_per_second, time_period=1)

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(5))
    async def handle_listing_details(self, listing_id: ListingID) -> RawProperty:
        async with self.limiter:
            data = await (await self.client.get(get_expose_details_url(listing_id))).json()
            # Mock implementation for the sake of example
            return RawProperty(listing_id=data["header"]["id"], data=data)

    async def handle_listing_page(self, search_url: str, page: int) -> AsyncGenerator[RawProperty, None]:
        response: Response = await fetch_listing_page(self.client, search_url, page)

        listing_ids = parse_listings_page(await response.json())
        listing_ids_to_scrape = listing_ids - self.already_scraped

        # Request pages - should return any results as soon as it is available
        async with self.limiter:
            scrape_tasks = [
                asyncio.create_task(self.handle_listing_details(listing_id)) for listing_id in listing_ids_to_scrape
            ]
            for listing_page in asyncio.as_completed(scrape_tasks):
                yield (await listing_page)

    async def scrape_listings(self, search_url: str, max_pages: int = sys.maxsize) -> AsyncGenerator[RawProperty, None]:
        # Make first request to get starting page and page count
        response: Response = await fetch_listing_page(self.client, search_url, page=1)
        page_data = await response.json()

        total_results = page_data["totalResults"]
        total_pages = page_data["numberOfPages"]
        total_pages_to_scrape = min(total_pages, max_pages)
        print(f"Found {total_results} listings on {total_pages} pages. Scraping {total_pages_to_scrape} pages.")

        # Kick off requests for all pages
        for page in range(1, total_pages_to_scrape + 1):
            async for property_model in self.handle_listing_page(search_url, page):
                yield property_model
