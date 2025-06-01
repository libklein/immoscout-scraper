from immoscout_scraper.url_conversion import get_expose_details_url, get_page_url
from rnet import Impersonate, Client, Response
import asyncio
import tenacity
from aiolimiter import AsyncLimiter
import logging
from typing import AsyncGenerator
from immoscout_scraper.models import ListingID, Listing
from immoscout_scraper.db import PropertyDatabase

logging.basicConfig(level=logging.INFO)


def create_client() -> Client:
    return Client(
        impersonate=Impersonate.OkHttp5,
        user_agent="ImmoScout24_1410_30_._",
        timeout=30,
    )


def parse_listings_page(page_data: dict) -> set[ListingID]:
    results = page_data["resultListItems"]
    return {int(result_item["item"]["id"]) for result_item in results if result_item["type"] == "EXPOSE_RESULT"}


async def fetch_listing_page(client: Client, search_url: str, page: int) -> Response:
    return await client.post(get_page_url(search_url, page=page), json={"supportedResultListType": [], "userData": {}})


class ImmoscoutScraper:
    def __init__(
        self, client: Client, already_scraped: set[ListingID] | None = None, max_requests_per_second: int = 16
    ):
        self.client = client
        self.already_scraped = already_scraped or set()
        self.limiter = AsyncLimiter(max_requests_per_second, time_period=1)

    async def handle_listing_details(self, listing_id: ListingID) -> Listing:
        async with self.limiter:
            data = await (await self.client.get(get_expose_details_url(listing_id))).json()
            # Mock implementation for the sake of example
            return Listing(data["header"]["id"], data)

    async def handle_listing_page(self, search_url: str, page: int) -> AsyncGenerator[Listing, None]:
        response: Response = await fetch_listing_page(self.client, search_url, page)

        listing_ids = parse_listings_page(await response.json())
        listing_ids_to_scrape = listing_ids - self.already_scraped
        print(f"Found {listing_ids_to_scrape} new listings on page {page}.")

        # Request pages - should return any results as soon as it is available
        async with self.limiter:
            scrape_tasks = [
                asyncio.create_task(self.handle_listing_details(listing_id)) for listing_id in listing_ids_to_scrape
            ]
            for listing_page in asyncio.as_completed(scrape_tasks):
                yield (await listing_page)

    async def scrape_listings(self, search_url: str) -> list[Listing]:
        # Make first request to get starting page and page count
        response: Response = await fetch_listing_page(self.client, search_url, page=1)
        page_data = await response.json()

        total_results = page_data["totalResults"]
        results_per_page = page_data["pageSize"]
        total_pages = page_data["numberOfPages"]
        print(f"Total results: {total_results}, Results per page: {results_per_page}, Total pages: {total_pages}")

        total_pages = 1
        # Kick off requests for all pages
        parsed_listings = []
        for page in range(1, total_pages + 1):
            async for property_model in self.handle_listing_page(search_url, page):
                parsed_listings.append(property_model)

        return parsed_listings


async def main():
    from pathlib import Path
    from immoscout_scraper.url_conversion import convert_web_to_mobile

    db = PropertyDatabase(Path("properties.db"))
    existing_ids = db.fetch_saved_listing_ids()
    print(f"Already scraped {existing_ids} listings.")

    client = create_client()
    scraper = ImmoscoutScraper(client, existing_ids, max_requests_per_second=16)
    new_properties = await scraper.scrape_listings(
        convert_web_to_mobile("https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten")
    )

    db.save_listings(new_properties)


if __name__ == "__main__":
    asyncio.run(main())
