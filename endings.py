"""Finds and collects endings/CTE from NationStates"""

# Import logging
import dataclasses
import logging
import time
import typing as t

# Import nsapi
import nsapi
import config

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)


@dataclasses.dataclass()
class Ending:
    """Represents an Ending/CTE of a nation, includes the nation and region."""

    nation: str
    region: str


def retrieve_endings(
    requester: nsapi.NSRequester,
    since: t.Optional[int] = None,
    before: t.Optional[int] = None,
) -> t.Iterable[Ending]:
    """Returns the endings in the given timestamp frame.

    `before` defaults to now,
    and `since` defaults to 24 hours ago.
    """

    # Define default window in seconds
    DEFAULT_WINDOW = 24 * 3600

    # Check for since default
    if since:
        sincetime = str(since)
    else:
        sincetime = str(int(time.time()) - DEFAULT_WINDOW)

    # Check for before default
    if before:
        beforetime = str(before)
    else:
        beforetime = str(int(time.time()))

    # Retrieve endings happening data
    endings = requester.world().happenings(
        safe=False, filter="cte", sincetime=sincetime, beforetime=beforetime
    )

    return endings


# https://www.nationstates.net/cgi-bin/api.cgi?q=happenings;view=nation.Faber-of-will-and-might


def founder_endings(
    requester: nsapi.NSRequester,
    since: t.Optional[int] = None,
    before: t.Optional[int] = None,
) -> t.Sequence[Ending]:
    """Returns the founder endings in the given timestamp frame.

    `before` defaults to now,
    and `since` defaults to 24 hours ago.
    """


def main() -> None:
    """Main method"""


if __name__ == "__main__":
    main()
