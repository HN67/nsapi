"""Finds and collects endings/CTE from NationStates"""

# Import standard modules
import dataclasses
import datetime
import logging
import re
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
    and `since` defaults to 24 hours before `before`.
    """

    # Define default window in seconds
    DEFAULT_WINDOW = 24 * 3600

    # Check for before default
    if before:
        beforetime = before
    else:
        beforetime = int(time.time())

    # Check for since default
    if since:
        sincetime = since
    else:
        sincetime = beforetime - DEFAULT_WINDOW

    # Retrieve endings happening data
    happenings = requester.world().happenings(
        safe=False, filter="cte", sincetime=str(sincetime), beforetime=str(beforetime)
    )

    output = []
    for happ in happenings:
        # Try to match the two patterns
        nationMatch = re.search(r"@@(.*)@@", happ.text)
        regionMatch = re.search(r"%%(.*)%%", happ.text)
        if nationMatch and regionMatch:
            # Pull the first group of each match, i.e. omit the @@/%% delimiters
            output.append(Ending(nation=nationMatch[1], region=regionMatch[1]))
        else:
            logging.warning(
                "Found CTE happening with no nation or no region: %s", happ.text
            )

    return output


# https://www.nationstates.net/cgi-bin/api.cgi?q=happenings;view=nation.Faber-of-will-and-might
def founder_endings(
    requester: nsapi.NSRequester,
    since: t.Optional[int] = None,
    before: t.Optional[int] = None,
    referenceDate: datetime.date = None,
) -> t.Iterable[Ending]:
    """Returns the founder endings in the given timestamp frame.

    `before` defaults to now,
    and `since` defaults to 24 hours ago.

    Uses the given referenceDate to retrive a region dump to cross-reference
    with endings with region founders (defaults to most recent dump).
    """

    endings = retrieve_endings(requester, since, before)
    # convert endings to nation: region map
    endingRegions = {
        nsapi.clean_format(ending.nation): ending.region for ending in endings
    }

    # cross reference with region dump
    founderEndings = (
        Ending(
            nation=nsapi.clean_format(region.founder),
            region=endingRegions[nsapi.clean_format(region.founder)],
        )
        for region in requester.dumpManager().regions(date=referenceDate)
        if nsapi.clean_format(region.founder) in endingRegions.keys()
    )

    return founderEndings


def main() -> None:
    """Main method"""

    requester = nsapi.NSRequester(config.userAgent)

    endings = founder_endings(requester)

    # Define default window in seconds
    # DEFAULT_WINDOW = 24 * 3600
    # beforetime = int(time.time())
    # sincetime = beforetime - DEFAULT_WINDOW

    # # Retrieve endings happening data
    # happenings = requester.world().happenings(
    #     safe=False, sincetime=str(sincetime), beforetime=str(beforetime)
    # )

    print(list(endings))

    # with open("test.txt", "w") as file:
    #     for ending in retrieve_endings(requester):
    #         print(f"{ending.nation},", file=file, end="")


if __name__ == "__main__":
    main()
