"""Retrieves the WA residents of a region"""

import argparse
import logging
from typing import Collection, Iterable

import config
import nsapi

# Set logging level
level = logging.WARNING
# Name logger
logger = logging.getLogger()
# Configure loggers
nsapi.configure_logger(logger, level=level)
nsapi.configure_logger(nsapi.logger, level=level)


def residents(requester: nsapi.NSRequester, region: str) -> Collection[str]:
    """Retrieves the WA residents of the given region."""

    # Retrieve residents
    return set(requester.region(region).nations()) & set(
        requester.wa().shard("members").split(",")
    )


def listLinks(nations: Iterable[str]) -> str:
    """Returns a string containing the given nations formatted into links,
    seperated by newlines (with trailing).
    """

    return (
        "\n".join(
            f"https://www.nationstates.net/nation={nsapi.clean_format(nation)}"
            for nation in nations
        )
        + "\n"
    )


def low_endorsements(
    requester: nsapi.NSRequester, region: str, count: int = 20
) -> Collection[str]:
    """
    Finds nations with low endorsements.

    Searches the nation dump for WA nations in the specified region
    with less endorsements than the given count.
    """

    filtered = []

    # Squash casing on region
    lower_region = region.lower()

    # Search for matching nations
    for nation in requester.dumpManager().nations():
        if (
            # Compare regions, case insensitive
            nation.region.lower() == lower_region
            # Check that in WA
            and nation.WAStatus.startswith("WA")
            # Check that endorsements are under the specified level
            and len(nation.endorsements) <= count
        ):
            # Save to return at end of search
            filtered.append(nation.name)

    return filtered


def main() -> None:
    """Main function, mainly for testing purposes."""

    parser = argparse.ArgumentParser(
        description="Collects various information on WA residents of a region."
    )

    parser.add_argument("region", help="Region to search.")

    parser.add_argument(
        "-c",
        "--count",
        help="Only collect residents with less endorsements than this.",
        type=int,
        default=None,
    )

    # Parse args
    args = parser.parse_args()

    # Setup requester
    requester = nsapi.NSRequester(config.userAgent)

    # Use api if getting all residents
    if not args.count:
        nations = residents(requester, args.region)
    # Use dump if filtering
    else:
        nations = low_endorsements(requester, args.region, args.count)

    # print(listLinks(nations))
    print(nations)


# Call main if this script is the entrypoint
if __name__ == "__main__":
    main()
