"""Script utility to track the number of issues answered on nations"""

import argparse
import calendar
import datetime
import logging
import os
import shlex
import sys
import textwrap
import typing as t

import requests

import config
import nsapi

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
logger = logging.getLogger()
nsapi.logger.setLevel(level=level)


def count_change(
    requester: nsapi.NSRequester,
    nations: t.Collection[str],
    start: datetime.date,
    end: datetime.date,
) -> t.Tuple[t.Mapping[str, int], t.Iterable[str]]:
    """For each nation provided, retrieves the number of issues
    they have answered between the two dates.
    """

    starting = {}
    ending = {}

    invalid = []

    # Get the starting number of issues
    for nation in requester.dumpManager().nations(date=start):
        # Check if either normal or clean name was provided
        if nation.name in nations or nsapi.clean_format(nation.name) in nations:
            starting[nation.name] = nation.issuesAnswered

    # Get the ending number of issues
    for nation in requester.dumpManager().nations(date=end):
        # Check if either normal or clean name was provided
        if nation.name in nations or nsapi.clean_format(nation.name) in nations:
            ending[nation.name] = nation.issuesAnswered

    # Check/make sure both starting/ending have all the nations
    # (e.g. differences may occur when a nation ceased to exist, was founded, etc)

    # If a nation didnt exist on the start date, it started with 0 answered.
    # If a nation didnt exist on the end date, it must have CTE
    # there is not really an easy way of finding the ending number of issues answered,
    # so we cant really calculate.
    for nationName in nations:
        if nationName not in starting:
            starting[nationName] = 0
        if nationName not in ending:
            starting.pop(nationName)
            # track the invalid nations
            invalid.append(nationName)

    # Calculate the difference between end and start for each nation in
    # starting, which should have identical keys to ending so it doesnt matter
    # which one we iterate through
    delta = {
        nationName: ending[nationName] - starting[nationName] for nationName in starting
    }

    return delta, invalid


def generate_report(month: datetime.date, count: t.Mapping[str, int]) -> str:
    """Generates a formatted report string for XKI Card Coop."""

    # Wage constant (Tacos per issue)
    wage = 10

    def tag(nation: str) -> str:
        """Returns a tag that should ping a nation on the forums.

        Converts to lowercase and removes any non-alphanumeric characters,
        and adds a '@' prefix.
        """
        return "@" + "".join(char for char in nation.lower() if char.isalnum())

    month_name = calendar.month_name[month.month]
    header = textwrap.dedent(
        f"""\
        [div align="center"][img style="max-width:20%;" src="http://10000islands.net/gallery/gallery-images/XKICardsCoop1.png"][/div]

        The following payments were earned in {month_name} {month.year} for XKI Cards Co-operative card farmers, paid at a [url=https://10000islands.proboards.com/post/1787776/thread][u]rate[/u][/url] of 10 [img class="smile" style="max-width:100%;" alt=":-X" src="http://10000islands.net/gallery/gallery-images/taco.gif"] per issue answered under [url=https://10000islands.proboards.com/thread/39475/312-xki-cards-operative-passed][u]NS 312-2[/u][/url].

        """
    )

    rows = []
    inactive = []
    # Create table rows for each active nation
    for nation, issues in count.items():
        if issues > 0:
            rows.append(
                textwrap.dedent(
                    f"""\
                    [tr]
                        [td style="text-align:center;border:1px solid rgb(255, 255, 255);padding:3px;"]{tag(nation)} [/td]
                        [td style="text-align:center;border:1px solid rgb(255, 255, 255);padding:3px;"]{issues} Issues Answered[/td]
                        [td style="text-align:center;border:1px solid rgb(255, 255, 255);padding:3px;"]{issues*wage} [img class="smile" style="max-width:100%;" alt=":-X" src="http://10000islands.net/gallery/gallery-images/taco.gif"][/td]
                    [/tr]
                    """
                )
            )
        else:
            inactive.append(nation)

    body = (
        textwrap.dedent(
            """\
            [div align="center"]
            [table style="text-align:center;"][tbody]
            [tr]
                [td style="text-align:center;border:1px solid rgb(255, 255, 255);padding:3px;"][i]Nation[/i][/td]
                [td style="text-align:center;border:1px solid rgb(255, 255, 255);padding:3px;"][i]Issues Answered[/i][/td]
                [td style="text-align:center;border:1px solid rgb(255, 255, 255);padding:3px;"][i]Wage[/i][/td]
            [/tr]
            """
        )
        # Note that each row already has a trailing newline due to the literal above
        + "".join(rows)
        + "[/tbody][/table]\n"
    )

    footer = textwrap.dedent(
        f"""\
            [table][tbody]
            [tr]
                [td style="text-align:center;border:1px solid rgb(255, 255, 255);padding:3px;"][i]Total Number of Active Cards Co-op Members[/i][/td]
                [td style="text-align:center;border:1px solid rgb(255, 255, 255);padding:3px;"][i]Total {month_name} Card Farming Pay[/i][/td]
            [/tr]
            [tr]
                [td style="text-align:center;border:1px solid rgb(255, 255, 255);padding:3px;"]{len(rows)} card farmers[/td]
                [td style="text-align:center;border:1px solid rgb(255, 255, 255);padding:3px;"]{sum(count.values())*10} [img class="smile" style="max-width:100%;" alt=":-X" src="http://10000islands.net/gallery/gallery-images/taco.gif"][/td]
            [/tr]
            [/tbody][/table]

            The following Cards Co-op members were moved to inactive status:
            {"".join(tag(nation) for nation in inactive)}
            [/div]
        """
    )

    return header + body + footer


def main() -> None:
    """Main method"""

    # TODO add type checking into the arguments?
    # would possibly provide better error messages

    parser = argparse.ArgumentParser(
        description="Count the issues answered by a set of nations."
    )

    # TODO add subcommands
    # dates (takes two dates) and month (takes 1 year-month)

    # output can be optional (default is based on mode)
    # maybe have source be optional? for XKI there is a reasonable default, but not in general
    # have option to read config file?

    # add option to generate formatted post output

    subparsers = parser.add_subparsers(
        help="The possible modes, rerun with [mode] -h for more info.", dest="sub",
    )

    datesParser = subparsers.add_parser("dates")

    datesParser.add_argument("start", help="The start date, in YYYY-MM-DD format.")

    datesParser.add_argument("end", help="The end date, in YYYY-MM-DD format.")

    monthParser = subparsers.add_parser("month")

    monthParser.add_argument(
        "month",
        help=(
            "The month to count across, in YYYY-MM format. "
            "Compares issue counts from YYYY-MM-01 to (MM+1)-01."
        ),
    )

    # TODO probably change this and the output check back to month only

    # monthParser.add_argument(
    parser.add_argument(
        "-r",
        "--report",
        action="store_true",
        help=(
            "Create output in report mode. Produces a formatted file in "
            "Issue Payout Reports folder for the given month."
        ),
    )

    parser.add_argument(
        "source",
        help=(
            """URL or file name to retrieve nation list from. Expects either
            one or two nations seperated by a tab per line, where the second
            is interpreted as the puppetmaster."""
        ),
    )

    parser.add_argument(
        "-f",
        "--file",
        action="store_true",
        help="Makes the script source from a file instead of URL.",
    )

    # TODO consider the output argument and its style

    parser.add_argument(
        "output",
        help="File name to write (raw) output to. Outputs to stdout if not provided.",
        nargs="?",
        default=None,
    )

    if len(sys.argv) > 1:
        args = parser.parse_args()
    else:
        inputString = input("Arguments (One line, -h for help): ")
        args = parser.parse_args(shlex.split(inputString))

    requester = nsapi.NSRequester(config.userAgent)

    # XKI Puppet List
    default_source = (
        "https://docs.google.com/spreadsheets/d/e/2PACX-1vSem15AVLXgdjxWBZOnWRFnF6NwkY0gVKPYI8"
        "aWuHJzlbyILBL3o1F5GK1hSK3iiBlXLIZBI5jdpkVr/pub?gid=1588413756&single=true&output=tsv"
    )

    # Get input data
    if args.file:
        with open(nsapi.absolute_path(args.source)) as file:
            nations = [line.split("\t") for line in file.readlines()]
    else:
        text = requests.get(args.source).text
        nations = [line.split("\t") for line in text.split("\r\n")]

    # Convert to puppetmaster dicts
    puppets = {
        nation[0]: nation[1] if len(nation) > 1 else nation[0] for nation in nations
    }

    # Convert dates to start and end date objects
    if args.sub == "dates":
        start = datetime.date.fromisoformat(args.start)
        end = datetime.date.fromisoformat(args.end)
    elif args.sub == "month":
        start = datetime.date.fromisoformat(args.month + "-01")
        # There are already general solutions to add months to a date,
        # such as the library dateutil (with its relativedelta), but
        # since this is a small script, the goal is to have fewer dependencies.
        # To that end, we homeroll a small formula. If the nsapi project and interactions
        # with datetime continue to grow, a dependency such as dateutil may eventually have
        # justification to be added.
        # The logic used here to get the next month is not at all general,
        # however, we can make several assumptions since we are not working with
        # an arbitrary date.
        # We know every month has day 1, so we dont need to worry about 31 -> 28 for instance.
        # One edgecase that must be handled is when start month is 12, then end -> 1 (not 13)
        # and year is incremented.
        # We add start.month // 12 to the year, since month is in [1, 12]. If month is [1, 11],
        # then // 12 is 0, if month == 12, then // 12 is 1, which is desired because we are adding
        # a month to 12 (December) so the year should increment.
        # To calculate the month we use % (modulo) to do wraparound, but % wrap only works
        # on 0-index sets, so we convert to [0, 11] first, add 1, modulate, and then convert back,
        # with (start.month - 1 + 1) % 12 + 1, which is equiv to start.month % 12 + 1
        end = datetime.date(start.year + start.month // 12, start.month % 12 + 1, 1)

    counts = count_change(requester, puppets.keys(), start, end)
    changes = counts[0]

    # Collect puppetmaster counts
    collected_count = {puppetmaster: 0 for puppetmaster in puppets.values()}
    for puppet, change in changes.items():
        collected_count[puppets[puppet]] += change

    def write_output(file: t.TextIO) -> None:
        for puppetmaster, count in collected_count.items():
            print(f"{puppetmaster},{count}", file=file)

    # Write output
    if args.output is not None:
        with open(args.output, "w") as file:
            write_output(file)
    else:
        write_output(sys.stdout)

    # TODO report formatting 2 issues:
    # line indendation is weird (maybe not a real issue)
    # account tags probably need to be formatted better (e.g. lower, no space)

    # Generate report if chosen.
    # Check the subcommand first, because if month
    # wasnt chosen, the .report attribute wont exist
    # this avoids any exception due to lazy eval
    # if args.sub == "month" and args.report:
    if args.report:
        report = generate_report(start, collected_count)
        # Check for output directory
        if not os.path.isdir(nsapi.absolute_path("IssuePayoutReports")):
            os.mkdir(nsapi.absolute_path("IssuePayoutReports"))
        # Write the report
        with open(
            nsapi.absolute_path(
                # Format the month to always be 2-digit
                f"IssuePayoutReports/issuePayoutReport_{start.year}-{start.month:0>2d}.txt"
            ),
            "w",
        ) as f:
            f.write(report)


# entry point construct
if __name__ == "__main__":
    main()
