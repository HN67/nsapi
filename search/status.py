"""Checks the status of a list of nations."""

import argparse
import dataclasses
import itertools
import logging
import os
import shlex
import sys
import typing as t

import requests

import config
import nsapi

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
logger = logging.getLogger()
nsapi.logger.setLevel(level=level)


@dataclasses.dataclass()
class Status:
    """Contains information on the status of a nation."""

    name: str

    cte: bool

    region: t.Optional[str]
    wa: t.Optional[str]


def retrieve_status(requester: nsapi.NSRequester, nation: str) -> Status:
    """Retrieves info on the nation provided."""

    # Check region, wa, and cte
    try:
        shard_info = requester.nation(nation).shards("region", "wa")
    except nsapi.ResourceError:
        return Status(nsapi.clean_format(nation), True, None, None,)
    else:
        return Status(
            nsapi.clean_format(nation),
            False,
            shard_info["region"],
            shard_info["unstatus"],
        )


def retrieve_statuses(
    requester: nsapi.NSRequester, nations: t.Iterable[str]
) -> t.Mapping[str, Status]:
    """Retrieves info of each nation provided."""

    return {nation: retrieve_status(requester, nation) for nation in nations}


def xki_label(status: Status) -> str:
    """Constructs a label for the status, based on its relation to XKI.

    If .cte is true, returns "CTE".
    If .region is '10000 Islands', returns "Islander", else "Friend"
    but if .wa starts with 'WA' (i.e. wa member), prefixs "WA ".
    """
    if status.cte:
        return "CTE"
    output = "Islander" if status.region == "10000 Islands" else "Friend"
    if status.wa and status.wa.startswith("WA"):
        output = "WA " + output

    return output


def report_status(
    requester: nsapi.NSRequester, table: t.Iterable[t.Sequence[str]]
) -> t.Iterable[t.Sequence[str]]:
    """Parses a table (such as sourced from csv), and returns columns reporting nation status.

    The returned iterable represents a iterable of rows in the same order as input.
    """

    iterator = iter(table)
    header = next(iterator)

    # Expected headers:
    # username, forum, nation
    # use username as primary key
    # usernameIndex = header.index("username")
    # forumIndex = header.index("forum")
    nationIndex = header.index("nation")

    # define output headers
    output = [("link", "cte", "region", "wa", "label")]

    link = "https://www.nationstates.net/nation={}"

    for row in iterator:
        nation = row[nationIndex]
        status = retrieve_status(requester, nation)
        output.append(
            (
                link.format(nsapi.clean_format(nation)),
                str(status.cte),
                str(status.region),
                str(status.wa),
                xki_label(status),
            )
        )

    return output


def main(argv: t.Optional[t.Sequence[str]] = None) -> None:
    """Main function.

    If args is provided, it is passed to the argparser.
    Otherwise, first falls back on sys.argv, and then stdin.
    """

    delim = "\t"

    parser = argparse.ArgumentParser(
        description="Checks the status of a list of nations."
    )

    parser.add_argument(
        "source",
        help="""File name or URL to retrieve data from. Expects a tsv formatted file,
            with the first row being a header including 'nation'. The output will be this data
            with the new data columns appended.
        """,
    )

    parser.add_argument(
        "-u",
        "--url",
        action="store_true",
        help="Specifies to treat the source argument as a URL, instead of file path.",
    )

    parser.add_argument(
        "output", help="""File path to write output table to. Outputs a tsv file."""
    )

    # Parse args, checking argument, then sys, then stdin
    if argv:
        args = parser.parse_args(argv)
    elif len(sys.argv) > 1:
        args = parser.parse_args()
    else:
        inputString = input("Arguments (One line, -h for help): ")
        args = parser.parse_args(shlex.split(inputString))

    # Get input data
    if args.url:
        text = requests.get(args.source).text
        table = [line.split(delim) for line in text.splitlines()]
    else:
        with open(args.source) as file:
            table = [line.strip().split(delim) for line in file.readlines()]

    # Create requester
    requester = nsapi.NSRequester(config.userAgent)

    output = report_status(requester, table)

    # Define generator
    combined = (
        itertools.chain.from_iterable(twopart) for twopart in zip(table, output)
    )

    # Write output
    logging.info("Writing output to %s", os.path.abspath(args.output))
    with open(args.output, "w") as file:
        for line in combined:
            print("\t".join(line), file=file)


if __name__ == "__main__":
    main()
