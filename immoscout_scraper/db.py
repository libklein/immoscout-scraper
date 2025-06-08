from pathlib import Path

from sqlmodel import Session, SQLModel, col, create_engine, select

from immoscout_scraper.models import ListingID, Property, RawProperty


class PropertyDatabase:
    def __init__(self, db_path: Path):
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        SQLModel.metadata.create_all(self.engine)

    def save_raw_properties(self, listings: list[RawProperty], upsert: bool = False) -> None:
        with Session(self.engine) as session:
            if upsert:
                # Delete existing entries with same listing_ids
                listing_ids = [listing.listing_id for listing in listings]
                if listing_ids:
                    # Fetch existing listings
                    existing_listings = session.exec(
                        select(RawProperty).where(col(RawProperty.listing_id).in_(listing_ids))
                    ).all()
                    for listing in existing_listings:
                        session.delete(listing)
                    session.commit()
            session.add_all(listings)
            session.commit()

    def save_properties(self, properties: list[Property], upsert: bool = False) -> None:
        with Session(self.engine) as session:
            if upsert:
                # Delete existing entries with same listing_ids
                listing_ids = [prop.listing_id for prop in properties]
                if listing_ids:
                    # Fetch existing listings
                    existing_listings = session.exec(
                        select(Property).where(col(Property.listing_id).in_(listing_ids))
                    ).all()
                    for listing in existing_listings:
                        session.delete(listing)
                    session.commit()
            session.add_all(properties)
            session.commit()

    def fetch_saved_listing_ids(self) -> set[ListingID]:
        with Session(self.engine) as session:
            return set(session.exec(select(RawProperty.listing_id)).all())
