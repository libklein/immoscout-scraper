import re
from datetime import date, datetime
from typing import Any, Optional

from pydantic import ConfigDict, field_validator
from pydantic.alias_generators import to_snake
from sqlmodel import JSON, Field, SQLModel

ListingID = int


class RawProperty(SQLModel, table=True):
    listing_id: ListingID = Field(primary_key=True, index=True)
    data: dict = Field(sa_type=JSON)


def parse_currency(value: str) -> float:
    """
    Convert a currency string (e.g., "€1,385", "€15.56/m²", "4.155,00 €") into a float.
    Handles both German-style (dots as thousand separators, commas as decimals)
    and international-style (commas as thousand separators).
    """
    # Remove all characters except digits, dots, and commas
    cleaned = re.sub(r"[^0-9\.,]", "", value)

    # If both '.' and ',' are present, assume German style: '.' thousands, ',' decimals
    if "." in cleaned and "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        # If only comma is present, assume it's a thousands separator -> remove it
        cleaned = cleaned.replace(",", "")

    try:
        return float(cleaned)
    except ValueError:
        return 0.0


class Property(SQLModel, table=True):
    listing_id: ListingID = Field(primary_key=True, index=True)
    scraped_on: datetime
    publication_state: str
    real_estate_type: str
    listing_title: str
    address: str
    latitude: float
    longitude: float

    basic_rent: float
    rooms: Optional[int]
    living_space: Optional[float]
    total_rent: float
    net_rent_plus_ancillary_costs: Optional[float]
    price_per_sqm: Optional[float]
    ancillary_costs: Optional[float]
    heating_costs_included: Optional[bool]
    deposit: Optional[float]

    apartment_type: Optional[str]
    floor: Optional[str]
    sleeping_rooms: Optional[int]
    bathrooms: Optional[int]
    vacant_from: Optional[date]
    pets: Optional[str]
    balcony_terrace: Optional[bool]
    elevator: Optional[bool]
    fitted_kitchen: Optional[bool]

    construction_year: Optional[int]
    object_state: Optional[str]
    interior_quality: Optional[str]
    type_of_heating: Optional[str]
    energy_identification_type: Optional[str]
    end_energy_demand: Optional[float]
    energy_efficiency_category: Optional[str]

    model_config = ConfigDict(
        alias_generator=to_snake,
        populate_by_name=True,
    )  # type: ignore[assignment]

    @field_validator("net_rent_plus_ancillary_costs", "price_per_sqm", "ancillary_costs", "deposit", mode="before")
    def _parse_currency(cls, v: Any) -> Optional[float]:
        if isinstance(v, str) and v.strip().lower() != "unknown":
            return parse_currency(v)
        elif isinstance(v, (int, float)):
            return float(v)
        return None

    @field_validator(
        "rooms",
        "living_space",
        "heating_costs_included",
        "apartment_type",
        "floor",
        "sleeping_rooms",
        "bathrooms",
        "vacant_from",
        "pets",
        "balcony_terrace",
        "elevator",
        "fitted_kitchen",
        "construction_year",
        "object_state",
        "interior_quality",
        "type_of_heating",
        "energy_identification_type",
        "end_energy_demand",
        "energy_efficiency_category",
        mode="before",
    )
    def set_unknown_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and v.strip().lower() == "unknown":
            return None
        return v

    @field_validator("vacant_from", mode="before")
    def _parse_vacant_from(cls, v: Any) -> Optional[date]:
        if v is None:
            return None
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            lower = v.strip().lower()
            if lower in {"sofort", "ab sofort"}:
                return date.today()
            if lower == "unknown":
                return None
            try:
                return datetime.strptime(v, "%d.%m.%Y").date()
            except Exception:
                return None
        return None


def parse_property(data: dict[str, Any]) -> Property:
    sections = data.get("sections", [])

    # HEADER
    header = data.get("header", {})
    listing_id = int(header.get("id", 0))
    publication_state = header.get("publicationState", "")
    real_estate_type = header.get("realEstateType", "")

    # TITLE section
    listing_title = ""
    for section in sections:
        if section.get("type") == "TITLE":
            listing_title = section.get("title", "")
            break

    # MAP section → address & coordinates
    latitude = longitude = 0.0
    address = ""
    for section in sections:
        if section.get("type") == "MAP":
            loc = section.get("location", {})
            latitude = loc.get("lat", 0.0)
            longitude = loc.get("lng", 0.0)
            addr1 = section.get("addressLine1", "")
            addr2 = section.get("addressLine2", "")
            address = f"{addr1}, {addr2}"
            break

    # TOP_ATTRIBUTES → basic_rent, rooms, living_space, total_rent
    basic_rent = 0.0
    rooms: Any = "unknown"
    living_space: Any = "unknown"
    total_rent = 0.0
    for section in sections:
        if section.get("type") == "TOP_ATTRIBUTES":
            for attr in section.get("attributes", []):
                label = attr.get("label", "")
                text = attr.get("text", "")
                if "Basic rent" in label:
                    basic_rent = parse_currency(text) if text.strip().lower() != "unknown" else 0.0
                elif label == "Rooms":
                    rooms = text if text.strip().lower() != "unknown" else "unknown"
                elif "Living space" in label:
                    living_space = (
                        text.split()[0].replace("\u00a0", "") if text.strip().lower() != "unknown" else "unknown"
                    )
                elif "Total rent" in label:
                    total_rent = parse_currency(text) if text.strip().lower() != "unknown" else 0.0
            break

    # Costs section → net_rent_plus_ancillary_costs, price_per_sqm, ancillary_costs, heating_costs_included, deposit
    net_rent_plus_ancillary: Any = "unknown"
    price_per_sqm: Any = "unknown"
    ancillary_costs: Any = "unknown"
    heating_costs_included: Any = "unknown"
    deposit: Any = "unknown"
    for section in sections:
        if section.get("type") == "ATTRIBUTE_LIST" and section.get("title") == "Costs":
            for attr in section.get("attributes", []):
                label = attr.get("label", "")
                text = attr.get("text", "")
                lower_text = text.strip().lower()
                if "Net rent" in label:
                    net_rent_plus_ancillary = text if lower_text != "unknown" else "unknown"
                elif "Price/m²" in label:
                    price_per_sqm = text if lower_text != "unknown" else "unknown"
                elif label.startswith("Ancillary costs"):
                    ancillary_costs = text if lower_text != "unknown" else "unknown"
                elif "Heating costs included" in label:
                    heating_costs_included = (
                        text.strip().lower() == "yes" if lower_text not in {"unknown", ""} else "unknown"
                    )
                elif "Deposit" in label:
                    deposit = text if lower_text != "unknown" else "unknown"
            break

    # Main criteria → apartment_type, floor, sleeping_rooms, bathrooms, vacant_from, pets, balcony_terrace, elevator, fitted_kitchen
    apartment_type: Any = "unknown"
    floor: Any = "unknown"
    sleeping_rooms: Any = "unknown"
    bathrooms: Any = "unknown"
    vacant_from: Any = "unknown"
    pets: Any = "unknown"
    balcony_terrace: Any = "unknown"
    elevator: Any = "unknown"
    fitted_kitchen: Any = "unknown"
    for section in sections:
        if section.get("type") == "ATTRIBUTE_LIST" and section.get("title") == "Main criteria":
            for attr in section.get("attributes", []):
                label = attr.get("label", "")
                text = attr.get("text", "")
                typ = attr.get("type", "")
                lower_text = text.strip().lower()
                if typ == "TEXT":
                    if "Apartment type" in label:
                        apartment_type = text if lower_text != "unknown" else "unknown"
                    elif "Floor" in label:
                        floor = text if lower_text != "unknown" else "unknown"
                    elif "Sleeping rooms" in label:
                        sleeping_rooms = text if lower_text != "unknown" else "unknown"
                    elif "Bathrooms" in label:
                        bathrooms = text if lower_text != "unknown" else "unknown"
                    elif "Vacant" in label:
                        vacant_from = text if lower_text != "unknown" else "unknown"
                    elif "Pets" in label:
                        pets = text if lower_text != "unknown" else "unknown"
                elif typ == "CHECK":
                    if "Balcony/Terrace" in label:
                        balcony_terrace = True
                    elif "Elevator" in label:
                        elevator = True
                    elif "Fitted kitchen" in label:
                        fitted_kitchen = True
            break

    # Building details → construction_year, object_state, interior_quality, type_of_heating,
    # energy_identification_type, end_energy_demand, energy_efficiency_category
    construction_year: Any = "unknown"
    object_state: Any = "unknown"
    interior_quality: Any = "unknown"
    type_of_heating: Any = "unknown"
    energy_identification_type: Any = "unknown"
    end_energy_demand: Any = "unknown"
    energy_efficiency_category: Any = "unknown"
    for section in sections:
        if section.get("type") == "ATTRIBUTE_LIST" and section.get("title") == "Building details & energy certificate":
            for attr in section.get("attributes", []):
                label = attr.get("label", "")
                text = attr.get("text", "")
                lower_text = text.strip().lower()
                if "Construction year" in label:
                    construction_year = text if lower_text != "unknown" else "unknown"
                elif "Object state" in label:
                    object_state = text if lower_text != "unknown" else "unknown"
                elif "Interior quality" in label:
                    interior_quality = text if lower_text != "unknown" else "unknown"
                elif "Type of heating" in label:
                    type_of_heating = text if lower_text != "unknown" else "unknown"
                elif "Energy identification type" in label:
                    energy_identification_type = text if lower_text != "unknown" else "unknown"
                elif "End energy demand" in label:
                    end_energy_demand = text.split()[0] if lower_text != "unknown" else "unknown"
                elif attr.get("type") == "IMAGE" and "Energy efficiency category" in label:
                    url = attr.get("url", "")
                    if lower_text == "unknown":
                        energy_efficiency_category = "unknown"
                    elif "A-plus" in url:
                        energy_efficiency_category = "A Plus"
                    else:
                        energy_efficiency_category = text or "unknown"
            break

    return Property.model_validate(
        dict(
            listing_id=listing_id,
            scraped_on=datetime.now(),
            publication_state=publication_state,
            real_estate_type=real_estate_type,
            listing_title=listing_title,
            address=address,
            latitude=latitude,
            longitude=longitude,
            basic_rent=basic_rent,
            rooms=rooms,
            living_space=living_space,
            total_rent=total_rent,
            net_rent_plus_ancillary_costs=net_rent_plus_ancillary,
            price_per_sqm=price_per_sqm,
            ancillary_costs=ancillary_costs,
            heating_costs_included=heating_costs_included,
            deposit=deposit,
            apartment_type=apartment_type,
            floor=floor,
            sleeping_rooms=sleeping_rooms,
            bathrooms=bathrooms,
            vacant_from=vacant_from,
            pets=pets,
            balcony_terrace=balcony_terrace,
            elevator=elevator,
            fitted_kitchen=fitted_kitchen,
            construction_year=construction_year,
            object_state=object_state,
            interior_quality=interior_quality,
            type_of_heating=type_of_heating,
            energy_identification_type=energy_identification_type,
            end_energy_demand=end_energy_demand,
            energy_efficiency_category=energy_efficiency_category,
        )
    )
