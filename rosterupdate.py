"""Checks and verifies a WA roster"""

import argparse
import dataclasses
import json
import logging
import sys
import typing as t

import config
import nsapi

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)


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


def main(
    oldRosterPath: t.Optional[str], outputPath: t.Optional[str], dataPath: str
) -> None:
    """Main function"""

    requester = nsapi.NSRequester(config.userAgent)

    # Collect data
    with open(nsapi.absolute_path(dataPath), "r") as file:
        nations: t.Mapping[str, t.Collection[str]] = json.load(file)

    # collect current/old roster
    current: t.Mapping[str, str]
    if oldRosterPath:
        with open(nsapi.absolute_path(oldRosterPath), "r") as file:
            current = json.load(file)
    else:
        # read from stdin
        current = json.load(sys.stdin)

    # search for current wa
    output = check_roster(requester, nations)

    # compare
    changes = {
        nation: output[nation] if nation in output else Result(None)
        for nation, oldWA in current.items()
        if nation not in output or output[nation].wa != oldWA
    }

    # Summarize results
    if outputPath:
        with open(nsapi.absolute_path(outputPath), "w") as file:
            print_output(file, changes)
    else:
        print_output(sys.stdout, changes)


if __name__ == "__main__":

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

    args = parser.parse_args()

    main(args.current, args.output, args.roster)
