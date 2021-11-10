"""Checks and verifies a WA roster"""

# TODO List

import argparse
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


def normalize(mapping: t.Mapping[str, str]) -> t.Mapping[str, nsapi.Name]:
    """Normalizes all strings in the given mapping.

    Uses nsapi.Name, and normalizes strs at both levels of nesting.
    """
    return {nsapi.Name(key): nsapi.Name(value) for key, value in mapping.items()}


def normalize_known(
    known: t.Mapping[str, t.Iterable[str]]
) -> t.Dict[str, t.List[nsapi.Name]]:
    """Normalizes all keys and items of each value iterable.

    Produces concrete output

    Uses nsapi.Name.
    """
    return {
        nsapi.Name(key): [nsapi.Name(item) for item in value]
        for key, value in known.items()
    }


def wa_deltas(
    requester: nsapi.NSRequester,
    roster: t.Mapping[str, str],
    known: t.Mapping[str, t.Iterable[str]],
) -> t.Mapping[str, t.Tuple[str, t.Optional[str]]]:
    """Finds the current WA for each member of the roster.

    Returns an (old, new) pair for each member.
    """
    return {
        # Include the nation and its new WA
        # if there is no new WA or it has changed
        nation: (old, new)
        for (nation, old, new) in (
            # Try to find the current WA
            # of a nation, None if the nation isn't in the data
            (
                nation,
                old,
                find_wa(requester, known[nation]),
            )
            if nation in known
            else (nation, old, None)
            for nation, old in roster.items()
        )
    }


def wa_changes(
    deltas: t.Mapping[str, t.Tuple[str, t.Optional[str]]]
) -> t.Mapping[str, t.Optional[str]]:
    """Checks which members have had a change in WA."""
    return {
        nation: new
        for (nation, (old, new)) in deltas.items()
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


T = t.TypeVar("T")


def bubble(top: T, items: t.Iterable[T]) -> t.Iterable[T]:
    """Bubble a specific element to the front of an Iterable.

    Wraps T, but yields top first,
    and will not yield any elements from items
    that are equal to top.
    """
    yield top
    yield from filter(lambda item: item != top, items)


def extract_new(
    deltas: t.Mapping[str, t.Tuple[str, t.Optional[str]]]
) -> t.Mapping[str, str]:
    """Extract new WA from a deltas mapping."""
    return {nation: new for nation, (_, new) in deltas.items() if new is not None}


def reorganize(
    known: t.Mapping[str, t.Iterable[str]],
    new: t.Mapping[str, str],
) -> t.Mapping[str, t.Iterable[str]]:
    """Reorganize known data to have new WAs at the front of puppet lists."""
    return {
        nation: (bubble(new[nation], puppets) if nation in new else puppets)
        for nation, puppets in known.items()
    }


def update_roster(
    oldRosterPath: t.Optional[str],
    outputPath: t.Optional[str],
    dataPath: str,
    newPath: t.Optional[str],
    *,
    parse_old: bool = True,
) -> None:
    """Update a roster using the given paths."""

    requester = nsapi.NSRequester(config.userAgent)

    # Collect data
    with open(dataPath, "r", encoding="utf-8") as file:
        known: t.Mapping[str, t.Collection[str]] = json.load(file)

    # collect current/old roster
    current: t.Mapping[str, str]

    if oldRosterPath:
        with open(oldRosterPath, "r", encoding="utf-8") as file:
            current = read_old_roster(file, parse_old)
    else:
        # read from stdin
        current = read_old_roster(sys.stdin, parse_old)

    # compare
    deltas = wa_deltas(requester, normalize(current), normalize_known(known))
    results = wa_changes(deltas)

    # Summarize results
    if outputPath:
        with open(outputPath, "w", encoding="utf-8") as file:
            print_output(file, results)
    else:
        print_output(sys.stdout, results)

    # Optionally output reorganized known data
    if newPath:
        with open(newPath, "w", encoding="utf-8") as file:
            # Cast iterables to list so they can be serialized
            json.dump(
                normalize_known(
                    reorganize(normalize_known(known), extract_new(deltas))
                ),
                file,
            )


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
        "--new",
        "-n",
        dest="new",
        default=None,
        help="Optional file to write reorganized known data to",
    )
    parser.add_argument(
        "--json",
        "-j",
        dest="as_json",
        action="store_true",
        help="Parse the old roster as JSON instead of bbcode",
    )

    args = parser.parse_args()

    update_roster(
        args.current, args.output, args.roster, args.new, parse_old=not args.as_json
    )


if __name__ == "__main__":
    main()
