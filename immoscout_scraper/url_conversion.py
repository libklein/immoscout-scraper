from furl import furl  # type: ignore[import-untyped]


def convert_web_to_mobile(web_url: str) -> str:
    """
    Convert a web URL from immobilienscout24.de to the corresponding mobile API URL.

    Args:
        web_url: The web URL from immobilienscout24.de search

    Returns:
        The corresponding mobile API URL

    Raises:
        ValueError: If the URL format is invalid or contains unsupported parameters
    """
    try:
        url = furl(web_url)
    except Exception as e:
        raise ValueError(f"Invalid URL: {web_url}") from e

    # Parse the path to extract geocodes
    segments = url.path.segments
    if len(segments) < 5 or segments[0] != "Suche":
        raise ValueError(f"Unexpected path format: {url.path}")

    geocodes = f"/{segments[1]}/{segments[2]}/{segments[3]}"

    # Get query parameters as dict
    web_params = {}
    for key, value in url.query.params.items():
        if isinstance(value, list) and len(value) == 1:
            web_params[key] = value[0]
        elif isinstance(value, list):
            web_params[key] = ",".join(value)
        else:
            web_params[key] = str(value)

    # Parameter name mapping from web to mobile API
    param_name_map = {
        "heatingtypes": "heatingtypes",
        "haspromotion": "haspromotion",
        "numberofrooms": "numberofrooms",
        "livingspace": "livingspace",
        "energyefficiencyclasses": "energyefficiencyclasses",
        "exclusioncriteria": "exclusioncriteria",
        "equipment": "equipment",
        "petsallowedtypes": "petsallowedtypes",
        "price": "price",
        "constructionyear": "constructionyear",
        "apartmenttypes": "apartmenttypes",
        "pricetype": "pricetype",
        "floor": "floor",
    }

    # Equipment value mapping from web to mobile API
    equipment_value_map = {
        "parking": "parking",
        "cellar": "cellar",
        "builtinkitchen": "builtInKitchen",
        "lift": "lift",
        "garden": "garden",
        "guesttoilet": "guestToilet",
        "balcony": "balcony",
    }

    # Remove unsupported parameters
    web_params.pop("enteredFrom", None)

    # Check for unsupported parameters
    for key in web_params:
        if key not in param_name_map:
            raise ValueError(f'Unsupported Web-API parameter: "{key}"')

    translated_params = {}

    # Translate parameters
    for web_key, web_val in web_params.items():
        value = web_val

        if web_key == "equipment":
            # Map equipment list to camelCase values
            if isinstance(value, str):
                value_list = value.split(",")
            else:
                value_list = [str(value)]

            mapped_equipment: list[str] = []
            for token in value_list:
                token_lower = token.lower().strip()
                if token_lower not in equipment_value_map:
                    raise ValueError(f'Unknown equipment type: "{token}"')
                mapped_value = equipment_value_map[token_lower]
                mapped_equipment.append(mapped_value)
            translated_params[param_name_map[web_key]] = ",".join(mapped_equipment)
        else:
            translated_params[param_name_map[web_key]] = value

    # Build mobile API URL
    mobile_url = furl("https://api.mobile.immobilienscout24.de/search/list")

    # Set base parameters
    mobile_url.query.params.update({"searchType": "region", "geocodes": geocodes, "realestatetype": "apartmentrent"})

    # Add translated parameters
    mobile_url.query.params.update(translated_params)

    return str(mobile_url)


def get_page_url(mobile_url: str, page: int) -> str:
    """
    Get the page URL for a given mobile API URL and page number.
    """
    url = furl(mobile_url)
    url.query.params["pagenumber"] = str(page)
    return str(url)


def get_expose_details_url(listing_id: int | str) -> str:
    """
    Get the expose details URL for a given listing ID.
    """
    return f"https://api.mobile.immobilienscout24.de/expose/{listing_id}"
