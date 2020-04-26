"""Determines who has not been endorsed on NationStates"""

# Import logging
import logging

# Import typing constructs
from typing import Iterable, Tuple

# Import nsapi
import nsapi
from nsapi import NationStandard as Nation

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)


def unendorsed_nations(
    requester: nsapi.NSRequester, endorser: str
) -> Tuple[str, Iterable[str]]:
    """Finds all WA members of the nation's region who have not been endorsed
    Returns a tuple containing the region, and a iterable of unendorsed nations
    """

    # Collect region
    region = requester.nation_shard_text(endorser, "region")

    # Load downloaded nation file
    # Pack into conversion generator to simplify transformations
    nationDump = (Nation(nation) for nation in requester.iterated_nation_dump())

    # Pull all nations in the region that are WA members
    # Use generator because we dont need to generate a list that is never used
    logging.info("Collecting %s WA Members", region)
    waMembers = (
        nation
        for nation in nationDump
        if nation.basic("REGION") == region
        and nation.basic("UNSTATUS").startswith("WA")
    )

    # Pull nations who are not endorsed
    logging.info("Collecting WA members who have not been endorsed")
    nonendorsed = [
        # Save name string, converting to lowercase, underscore format
        nation.basic("NAME").lower().replace(" ", "_")
        for nation in waMembers
        # Check if unendorsed by checking endorsements
        if nation["ENDORSEMENTS"].text is None
        or endorser not in nation["ENDORSEMENTS"].text
    ]

    return (region, nonendorsed)


def main() -> None:
    """Main function for running this module"""

    # Setup API
    API = nsapi.NSRequester("HN67 API Reader")
    # Set endorser nation to check for
    nation = "hn67"

    region, unendorsed = unendorsed_nations(API, nation)

    logging.info("Formatting results")
    # Create output display strings
    header = f"{nation} has not endorsed the following WA Members in {region}:"
    nationURLs = "\n".join(
        # Increment step so that the list is 1-indexed
        f"{step+1}. https://www.nationstates.net/nation={name}"
        for step, name in enumerate(unendorsed)
    )

    # Output unendorsed nations
    logging.info("Writing results")
    with open(nsapi.absolute_path("endorsements.txt"), "w") as f:
        # Header
        print(header, file=f)
        # Formatted nation urls
        print(nationURLs, file=f)


# Call main function when run as script
if __name__ == "__main__":
    main()
