"""Retrieves the WA residents of a region"""

import argparse
import logging
import sys
import typing as t
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


def listNationCodes(nations: Iterable[str]) -> str:
    """Returns a string containing the given nations formmatted into nscode links,
    conjoined into a single line.
    """

    return "".join(f"[nation]{nation}[/nation]" for nation in nations)


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

    parser.add_argument(
        "-o", "--output", help="File name to output to instead of stdout.", default=None
    )

    # Parse args
    # Check sys.argv first; if no args provided run interactive mode
    if len(sys.argv) <= 1:
        # Interactive mode
        region = input("Region to search: ")
        count_raw = input("Endorsement boundary (type nothing to get all WA): ")
        count: t.Optional[int]
        if count_raw:
            count = int(count_raw)
        else:
            count = None
        output = input("File name to output to: ")
    else:
        args = parser.parse_args()
        region = args.region
        count = args.count

    # Setup requester
    requester = nsapi.NSRequester(config.userAgent)

    # Use api if getting all residents
    if not count:
        nations = residents(requester, region)
    # Use dump if filtering
    else:
        nations = low_endorsements(requester, region, count)

    # print(listLinks(nations))
    # print(nations)
    if output:
        with open(output, "w") as out_file:
            print(listNationCodes(nations), file=out_file)
    else:
        print(listNationCodes(nations))


# Call main if this script is the entrypoint
if __name__ == "__main__":
    main()
