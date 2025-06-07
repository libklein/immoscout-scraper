from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

from immoscout_scraper.models import ListingID, Property, RawProperty


class PropertyDatabase:
    def __init__(self, db_path: Path):
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        SQLModel.metadata.create_all(self.engine)

    def save_raw_properties(self, listings: list[RawProperty]) -> None:
        with Session(self.engine) as session:
            session.add_all(listings)
            session.commit()

    def save_properties(self, properties: list[Property]) -> None:
        with Session(self.engine) as session:
            session.add_all(properties)
            session.commit()

    def fetch_saved_listing_ids(self) -> set[ListingID]:
        with Session(self.engine) as session:
            return set(session.exec(select(RawProperty.listing_id)).all())
