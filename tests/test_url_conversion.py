import pytest
from furl import furl

# Import the function we want to test
from immoscout_scraper.url_conversion import convert_web_to_mobile, get_page_url


class TestURLConversion:
    def test_convert_full_web_url_to_mobile_url(self):
        web_url = (
            "https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten?"
            "heatingtypes=central,selfcontainedcentral&haspromotion=false&"
            "numberofrooms=2.0-5.0&livingspace=10.0-25.0&"
            "energyefficiencyclasses=a,b,c,d,e,f,g,h,a_plus&"
            "exclusioncriteria=projectlisting,swapflat&"
            "equipment=parking,cellar,builtinkitchen,lift,garden,guesttoilet,balcony&"
            "petsallowedtypes=no,yes,negotiable&price=10.0-100.0&"
            "constructionyear=1920-2026&"
            "apartmenttypes=halfbasement,penthouse,other,loft,groundfloor,terracedflat,raisedgroundfloor,roofstorey,apartment,maisonette&"
            "pricetype=calculatedtotalrent&floor=2-7&enteredFrom=result_list"
        )

        expected_mobile_url = (
            "https://api.mobile.immobilienscout24.de/search/list?"
            "apartmenttypes=halfbasement,penthouse,other,loft,groundfloor,terracedflat,raisedgroundfloor,roofstorey,apartment,maisonette&"
            "constructionyear=1920-2026&"
            "energyefficiencyclasses=a,b,c,d,e,f,g,h,a_plus&"
            "equipment=parking,cellar,builtInKitchen,lift,garden,guestToilet,balcony&"
            "exclusioncriteria=projectlisting,swapflat&"
            "floor=2-7&"
            "geocodes=%2Fde%2Fberlin%2Fberlin&"
            "haspromotion=false&"
            "heatingtypes=central,selfcontainedcentral&"
            "livingspace=10.0-25.0&"
            "numberofrooms=2.0-5.0&"
            "petsallowedtypes=no,yes,negotiable&"
            "price=10.0-100.0&"
            "pricetype=calculatedtotalrent&"
            "realestatetype=apartmentrent&"
            "searchType=region"
        )

        actual_mobile_url = convert_web_to_mobile(web_url)

        # Parse both URLs to compare parameters (order may differ)
        expected_parsed = furl(expected_mobile_url)
        actual_parsed = furl(actual_mobile_url)

        # Check base URL is correct
        assert actual_parsed.scheme == expected_parsed.scheme
        assert actual_parsed.netloc == expected_parsed.netloc
        assert actual_parsed.path == expected_parsed.path

        # Parse query parameters for comparison
        expected_params = expected_parsed.query.params
        actual_params = actual_parsed.query.params

        # Check all expected parameters are present and correct
        for key, expected_values in expected_params.items():
            assert key in actual_params, f"Missing parameter: {key}"
            assert actual_params[key] == expected_values, f"Parameter {key} mismatch"

        # Check no extra parameters
        assert len(actual_params) == len(expected_params), "Parameter count mismatch"

    def test_unsupported_query_parameter_raises_error(self):
        web_url = "https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten?minimuminternetspeed=100000"

        with pytest.raises(ValueError, match='Unsupported Web-API parameter: "minimuminternetspeed"'):
            convert_web_to_mobile(web_url)

    def test_invalid_url_raises_error(self):
        invalid_url = "invalid-url"

        with pytest.raises(ValueError):
            convert_web_to_mobile(invalid_url)

    def test_unexpected_path_format_raises_error(self):
        web_url = "https://www.immobilienscout24.de/invalid/path/format"

        with pytest.raises(ValueError, match="Unexpected path format: /invalid/path/format"):
            convert_web_to_mobile(web_url)

    def test_simple_url_conversion(self):
        web_url = (
            "https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten?"
            "price=500-1500&pricetype=calculatedtotalrent"
        )

        result = convert_web_to_mobile(web_url)
        parsed = furl(result)
        params = parsed.query.params

        # Check base URL structure
        assert parsed.scheme == "https"
        assert parsed.netloc == "api.mobile.immobilienscout24.de"
        assert parsed.path == "/search/list"

        # Check required parameters
        assert "searchType" in params
        assert params["searchType"] == "region"
        assert "geocodes" in params
        assert params["geocodes"] == "/de/berlin/berlin"
        assert "realestatetype" in params
        assert params["realestatetype"] == "apartmentrent"

        # Check passed parameters
        assert "price" in params
        assert params["price"] == "500-1500"
        assert "pricetype" in params
        assert params["pricetype"] == "calculatedtotalrent"

    def test_equipment_parameter_mapping(self):
        web_url = (
            "https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten?"
            "equipment=balcony,builtinkitchen,parking"
        )

        result = convert_web_to_mobile(web_url)
        parsed = furl(result)
        params = parsed.query.params

        # Check equipment mapping
        assert "equipment" in params
        equipment_value = params["equipment"]

        # The equipment should be mapped to camelCase
        assert "balcony" in equipment_value
        assert "builtInKitchen" in equipment_value  # mapped from builtinkitchen
        assert "parking" in equipment_value

    def test_unknown_equipment_type_raises_error(self):
        web_url = "https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten?equipment=unknownequipment"

        with pytest.raises(ValueError, match='Unknown equipment type: "unknownequipment"'):
            convert_web_to_mobile(web_url)

    def test_entered_from_parameter_is_removed(self):
        web_url = (
            "https://www.immobilienscout24.de/Suche/de/berlin/berlin/wohnung-mieten?"
            "price=500-1500&enteredFrom=result_list"
        )

        result = convert_web_to_mobile(web_url)
        parsed = furl(result)
        params = parsed.query.params

        # enteredFrom should not be present in the result
        assert "enteredFrom" not in params
        assert "price" in params  # but other parameters should be present

    def test_short_path_raises_error(self):
        web_url = "https://www.immobilienscout24.de/Suche/de/berlin"

        with pytest.raises(ValueError, match="Unexpected path format: /Suche/de/berlin"):
            convert_web_to_mobile(web_url)

    def test_wrong_first_segment_raises_error(self):
        web_url = "https://www.immobilienscout24.de/NotSuche/de/berlin/berlin/wohnung-mieten"

        with pytest.raises(ValueError, match="Unexpected path format: /NotSuche/de/berlin/berlin/wohnung-mieten"):
            convert_web_to_mobile(web_url)

    def test_get_page_url(self):
        for expected_url, url, page in [
            (
                "https://api.mobile.immobilienscout24.de/search/list?pagenumber=3&searchType=region&geocodes=%2Fde%2Fberlin%2Fberlin&realestatetype=apartmentrent",
                "https://api.mobile.immobilienscout24.de/search/list?searchType=region&geocodes=%2Fde%2Fberlin%2Fberlin&realestatetype=apartmentrent",
                3,
            ),
            (
                "https://api.mobile.immobilienscout24.de/search/list?pagenumber=2&searchType=region&geocodes=%2Fde%2Fberlin%2Fberlin&realestatetype=apartmentrent",
                "https://api.mobile.immobilienscout24.de/search/list?pagenumber=1&searchType=region&geocodes=%2Fde%2Fberlin%2Fberlin&realestatetype=apartmentrent",
                2,
            ),
        ]:
            actual_url = get_page_url(url, page)
            # Url should without page number query parameter be the same as the original url
            actual_params = furl(actual_url).query.params
            expected_params = furl(expected_url).query.params
            for key, expected_val in expected_params.items():
                assert key in actual_params
                assert actual_params[key] == expected_val
            # Rest of the url should be the same
            assert furl(actual_url).set(query=None) == furl(expected_url).set(query=None)


if __name__ == "__main__":
    pytest.main([__file__])
