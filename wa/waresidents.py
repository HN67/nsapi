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


def nation_url(nation: str) -> str:
    """Format a nation into a URL."""

    return f"https://www.nationstates.net/nation={nsapi.clean_format(nation)}"


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

    parser.add_argument(
        "-f",
        "--format",
        choices=["raw", "url", "bbcode"],
        default="bbcode",
        help="How to format the output.",
    )

    # Parse args
    # Check sys.argv first; if no args provided run interactive mode
    region: str
    count: t.Optional[int]
    output: t.Optional[str]
    form: str
    if len(sys.argv) <= 1:
        # Interactive mode
        region = input("Region to search: ")
        count_raw = input("Endorsement boundary (type nothing to get all WA): ")
        if count_raw:
            count = int(count_raw)
        else:
            count = None
        output = input("File name to output to: ")
        form = "bbcode"
    else:
        args = parser.parse_args()
        region = args.region
        count = args.count
        output = args.output
        form = args.format

    # Setup requester
    requester = nsapi.NSRequester(config.userAgent)

    # Use api if getting all residents
    if not count:
        nations = residents(requester, region)
    # Use dump if filtering
    else:
        nations = low_endorsements(requester, region, count)

    output_block: str
    if form == "url":
        output_block = "\n".join(map(nation_url, nations))
    elif form == "bbcode":
        output_block = listNationCodes(nations)
    else:
        output_block = "\n".join(nations)

    if output:
        with open(output, "w", encoding="utf-8") as out_file:
            print(output_block, file=out_file)
    else:
        print(output_block)


# Call main if this script is the entrypoint
if __name__ == "__main__":
    main()
