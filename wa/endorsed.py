"""Determines who has not endorsed someone on NationStates"""

# Import standard modules
import argparse
import logging
import typing as t

# Import library code
import nsapi
import config

# Set logging level
# Name logger
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def non_endorsers(
    requester: nsapi.NSRequester, nation: str
) -> t.Tuple[str, t.Iterable[str]]:
    """Find the region and all non-endorsers of a nation."""

    # Set target nation to check against
    target = nation

    # Collect region
    region = requester.nation(target).shard("region")

    # Pull target endorsement list
    endorsers = set(requester.nation(target).shard("endorsements").split(","))

    # Pull all nations in the region that are WA members
    logging.info("Collecting %s WA Members", region)

    # Pull all world wa nations
    worldWA = set(requester.wa().shard("members").split(","))

    # Pull all region nations
    regionNations = set(requester.region(region).shard("nations").split(":"))

    # Intersect wa members and region members
    citizens = worldWA & regionNations

    logging.info("Comparing WA Member list with target endorsers")
    # Determine WA members who have not endorsed target
    nonendorsers = citizens - endorsers

    return (region, nonendorsers)


def main() -> None:
    """Main function"""

    # Change nsapi logging level
    nsapi.enable_logging()

    # Parse nation from command line
    parser = argparse.ArgumentParser(description="Determine who has not been endorsed.")
    parser.add_argument(
        "nation", help="Check who has not endorsed this nation.", default=None
    )
    parser.add_argument(
        "--format",
        help="Format output.",
        action="store_true",
    )
    parser.add_argument(
        "--bbcode",
        help="Format nations with bbcode links. Overridden by --format.",
        action="store_true",
    )

    args = parser.parse_args()
    target = args.nation

    # Setup API
    requester = nsapi.NSRequester(config.userAgent)

    region, nonendorsers = non_endorsers(requester, nation=target)

    # Print output in formatted manner
    logging.info("Outputting results")

    # Header
    if args.format:
        print(f"The following WA Members of {region} have not endorsed {target}:")

    for step, nonendorser in enumerate(nonendorsers):
        if args.format:
            # Increment step so that it is 1-based
            print(f"{step+1}. https://www.nationstates.net/nation={nonendorser}")
        elif args.bbcode:
            print(f"[nation]{nonendorser}[/nation]")
        else:
            print(nonendorser)


if __name__ == "__main__":
    main()
