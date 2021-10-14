"""Determines who has not been endorsed on NationStates"""

# Import standard modules
import argparse
import datetime
import itertools
import logging
from typing import Iterable, Tuple

# Import nsapi
import nsapi
import config

# Set logging level
level = logging.INFO
# Name logger
logger = logging.getLogger(__name__)
# Configure loggers
nsapi.configure_logger(logging.getLogger(), level=level)


def unendorsed_nations(
    requester: nsapi.NSRequester, endorser: str
) -> Tuple[str, Iterable[str]]:
    """Finds all WA members of the nation's region who have not been endorsed
    Returns a tuple containing the region, and a iterable of unendorsed nations
    """

    # Collect region
    region = requester.nation(endorser).shard("region")

    # Load downloaded nation file
    # Pack into conversion generator to simplify transformations
    nationDump = requester.dumpManager().nations()

    # Pull all nations in the region that are WA members
    # Use generator because we dont need to generate a list that is never used
    logger.info("Collecting %s WA Members", region)
    waMembers = (
        nation
        for nation in nationDump
        if nation.region == region and nation.WAStatus.startswith("WA")
    )

    # Pull nations who are not endorsed
    logger.info("Collecting WA members who have not been endorsed")
    nonendorsed = (
        # Save name string, converting to lowercase, underscore format
        nsapi.clean_format(nation.name)
        for nation in waMembers
        # Check if unendorsed by checking endorsements
        if endorser not in nation.endorsements
    )

    return (region, nonendorsed)


# # TDO: update nonendorsed using activity:
# # api.cgi?q=happenings&view=region.10000_islands&filter=member+move
# # convert current_dump_day to the time the dump was generated as timestamp
# # and then request happenings since then. page through the happenings using `beforeid`
# # until empty list is returned, which signifies all happenings
# # since the timestamp have been retrieved
# # Consider adding this paging logic to the World class
# # in the happenings method, check if the limit keyword was given and >100,
# # if so page until reached
# # requester.world().happenings(view=f"region.{region}", filter="member+move")

# # Sort happenings by keyword
# # These keywords do not differentiate between all happening types,
# # (notably arriving and leaving)
# # but differentiate between formmating types
# # Prepare a dict of keywords -> list of happenings
# keywords: Dict[str, List[nsapi.Happening]] = {
#     "relocated": [],  # a nation move to or from the region
#     "admitted": [],  # a nation joined the WA
#     "resigned": [],  # a nation left the WA
#     "other": [],  # a 'other' bin, should only contain application happenings
# }
# for happening in requester.world().happenings(
#     view=f"region.{region}", filter="member+move"
# ):
#     for keyword in keywords:
#         if keyword in happening.text:
#             keywords[keyword].append(happening)
#             break
#     else:
#         keywords["other"].append(happening)

# # Handle happenings
# # should probably be handled in timestamp ascending order (maybe someone left and rejoined, etc)
# # relocated: if leaving, remove from unendorsed set (if in it)
# #            if arriving, check if they have been endorsed
# #               (maybe collaborate with false positive section)
# # admitted: check if they have been unendorsed (maybe collaborate)
# # resigned: remove from unendorsed set

# # Filter false positives
# # use `endo` filter on happenings of endorser
# # similar to wa changes/region moves, page through all happenings.


def unendorsed_nations_v2(
    requester: nsapi.NSRequester, endorser: str
) -> Tuple[str, Iterable[str]]:
    """Finds all WA members of the nation's region who have not been endorsed
    Returns a tuple containing the region, and a iterable of unendorsed nations
    """

    # Retrieve endorser region and endorsement list
    logger.info("Collecting WA Members")
    info = requester.nation(endorser).shards("region", "endorsements")
    region = info["region"]
    endorsements = set(info["endorsements"].split(","))

    # Retrieve regional citizens by cross referencing residents and wa members
    citizens = set(requester.wa().shard("members").split(",")) & set(
        requester.region(region).shard("nations").split(":")
    )

    # Optionally only check nations who havent endorsed the endorser
    nations = citizens - endorsements

    # Check each nation's endorsments
    logger.info("Checking WA members for endorsement")
    nonendorsed = [
        nation
        for nation in nations
        if endorser not in requester.nation(nation).shard("endorsements")
    ]

    return (region, nonendorsed)


def main() -> None:
    """Main function for running this module"""

    # Parse nation from command line
    parser = argparse.ArgumentParser(description="Determine who has not been endorsed.")
    parser.add_argument(
        "nation", help="Check who this nation has not endorsed.", default=None
    )
    parser.add_argument(
        "--format",
        help="Format output.",
        action="store_true",
    )

    args = parser.parse_args()
    nation: str = args.nation if args.nation else input("Nation: ")

    # Setup API
    API = nsapi.NSRequester(config.userAgent)

    logger.info("Collecting data")
    logger.info("Current time is %s UTC", datetime.datetime.utcnow())
    region, unendorsed = unendorsed_nations(API, nation)

    # Output unendorsed nations
    lines: Iterable[str]
    if args.format:
        logger.info("Formatting results")
        # Header
        header = f"{nation} has not endorsed the following WA Members in {region}:"
        # Formatted nation urls
        # Create output display strings
        # Increment step so that the list is 1-indexed
        nation_lines = (
            f"{step+1}. https://www.nationstates.net/nation={name}"
            for step, name in enumerate(unendorsed)
        )
        lines = itertools.chain([header], nation_lines)
    else:
        lines = unendorsed

    logger.info("Writing results")
    for line in lines:
        # Print to stdout
        print(line)

    logger.info("Current time is %s UTC", datetime.datetime.utcnow())


# Call main function when run as script
if __name__ == "__main__":
    main()
