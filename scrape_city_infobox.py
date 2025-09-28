#!/usr/bin/env python3

import sys
from typing import Dict, Tuple, Optional

import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 LocalInfoScraper/1.0"
)


def fetch_city_page_html(city_name: str) -> Tuple[str, str]:
    """Fetch the HTML for a Wikipedia page for the given city name.

    Returns a tuple of (html_text, resolved_url).
    """
    canonical_name = city_name.replace(" ", "_")
    url = f"https://en.wikipedia.org/wiki/{canonical_name}"
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.text, response.url


def parse_infobox(html_text: str) -> Tuple[Optional[str], Dict[str, str], BeautifulSoup]:
    """Parse the Wikipedia HTML and extract the page title and an infobox map.

    The returned dict maps infobox row labels to their text content.
    """
    soup = BeautifulSoup(html_text, "html.parser")

    # Page title
    title_element = soup.find(id="firstHeading")
    page_title = title_element.get_text(strip=True) if title_element else None

    # Find the infobox table. Wikipedia uses a few variants of class names.
    infobox = (
        soup.find("table", class_="infobox geography vcard")
        or soup.find("table", class_="infobox vcard")
        or soup.find("table", class_="infobox")
    )

    info: Dict[str, str] = {}
    if infobox is not None:
        for row in infobox.find_all("tr"):
            header_cell = row.find("th")
            data_cell = row.find("td")
            if header_cell and data_cell:
                label = " ".join(header_cell.get_text(separator=" ", strip=True).split())
                value_text = " ".join(data_cell.get_text(separator=" ", strip=True).split())
                if label and value_text:
                    info[label] = value_text

    # Coordinates sometimes are outside the table; include if present.
    geo = soup.find(class_="geo")
    if geo is not None:
        info.setdefault("Coordinates", " ".join(geo.get_text(separator=" ", strip=True).split()))

    return page_title, info, soup


def select_interesting_fields(info: Dict[str, str]) -> Dict[str, str]:
    """Select a subset of commonly useful local information fields from infobox.

    Uses fuzzy label inclusion to account for variations across cities/countries.
    """
    desired_to_label_hints = {
        "Country": ["Country"],
        "State/Province": ["State", "Province", "Region", "Prefecture"],
        "County/District": ["County", "District", "Municipality"],
        "Settlement type": ["Settlement type", "Type"],
        "Incorporated/Founded": ["Incorporated", "Established", "Founded"],
        "Mayor/Leader": ["Mayor", "Leader", "Governing body"],
        "Area total": ["Area total", "Area", "Area Total"],
        "Elevation": ["Elevation"],
        "Population": ["Population", "Population Total", "Population ("],
        "Demonym": ["Demonym"],
        "Time zone": ["Time zone", "Timezone"],
        "Postal code": ["Postal code", "Postcode", "ZIP codes"],
        "FIPS/GNIS": ["FIPS code", "GNIS feature ID"],
        "Coordinates": ["Coordinates"],
    }

    # Build a lowercase index for fuzzy matching
    original_to_lower = {original_label: original_label.lower() for original_label in info.keys()}

    selected: Dict[str, str] = {}
    for output_key, label_hints in desired_to_label_hints.items():
        found_value: Optional[str] = None
        for hint in label_hints:
            hint_lower = hint.lower()
            for original_label, lowered in original_to_lower.items():
                if hint_lower in lowered:
                    found_value = info[original_label]
                    break
            if found_value is not None:
                break
        if found_value is not None:
            selected[output_key] = found_value
    return selected


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python scrape_city_infobox.py "City Name"')
        sys.exit(1)

    city_name = " ".join(sys.argv[1:])
    try:
        html_text, resolved_url = fetch_city_page_html(city_name)
    except requests.HTTPError as http_error:
        print(f"HTTP error fetching page: {http_error}")
        sys.exit(2)
    except requests.RequestException as request_error:
        print(f"Network error fetching page: {request_error}")
        sys.exit(2)

    page_title, info_map, _soup = parse_infobox(html_text)

    print(f"Title: {page_title or city_name}")
    print(f"Source: {resolved_url}")

    if not info_map:
        print("Could not find an infobox on the page or it is empty.")
        sys.exit(0)

    interesting = select_interesting_fields(info_map)
    if not interesting:
        print("No common local information fields were detected.")
        sys.exit(0)

    # Print the selected fields in a readable order
    for key, value in interesting.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()


