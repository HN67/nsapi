"""Determines who you have not endorsed recently among the endorsers of a lead"""

# Import types
from typing import Iterable, List, Set, Tuple

# Import core modules
import logging
import time

# Core library
import nsapi
import config

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)


def uncrossed(
    requester: nsapi.NSRequester, nation: str, lead: str, duration: int = 3600
) -> Iterable[str]:
    """Returns a iterable of non-recently endorsed nations sourced from lead endorsements
    `duration` is the number of seconds to check back in the nation's endo happenings
    """

    # Source endorsement list from lead
    logging.info("Retrieving lead endorser list")
    nations: Set[str] = set(requester.nation(nation).shard("endorsements").split(","))

    # Retrieve recent endo happenings in text form
    timestamp = int(time.time()) - duration
    logging.info("Retrieving endo happenings of nation since %s", timestamp)
    endos: List[str] = [
        happening.text
        for happening in requester.world().happenings(
            view=f"nation.{nation}", filter="endo", sincetime=str(timestamp),
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
    logging.info("Filtering for outgoing endorsements")
    outgoing: Set[str] = set(
        text.split("@@")[3] for text in endos if text.split("@@")[1] == nation
    )

    # Unendorsed is obtained by subtracting the outgoing endorsements from the lead endorsement list
    logging.info("Obtaining uncross endorsed nations")
    unendorsed = nations - outgoing
    return unendorsed


def main() -> None:
    """Main function"""

    # Provide proper user agent to api requester
    requester = nsapi.NSRequester(config.userAgent)

    # Function arguments, could be connected to command line, etc
    nation = "ne hcea"
    lead = "panther"

    # Actually run the bulk logic
    print(uncrossed(requester, nation, lead, duration=3600 * 3))


# Main function convention
if __name__ == "__main__":
    main()
