"""Script utility to track the number of issues answered on nations"""

import argparse
import datetime
import logging
import shlex
import sys
import typing as t

import requests

import config
import nsapi

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
logger = logging.getLogger()
nsapi.logger.setLevel(level=level)


def count_change(
    requester: nsapi.NSRequester,
    nations: t.Collection[str],
    start: datetime.date,
    end: datetime.date,
) -> t.Tuple[t.Mapping[str, int], t.Iterable[str]]:
    """For each nation provided, retrieves the number of issues
    they have answered between the two dates.
    """

    starting = {}
    ending = {}

    invalid = []

    # Get the starting number of issues
    for nation in requester.dumpManager().nations(date=start):
        # Check if either normal or clean name was provided
        if nation.name in nations or nsapi.clean_format(nation.name) in nations:
            starting[nation.name] = nation.issuesAnswered

    # Get the ending number of issues
    for nation in requester.dumpManager().nations(date=end):
        # Check if either normal or clean name was provided
        if nation.name in nations or nsapi.clean_format(nation.name) in nations:
            ending[nation.name] = nation.issuesAnswered

    # Check/make sure both starting/ending have all the nations
    # (e.g. differences may occur when a nation ceased to exist, was founded, etc)

    # If a nation didnt exist on the start date, it started with 0 answered.
    # If a nation didnt exist on the end date, it must have CTE
    # there is not really an easy way of finding the ending number of issues answered,
    # so we cant really calculate.
    for nationName in nations:
        if nationName not in starting:
            starting[nationName] = 0
        if nationName not in ending:
            starting.pop(nationName)
            # track the invalid nations
            invalid.append(nationName)

    # Calculate the difference between end and start for each nation in
    # starting, which should have identical keys to ending so it doesnt matter
    # which one we iterate through
    delta = {
        nationName: ending[nationName] - starting[nationName] for nationName in starting
    }

    return delta, invalid


def main() -> None:
    """Main method"""

    parser = argparse.ArgumentParser(
        description="Count the issues answered by a set of nations."
    )

    parser.add_argument("start", help="The start date, in YYYY-MM-DD format.")

    parser.add_argument("end", help="The end date, in YYYY-MM-DD format.")

    parser.add_argument(
        "source",
        help=(
            """URL or file name to retrieve nation list from. Expects either
            one or two nations seperated by a tab per line, where the second
            is interpreted as the puppetmaster."""
        ),
    )

    parser.add_argument(
        "-f",
        "--file",
        action="store_true",
        help="Makes the script source from a file instead of URL.",
    )

    parser.add_argument("output", help="File name to write output too.")

    if len(sys.argv) > 1:
        args = parser.parse_args()
    else:
        inputString = input("Arguments: ")
        args = parser.parse_args(shlex.split(inputString))

    requester = nsapi.NSRequester(config.userAgent)

    # XKI Puppet List
    default_source = (
        "https://docs.google.com/spreadsheets/d/e/2PACX-1vSem15AVLXgdjxWBZOnWRFnF6NwkY0gVKPYI8"
        "aWuHJzlbyILBL3o1F5GK1hSK3iiBlXLIZBI5jdpkVr/pub?gid=1588413756&single=true&output=tsv"
    )

    # Get input data
    if args.file:
        with open(nsapi.absolute_path(args.source)) as file:
            nations = [line.split("\t") for line in file.readlines()]
    else:
        text = requests.get(args.source).text
        nations = [line.split("\t") for line in text.split("\r\n")]

    # Convert to puppetmaster dicts
    puppets = {nation[0]: nation[1] if len(nation) > 1 else None for nation in nations}

    # Convert dates to date objects
    start = datetime.date.fromisoformat(args.start)
    end = datetime.date.fromisoformat(args.end)

    counts = count_change(requester, puppets.keys(), start, end)
    changes = counts[0]

    # Collect puppetmaster counts
    collected_count = {puppetmaster: 0 for puppetmaster in puppets.values()}
    for puppet, change in changes.items():
        collected_count[puppets[puppet]] += change

    # Write output
    with open(args.output, "w") as file:
        for puppetmaster, count in collected_count.items():
            print(f"{puppetmaster},{count}", file=file)


# entry point construct
if __name__ == "__main__":
    main()
