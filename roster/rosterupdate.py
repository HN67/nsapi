"""Checks and verifies a WA roster"""

import argparse
import dataclasses
import json
import logging
import sys
import typing as t

import config
import nsapi

from roster import rosterread

# Name logger
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


@dataclasses.dataclass()
class Result:
    """Class containing resulting data from check_roster method."""

    wa: t.Optional[str]


def is_wa(requester: nsapi.NSRequester, nation: str) -> bool:
    """Checks if the nation is in the WA"""
    try:
        return requester.nation(nation).wa().startswith("WA")
    except nsapi.ResourceError:
        return False


def check_roster(
    requester: nsapi.NSRequester, nations: t.Mapping[str, t.Collection[str]]
) -> t.Mapping[str, Result]:
    """Checks for the WA of each nation.

    Checks the main nation, and the list of puppets.
    If none are in the WA, prompts for a new nation.
    """
    output = {}
    for nation, puppets in nations.items():
        # Find current WA nation(s): SHOULD NOT BE PLURAL, WARN IF SO
        WAs = []
        if is_wa(requester, nation):
            WAs.append(nation)
        WAs.extend(puppet for puppet in puppets if is_wa(requester, puppet))
        # Warn if len > 1
        if len(WAs) > 1:
            print(f"WARNING: {nation} has multiple WA nations: {WAs}")
        # Construct Result object
        if WAs:
            result = Result(nsapi.clean_format(WAs[0]))
        else:
            result = Result(None)
        output[nsapi.clean_format(nation)] = result
    return output


def print_output(file: t.TextIO, output: t.Mapping[str, Result]) -> None:
    """Prints output to to given stream"""
    sortedOutput: t.List[t.Tuple[str, Result]] = sorted(
        output.items(), key=lambda pair: pair[0]
    )
    for nation, result in sortedOutput:
        if result.wa:
            print(f"{nation} - {result.wa}", file=file)
        else:
            print(f"{nation} - Unknown WA", file=file)


def compare_wa(
    old: t.Mapping[str, str], activeWA: t.Mapping[str, Result]
) -> t.Mapping[str, Result]:
    """Compares old WA data to scraped active WA data.

    Returns a nation only if its WA has changed.
    """
    return {
        # map to current wa if exists
        nation: activeWA[nation] if nation in activeWA else Result(None)
        # iterate over the "old" data usually copied from roster
        for nation, oldWA in old.items()
        # filter to only keep nations that either arent tracked in active
        # or have had their wa change
        if nation not in activeWA or activeWA[nation].wa != oldWA
    }


def read_old_roster(file: t.TextIO, is_raw: bool = True) -> t.Mapping[str, str]:
    """Reads the old/current roster from an open file,
    converting from bbcode to JSON if requested.
    """
    if is_raw:
        return rosterread.read_plain(file.readlines())
    else:
        return json.load(file)


def update_roster(
    oldRosterPath: t.Optional[str],
    outputPath: t.Optional[str],
    dataPath: str,
    *,
    parse_old: bool = True,
) -> None:
    """Update a roster using the given paths."""

    requester = nsapi.NSRequester(config.userAgent)

    # Collect data
    with open(dataPath, "r") as file:
        nations: t.Mapping[str, t.Collection[str]] = json.load(file)

    # collect current/old roster
    current: t.Mapping[str, str]

    if oldRosterPath:
        with open(oldRosterPath, "r") as file:
            current = read_old_roster(file, parse_old)
    else:
        # read from stdin
        current = read_old_roster(sys.stdin, parse_old)

    # search for current wa
    output = check_roster(requester, nations)

    # compare
    changes = compare_wa(current, output)

    # Summarize results
    if outputPath:
        with open(outputPath, "w") as file:
            print_output(file, changes)
    else:
        print_output(sys.stdout, changes)


def main() -> None:
    """Main function"""

    nsapi.enable_logging()

    parser = argparse.ArgumentParser(description="Update a WA roster.")
    parser.add_argument("roster", help="File containing puppet lists, in JSON form.")
    parser.add_argument(
        "--current",
        "-c",
        dest="current",
        default=None,
        help="File to read current roster from, instead of stdin",
    )
    parser.add_argument(
        "--output",
        "-o",
        dest="output",
        default=None,
        help="File to output to, instead of stdout",
    )
    parser.add_argument(
        "--json",
        "-j",
        dest="as_json",
        action="store_true",
        help="Parse the old roster as JSON instead of bbcode",
    )

    args = parser.parse_args()

    update_roster(args.current, args.output, args.roster, parse_old=not args.as_json)


if __name__ == "__main__":
    main()
