from immoscout_scraper.url_conversion import get_expose_details_url, get_page_url, convert_web_to_mobile
from rnet import Impersonate, Client, Response
import asyncio
import tenacity
from aiolimiter import AsyncLimiter
import logging
from typing import AsyncGenerator, Coroutine

logging.basicConfig(level=logging.INFO)

ListingID = int

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
    return await client.post(get_page_url(search_url, page=page), json={'supportedResultListType': [], "userData": {}})

class ImmoscoutScraper:
    def __init__(self, client: Client, already_scraped: set[ListingID] | None = None):
        self.client = client
        self.already_scraped = already_scraped or set()
        self.limiter = AsyncLimiter(10, 1)

    async def handle_listing_details(self, listing_id: ListingID) -> dict:
        async with self.limiter:
            data = await (await self.client.get(get_expose_details_url(listing_id))).json()
            # Mock implementation for the sake of example
            return data

    async def handle_listing_page(self, search_url: str, page: int) -> AsyncGenerator[dict, None]:
        response: Response = await fetch_listing_page(self.client, search_url, page)

        listing_ids = parse_listings_page(await response.json())
        listing_ids_to_scrape = listing_ids - self.already_scraped

        # Request pages - should return any results as soon as it is available
        async with self.limiter:
            scrape_tasks = [asyncio.create_task(self.handle_listing_details(listing_id)) for listing_id in listing_ids_to_scrape]
            for listing_page in asyncio.as_completed(scrape_tasks):
                yield (await listing_page)

    async def scrape_listings(self, search_url: str):
        # Make first request to get starting page and page count
        response: Response = await fetch_listing_page(client, search_url, page=1)
        page_data = await response.json()

        total_results = page_data["totalResults"]
        results_per_page = page_data["pageSize"]
        total_pages = page_data["numberOfPages"]
        print(f"Total results: {total_results}, Results per page: {results_per_page}, Total pages: {total_pages}")

        total_pages = 1
        # Kick off requests for all pages
        listing_tasks = []
        for page in range(1, total_pages + 1):
            async for property_model in self.handle_listing_page(search_url, page):
                print(property_model)

if __name__ == "__main__":
    client = create_client()
    scraper = ImmoscoutScraper(client)
    asyncio.run(scraper.scrape_listings(convert_web_to_mobile("https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten")))
