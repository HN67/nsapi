"""Checks and verifies a WA roster"""
import dataclasses
import json
import logging
import sys
import typing as t

import config
import nsapi

# Set logging level
level = logging.WARNING
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
            result = Result(WAs[0])
        else:
            result = Result(None)
        output[nation] = result
    return output


def print_output(file: t.TextIO, output: t.Mapping[str, Result]) -> None:
    """Prints output to to given stream"""
    sortedOutput: t.List[t.Tuple[str, Result]] = sorted(
        output.items(), key=lambda pair: pair[0]
    )
    for nation, result in sortedOutput:
        if result.wa:
            print(f"{nation}: {result.wa}", file=file)
        else:
            print(f"{nation}: No known WA", file=file)


def main() -> None:
    """Main function"""

    print(
        "Specify a json file to load the nation data from. (Based on this script's directory)"
    )
    inputPath = input("File: ")

    print(
        "\nEnter a file to generate output in, or enter nothing to output to standard output."
    )
    outputPath = input("Output File: ")

    requester = nsapi.NSRequester(config.userAgent)

    # Collect data
    with open(nsapi.absolute_path(inputPath), "r") as file:
        nations: t.Mapping[str, t.Collection[str]] = json.load(file)

    output = check_roster(requester, nations)

    # Summarize results
    if outputPath != "":
        with open(nsapi.absolute_path(outputPath), "w") as file:
            print_output(file, output)
    else:
        print_output(sys.stdout, output)


if __name__ == "__main__":
    main()
