from dataclasses import dataclass

ListingID = int


@dataclass
class Listing:
    listing_id: ListingID
    data: dict
