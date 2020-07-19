"""Utility for searching the daily region dump for keywords"""

import logging
from typing import Sequence

import config
import nsapi

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)


def factbook_searcher(
    requester: nsapi.NSRequester, *keywords: str, populationMinimum: int = 0
) -> Sequence[nsapi.RegionStandard]:
    """Returns Region's which have at least one of the given keywords in their WFE (.factbook)"""
    return [
        region
        # Maps from XML to RegionStandard, should be single pass since its a generator wrapping
        for region in (
            nsapi.RegionStandard.from_xml(regionXML)
            for regionXML in requester.dumpManager().retrieve_iterator("regions")
        )
        # Probably not the most efficient (probably O(n^2))
        if any(keyword in region.factbook for keyword in keywords)
        and region.numnations > populationMinimum
    ]


# f"https://www.nationstates.net/region={clean_format(region.name)}"
def main() -> None:
    """Main function"""

    requester = nsapi.NSRequester(config.userAgent)

    print("Enter keywords to search for, split with commas.")
    print("Any region with at least one keyword in the WFE is returned.")
    keywords = input("Keywords: ").split(",")

    print("Enter the minimum number of residents of a region.")
    print("Regions with less residents than this number will not be reported.")
    print("0 can be used to report all regions that match the keywords.")
    minimum = int(input("Minimum: "))

    print("\nResults:")
    for region in factbook_searcher(requester, *keywords, populationMinimum=minimum):
        print(f"https://www.nationstates.net/region={nsapi.clean_format(region.name)}")


if __name__ == "__main__":
    main()
