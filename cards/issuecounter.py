"""Script utility to track the number of issues answered on nations"""

import argparse
import calendar
import datetime
import logging
import pathlib
import shlex
import sys
import textwrap
import typing as t

import requests

import config
import nsapi

# External data spreadsheets
FORUM_SPREADSHEET = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQolEKIC63tiAK1qpAGac6e-eT99-rjFl6oI8UYf0Rt2CVwWp9KsjOPk8R65O8SS_1yS2Af2fBfR7ly/pub?gid=1835258219&single=true&output=tsv"  # pylint: disable=line-too-long # noqa
PUPPET_SPREADSHEET = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQolEKIC63tiAK1qpAGac6e-eT99-rjFl6oI8UYf0Rt2CVwWp9KsjOPk8R65O8SS_1yS2Af2fBfR7ly/pub?gid=1588413756&single=true&output=tsv"  # pylint: disable=line-too-long # noqa

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

    The returned mapping contains .clean_format version of nation names.
    """

    starting = {}
    ending = {}

    invalid = []

    # Get the starting number of issues
    for nation in requester.dumpManager().nations(date=start):
        # Check if either normal or clean name was provided
        if nation.name in nations or nsapi.clean_format(nation.name) in nations:
            starting[nsapi.clean_format(nation.name)] = nation.issuesAnswered

    # Get the ending number of issues
    for nation in requester.dumpManager().nations(date=end):
        # Check if either normal or clean name was provided
        if nation.name in nations or nsapi.clean_format(nation.name) in nations:
            ending[nsapi.clean_format(nation.name)] = nation.issuesAnswered

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
    # Standardize nation name formatting
    delta = {
        nsapi.clean_format(nationName): ending[nationName] - startCount
        for nationName, startCount in starting.items()
    }

    return delta, invalid


def _get_forum_names() -> t.Mapping[str, str]:
    """Returns a mapping of main nation names to forum usernames.

    If the main nation does not have a forum account, it will not be in the map.

    This method only provides nations part of the XKI Card Coop program.

    Guarenteed to return cleaned format of nation names.
    """
    source = FORUM_SPREADSHEET

    logger.info("Retrieving nation-forum mappings")

    text = requests.get(source).text
    # 2D table: each first-level element is a row,
    # each row contains 1st element main nation and
    # optionally 2nd forum username.
    # If there is no username, the second element should be "", which is falsy
    table = [line.split("\t") for line in text.split("\r\n")]

    usernames = {nsapi.clean_format(row[0]): row[1] for row in table if row[1]}

    logger.info("Retrieved nation-forum mappings")

    return usernames


def generate_report(month: datetime.date, count: t.Mapping[str, int]) -> str:
    """Generates a formatted report string for XKI Card Coop."""

    # Wage constant (Tacos per issue)
    wage = 10

    forum_names = _get_forum_names()

    def tag(nation: str) -> t.Optional[str]:
        """Returns a tag that should ping a nation on the forums.

        Returns None if the nation does not have a forum account.
        """
        # return "@" + "".join(char for char in nation.lower() if char.isalnum())
        return "@" + forum_names[nation] if nation in forum_names else None

    taco = (
        '[img class="smile" style="max-width:100%;" alt=":-X"'
        ' src="http://10000islands.net/gallery/gallery-images/taco.gif"]'
    )
    tdh = '[td style="text-align:center;border:1px solid rgb(255, 255, 255);padding:3px;"]'

    month_name = calendar.month_name[month.month]
    header = "\n".join(
        (
            (
                '[div align="center"][img style="max-width:20%;"'
                ' src="http://10000islands.net/gallery/gallery-images/XKICardsCoop1.png"][/div]'
            ),
            ("\n"),
            (
                f"The following payments were earned in {month_name} {month.year} for "
                " XKI Cards Co-operative card farmers, paid at a"
                " [url=https://10000islands.proboards.com/post/1787776/thread][u]rate"
                f"[/u][/url] of {wage} {taco} per issue answered under"
                " [url=https://10000islands.proboards.com/thread/"
                "39475/312-xki-cards-operative-passed]"
                "[u]NS 312-2[/u][/url]."
            ),
            ("\n\n"),
        )
    )

    rows = []
    inactive = []
    # Create table rows for each active nation
    for nation, issues in count.items():

        # Retrieve the nation forum tag
        nationTag = tag(nation)
        # If the tag is None, fallback on nationname and set payout to NA
        if nationTag is None:
            nationTag = nation
            payout = "N/A"
        else:
            payout = str(issues * wage)

        # Only add the nation to the table if they answered issues
        if issues > 0:
            rows.append(
                textwrap.dedent(
                    f"""\
                    [tr]
                        {tdh}{nationTag}[/td]
                        {tdh}{issues}[/td]
                        {tdh}{payout} {taco}[/td]
                    [/tr]
                    """
                )
            )
        else:
            inactive.append(nationTag)

    body = (
        textwrap.dedent(
            f"""\
            [div align="center"]
            [table style="text-align:center;"][tbody]
            [tr]
                {tdh}[i]Nation[/i][/td]
                {tdh}[i]Issues Answered[/i][/td]
                {tdh}[i]Wage[/i][/td]
            [/tr]
            """
        )
        # Note that each row already has a trailing newline due to the literal above
        + "".join(rows)
        + "[/tbody][/table]\n"
    )

    footer = textwrap.dedent(
        # Note that inactive is made up of strings already passed through the tag method,
        # falling back on original name if no forum name
        f"""\
            [table][tbody]
            [tr]
                {tdh}[i]Total Number of Active Cards Co-op Members[/i][/td]
                {tdh}[i]Total {month_name} Card Farming Pay[/i][/td]
            [/tr]
            [tr]
                {tdh}{len(rows)} card farmers[/td]
                {tdh}{sum(count.values())*10} {taco}[/td]
            [/tr]
            [/tbody][/table]

            The following Cards Co-op members were moved to inactive status:
            {" ".join(nation for nation in inactive)}
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

    subparsers = parser.add_subparsers(
        help="The possible modes, rerun with [mode] -h for more info.",
        dest="sub",
    )

    datesParser = subparsers.add_parser("dates")

    datesParser.add_argument("start", help="The start date, in YYYY-MM-DD format.")

    datesParser.add_argument("end", help="The end date, in YYYY-MM-DD format.")

    datesParser.add_argument(
        "-m",
        "--month",
        help="The month to use for a report. Defaults to month of end date.",
        default=None,
    )

    monthParser = subparsers.add_parser("month")

    monthParser.add_argument(
        "month",
        help=(
            "The month to count across, in YYYY-MM format. "
            "Compares issue counts from YYYY-MM-01 to (MM+1)-01."
        ),
    )

    # monthParser.add_argument(
    parser.add_argument(
        "-r",
        "--report",
        action="store_true",
        help=(
            "Create output in report mode. Produces a formatted file in "
            "Issue Payout Reports folder for the given month. "
            "The report is labelled using the month of the starting date, "
            "unless specified by month parameter."
        ),
    )

    # XKI Puppet List
    default_source = PUPPET_SPREADSHEET

    parser.add_argument(
        "-s",
        "--source",
        help=(
            """URL or file name to retrieve nation list from. Expects either
            one or two nations seperated by a tab per line, where the second
            is interpreted as the puppetmaster. Defaults to the XKI puppets URL."""
        ),
        default=default_source,
    )

    parser.add_argument(
        "-f",
        "--file",
        action="store_true",
        help="Makes the script source from a file instead of URL.",
    )

    parser.add_argument(
        "-o",
        "--output",
        help="File name to write (raw) output to. Outputs to stdout if not provided.",
        default=None,
    )

    if len(sys.argv) > 1:
        args = parser.parse_args()
    else:
        inputString = input("Arguments (One line, -h for help): ")
        args = parser.parse_args(shlex.split(inputString))

    requester = nsapi.NSRequester(config.userAgent)

    # Get input data
    if args.file:
        with open(args.source, "r", encoding="utf-8") as file:
            nations = [line.split("\t") for line in file.readlines()]
    else:
        text = requests.get(args.source).text
        nations = [line.split("\t") for line in text.split("\r\n")]

    # Convert to puppetmaster dicts
    # nation[1] is "" if no master, which is falsy
    # Clean the format of all the names
    puppets = {
        nsapi.clean_format(nation[0]): nsapi.clean_format(nation[1])
        if nation[1]
        else nsapi.clean_format(nation[0])
        for nation in nations
    }

    # Convert dates to start and end date objects
    if args.sub == "dates":
        start = datetime.date.fromisoformat(args.start)
        end = datetime.date.fromisoformat(args.end)
        # Usually makes sense to have the 'month' (for reports) be the ending date if not provided
        if args.month:
            month = datetime.date.fromisoformat(args.month + "-01")
        else:
            month = end.replace(day=1)
    elif args.sub == "month":
        month = datetime.date.fromisoformat(args.month + "-01")
        # Last day of previous month, i.e. 08 -> 07-31
        start = month - datetime.timedelta(days=1)
        # Last day of this month, i.e. 08 -> 08-31
        end = month.replace(day=calendar.monthrange(month.year, month.month)[1])

    logger.info("month: %s start: %s end: %s", month, start, end)

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
        with open(args.output, "w", encoding="utf-8") as file:
            write_output(file)
    else:
        write_output(sys.stdout)

    # Generate report if chosen.
    # Check the subcommand first, because if month
    # wasnt chosen, the .report attribute wont exist
    # this avoids any exception due to lazy eval
    # if args.sub == "month" and args.report:
    if args.report:
        report = generate_report(month, collected_count)
        # Format the month to always be 2-digit
        path = pathlib.Path(
            f"IssuePayoutReports/issuePayoutReport_{month.year}-{month.month:0>2d}.txt"
        )
        # Ensure output directory
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write the report
        with open(path, "w", encoding="utf-8") as f:
            f.write(report)


# entry point construct
if __name__ == "__main__":
    main()
