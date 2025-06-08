import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from aiolimiter import AsyncLimiter
from rnet import Client
from tenacity import retry, stop_after_attempt, wait_exponential

from immoscout_scraper.models import ListingID, RawProperty
from immoscout_scraper.url_conversion import get_expose_details_url, get_page_url

logging.basicConfig(level=logging.INFO)


@dataclass
class ListingCounts:
    total_listings: int
    number_of_pages: int
    page_size: int


def parse_listings_page(page_data: dict) -> set[ListingID]:
    results = page_data["resultListItems"]
    return {int(result_item["item"]["id"]) for result_item in results if result_item["type"] == "EXPOSE_RESULT"}


@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(5))
async def fetch_listing_page(client: Client, search_url: str, page: int) -> dict:
    return await (
        await client.post(get_page_url(search_url, page=page), json={"supportedResultListType": [], "userData": {}})
    ).json()


@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(5))
async def fetch_property_details(client: Client, listing_id: ListingID) -> dict:
    return await (await client.get(get_expose_details_url(listing_id))).json()


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
            data = await fetch_property_details(self.client, listing_id)
            return RawProperty(listing_id=data["header"]["id"], data=data)

    async def handle_listing_page(self, search_url: str, page: int) -> AsyncGenerator[RawProperty, None]:
        async with self.limiter:
            data = await fetch_listing_page(self.client, search_url, page)

        listing_ids = parse_listings_page(data)
        listing_ids_to_scrape = listing_ids - self.already_scraped

        # Request pages - should return any results as soon as it is available
        scrape_tasks = [
            asyncio.create_task(self.handle_listing_details(listing_id)) for listing_id in listing_ids_to_scrape
        ]
        for listing_page in asyncio.as_completed(scrape_tasks):
            yield (await listing_page)

    async def get_number_of_listings(self, search_url: str) -> ListingCounts:
        page_data = await fetch_listing_page(self.client, search_url, page=1)

        return ListingCounts(
            total_listings=page_data["totalResults"],
            number_of_pages=page_data["numberOfPages"],
            page_size=page_data["pageSize"],
        )

    async def scrape_listings(self, search_url: str, pages: list[int] | int) -> AsyncGenerator[RawProperty, None]:
        if isinstance(pages, int):
            pages = list(range(1, pages + 1))

        # Kick off requests for all pages
        for page in pages:
            async for property_model in self.handle_listing_page(search_url, page):
                yield property_model
