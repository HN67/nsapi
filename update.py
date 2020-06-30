"""Summarizes NS update, such as delegacy changes"""
# Somethings Wrong lost WA Delegate status in Mesoamerican Confederation.
# @@Hexen 43@@ became WA Delegate of %%The Democracy Pact%%.
# @@Viatta@@ seized the position of %%ASEAN REGION%% WA Delegate from @@New Order Philippines@@.

import logging
import re
import time
from typing import Iterable

import config
import nsapi

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)


def delegacy(
    requester: nsapi.NSRequester, startTime: int = None, endTime: int = None
) -> Iterable[nsapi.Happening]:
    """Returns all delegacy changes between start and end times (as epoch timestamps),
    endTime defaults to now, and startTime defaults to 12 hours before endTime
    """
    # Set start/end defaults
    if not endTime:
        # Time.time produces a float to represent milli, we just want seconds
        endTime = int(time.time())
    if not startTime:
        # 12 hours, 3600 seconds an hour, 12 hours previous
        startTime = endTime - 12 * 3600
    # Filter happenings
    return [
        happening
        for happening in requester.world().happenings(
            safe=False,
            sincetime=str(startTime),
            beforetime=str(endTime),
            filter="member",
        )
        if "WA Delegate" in happening.text
    ]


def main() -> None:
    """Main function"""

    requester = nsapi.NSRequester(config.userAgent)
    with open(nsapi.absolute_path("delegacy.txt"), "w") as f:
        logging.info("Outputting to file.")
        print("Delegacy changes in the last twelve hours")
        print(
            "\n".join(
                re.sub(
                    # In the text returned by NS api, nation names are enclosed by @@
                    # and region names by %%. @@(.*?)@@ is a regex pattern that matches
                    # anything surrounded by the @@, as well as the @@ @@. we pull the nation name
                    # by taking group 1 of the match (0 is the entire match).
                    # the nation name is a group because of the () surround the .*?
                    # .*? lazily matches any number of any characters
                    "%%(.*?)%%",
                    lambda match: f"https://www.nationstates.net/region={match.group(1)}",
                    re.sub(
                        "@@(.*?)@@",
                        lambda match: f"https://www.nationstates.net/nation={match.group(1)}",
                        happening.text,
                    ),
                )
                for happening in delegacy(requester)
            ),
            file=f,
        )


if __name__ == "__main__":
    main()
