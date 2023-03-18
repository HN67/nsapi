"""Determines missing crosses on a lead."""

# Import types
import typing as t
from typing import Iterable, List, Set

# Import core modules
import argparse
import logging
import time

# Core library
import nsapi
import config

# Make logger
logger = logging.getLogger()


def uncrossed(
    requester: nsapi.NSRequester, nation: str, lead: str, duration: int = 3600
) -> Iterable[str]:
    """Returns a iterable of non-recently endorsed nations sourced from lead endorsements
    `duration` is the number of seconds to check back in the nation's endo happenings

    NOT SUPER USEFUL
    """

    # Source endorsement list from lead
    logging.info("Retrieving lead endorser list")
    nations: Set[str] = set(requester.nation(lead).shard("endorsements").split(","))

    # Retrieve recent endo happenings in text form
    timestamp = int(time.time()) - duration
    logging.info("Retrieving endo happenings of nation since %s", timestamp)
    endos: List[str] = [
        happening.text
        for happening in requester.world().happenings(
            view=f"nation.{nation}",
            filter="endo",
            sincetime=str(timestamp),
        )
    ]

    # Parse endo happening texts
    # A text can be one of the following two 'distinct' forms:
    # based on 'hn67' == nation
    # '@@hn67@@ endorsed @@hn67_ii@@.' (outgoing)
    # '@@hn67_ii@@ endorsed @@hn67@@.' (incoming)
    # we only care about outgoing endorsements
    # the endorsed nation is retrieved using the following process:
    # .split() transforms the above outgoing example to ['', 'hn67', 'endorsed', 'hn67_ii', '']
    # index [3] retrieves the endorsed nation, index [1] retrieves the endorser
    # [1] is used to verify outgoing ( by checking == nation), and [3] retrieves the endorsee
    # Note: Splitting twice, could be optimized with pre-comprehension, for loop, or walrus operator
    logger.info("Filtering for outgoing endorsements")
    outgoing: Set[str] = set(
        text.split("@@")[3] for text in endos if text.split("@@")[1] == nation
    )

    # Unendorsed is obtained by subtracting the outgoing endorsements from the lead endorsement list
    logger.info("Obtaining uncross endorsed nations")
    unendorsed = nations - outgoing
    return unendorsed


def endorsements(
    requester: nsapi.NSRequester, lead: str
) -> t.Mapping[str, t.Iterable[str]]:
    """Get the endorsements of everyone endorsing a lead."""

    # Get all endorsers of the lead and the lead themself
    endorsers = set(requester.nation(lead).endorsements()) | {lead}
    # Return a mapping of all the endorsements
    return {nation: requester.nation(nation).endorsements() for nation in endorsers}


def missing_crosses(
    reference: t.Mapping[str, t.Iterable[str]]
) -> t.Mapping[str, t.Iterable[str]]:
    """Produce the nations that have not been endorsed by each nation.

    Cross references a mapping of the endorsements of each nation.
    """

    # We need to make sure that the iterable of endorsers is reusable
    # Also make it a set so lookups are faster
    data: t.Mapping[str, t.Set[str]] = {
        nation: set(endorsers) for nation, endorsers in reference.items()
    }

    return {
        # Note: We MUST use a list comprehension here, not a generator,
        # because if we have a lazy iterable, it will use the `nation` closure
        # which will just be the last one in the data
        nation: [
            other
            for (other, existing) in data.items()
            if other != nation and nation not in existing
        ]
        for nation in data.keys()
    }


def main() -> None:
    """Main function"""

    nsapi.enable_logging()

    # Parse nation from command line
    parser = argparse.ArgumentParser(description="Find missing crosses.")
    parser.add_argument(
        "lead", help="Base off of this cross point nation.", default=None
    )
    parser.add_argument(
        "--format",
        help="Format output.",
        action="store_true",
    )
    args = parser.parse_args()

    lead: str = args.lead
    format_output: bool = args.format

    # Provide proper user agent to api requester
    requester = nsapi.NSRequester(config.userAgent)

    # Actually run the bulk logic
    missing = missing_crosses(endorsements(requester, lead))

    # Sort results alphabetically
    sorted_results = sorted(missing.items(), key=lambda pair: pair[0])

    if format_output:
        for nation, task in sorted_results:
            print(f"{nation}:")
            for index, other in enumerate(task, start=1):
                print(f"{index}. https://www.nationstates.net/nation={other}")
    else:
        for nation, task in sorted_results:
            print(f"{nation}: " + ",".join(task))


# Main function convention
if __name__ == "__main__":
    main()
