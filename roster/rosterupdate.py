"""Checks and verifies a WA roster"""

# TODO List
# Add feature to output new roster.json with reordered puppet lists,
# i.e. located WA at the top

import argparse
import itertools
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


def is_wa(requester: nsapi.NSRequester, nation: str) -> bool:
    """Checks if the nation is in the WA"""
    try:
        return requester.nation(nation).wa().startswith("WA")
    except nsapi.ResourceError:
        return False


def find_wa(requester: nsapi.NSRequester, nations: t.Iterable[str]) -> t.Optional[str]:
    """Lazily search the iterable until a WA nation is found.

    Returns None if none of the nations are in the WA.
    """
    for nation in nations:
        if is_wa(requester, nation):
            return nation
    return None


def read_old_roster(file: t.TextIO, is_raw: bool = True) -> t.Mapping[str, str]:
    """Reads the old/current roster from an open file,
    converting from bbcode to JSON if requested.
    """
    if is_raw:
        return rosterread.read_plain(file.readlines())
    else:
        return json.load(file)


def normalize(mapping: t.Mapping[str, str]) -> t.Mapping[str, str]:
    """Normalizes all strings in the given mapping.

    Uses nsapi.clean_format, and normalizes strs at both levels of nesting.
    """
    return {
        nsapi.clean_format(key): (
            nsapi.clean_format(value) if value is not None else None
        )
        for key, value in mapping.items()
    }


def normalize_roster(
    lists: t.Mapping[str, t.Iterable[str]]
) -> t.Mapping[str, t.Iterable[str]]:
    """Normalizes all keys and items of each value iterable.

    Uses nsapi.clean_format.
    """
    return {
        nsapi.clean_format(key): (nsapi.clean_format(item) for item in value)
        for key, value in lists.items()
    }


def compare_wa(
    requester: nsapi.NSRequester,
    last: t.Mapping[str, str],
    nations: t.Mapping[str, t.Iterable[str]],
) -> t.Mapping[str, t.Optional[str]]:
    """Compares old WA data to scraped active WA data.

    Returns a nation only if its WA has changed.
    """
    return {
        # Include the nation and its new WA
        # if there is no new WA or it has changed
        nation: new
        for (nation, old, new) in (
            # Try to find the current WA
            # of a nation, None if the nation isn't in the data
            (
                nation,
                old,
                find_wa(requester, itertools.chain([nation], nations[nation])),
            )
            if nation in nations
            else (nation, old, None)
            for nation, old in last.items()
        )
        if new is None or old != new
    }


def print_output(file: t.TextIO, output: t.Mapping[str, t.Optional[str]]) -> None:
    """Prints output to to given stream"""
    sortedOutput: t.List[t.Tuple[str, t.Optional[str]]] = sorted(
        output.items(), key=lambda pair: pair[0]
    )
    for nation, wa in sortedOutput:
        if wa:
            print(f"{nation} - {wa}", file=file)
        else:
            print(f"{nation} - Unknown WA", file=file)


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
    with open(dataPath, "r", encoding="utf-8") as file:
        nations: t.Mapping[str, t.Collection[str]] = json.load(file)

    # collect current/old roster
    current: t.Mapping[str, str]

    if oldRosterPath:
        with open(oldRosterPath, "r", encoding="utf-8") as file:
            current = read_old_roster(file, parse_old)
    else:
        # read from stdin
        current = read_old_roster(sys.stdin, parse_old)

    # compare
    changes = compare_wa(requester, normalize(current), normalize_roster(nations))

    # Summarize results
    if outputPath:
        with open(outputPath, "w", encoding="utf-8") as file:
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
