import json
import sqlite3
from pathlib import Path

from immoscout_scraper.models import Listing, ListingID


class PropertyDatabase:
    def __init__(self, db_path: Path):
        self.connection = sqlite3.connect(db_path)
        self.cursor = self.connection.cursor()
        self._setup()

    def _setup(self):
        self.cursor.execute("CREATE TABLE IF NOT EXISTS RawProperties (id INTEGER PRIMARY KEY, data JSON)")

    def save_listings(self, listings: list[Listing]):
        self.cursor.executemany(
            "INSERT INTO RawProperties VALUES (:listing_id, :data)",
            ({"listing_id": x.listing_id, "data": json.dumps(x.data)} for x in listings),
        )
        self.connection.commit()

    def fetch_saved_listing_ids(self) -> set[ListingID]:
        return {x[0] for x in self.cursor.execute("SELECT id FROM RawProperties").fetchall()}
