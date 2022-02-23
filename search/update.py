"""Summarizes NS update, such as delegacy changes"""
# Somethings Wrong lost WA Delegate status in Mesoamerican Confederation.
# @@Hexen 43@@ became WA Delegate of %%The Democracy Pact%%.
# @@Viatta@@ seized the position of %%ASEAN REGION%% WA Delegate from @@New Order Philippines@@.

import argparse
import logging
import re
import sys
import time
import typing as t
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
    requester: nsapi.NSRequester,
    startTime: int = None,
    endTime: int = None,
    duration: int = None,
) -> Iterable[nsapi.Happening]:
    """Obtain all delegacy changes in the requested time period.

    Up to two of startTime, endTime, and duration should be provided.

    End time defaults to now, unless overridden by a combination of start and duration.
    Start time defaults to duration before end time, or 12 hours before end time otherwise.
    If all three arguments are given, duration is ignored.
    """
    # Determine start and end
    if endTime is None:
        if startTime is not None and duration is not None:
            endTime = startTime + duration
        else:
            # Time.time produces a float to represent milli, we just want seconds
            endTime = int(time.time())
    if startTime is None:
        if duration is not None:
            startTime = endTime - duration
        else:
            # 12 hours
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


def write_output(results: t.Iterable[nsapi.Happening], file: t.TextIO) -> None:
    """Print result to a file."""
    print("Delegacy changes in the last twelve hours", file=file)
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
            for happening in results
        ),
        file=file,
    )


def main() -> None:
    """Main function"""

    parser = argparse.ArgumentParser(
        description="Check for WA Delegacy changes.\n",
        epilog=delegacy.__doc__,
    )

    parser.add_argument(
        "-s",
        "--start",
        help="Start time, in timestamp seconds.",
        type=int,
        default=None,
        dest="start",
    )
    parser.add_argument(
        "-e",
        "--end",
        help="End time, in timestamp seconds.",
        type=int,
        default=None,
        dest="end",
    )
    parser.add_argument(
        "-d, --duration",
        help="Duration, in seconds.",
        type=int,
        default=None,
        dest="duration",
    )

    parser.add_argument(
        "-o", "--output", help="Output file to write to.", default=None, dest="output"
    )

    args = parser.parse_args()

    requester = nsapi.NSRequester(config.userAgent)

    results = delegacy(
        requester, startTime=args.start, endTime=args.end, duration=args.duration
    )

    if args.output:
        with open("args.output", "w", encoding="utf-8") as file:
            write_output(results, file)
    else:
        write_output(results, sys.stdout)


if __name__ == "__main__":
    main()
