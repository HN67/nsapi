"""Use a roster file to find who is deployed in regions."""

import argparse
import json
import logging
import sys
import typing as t

import config
import nsapi

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def deployed(
    requester: nsapi.NSRequester,
    lead: str,
    roster: t.Mapping[str, t.Iterable[str]],
) -> t.Collection[str]:
    """Determine who are deployed and endorsing the lead."""
    # Obtain endorsement list of lead
    endos = map(nsapi.clean_format, requester.nation(lead).endorsements())
    # Invert roster into puppet -> main form
    owners = {
        nsapi.clean_format(switcher): main
        for main, switchers in roster.items()
        for switcher in switchers
    }
    # Also include main nations
    owners.update({main: main for main in roster.keys()})
    # Return owners who have a nation endoing lead
    return [owners[nation] for nation in endos if nation in owners]


def deployments(
    requester: nsapi.NSRequester,
    leads: t.Iterable[str],
    roster: t.Mapping[str, t.Iterable[str]],
) -> t.Mapping[str, t.Collection[str]]:
    """Determine who is endorsing for each lead.

    Returns a compound mapping which maps from leads to members endorsing that lead.

    The provided switcher iterables in the roster must be reusable.
    """
    return {lead: deployed(requester, lead, roster) for lead in leads}


def format_deployed(lead: str, members: t.Collection[str]) -> str:
    """Format the deployed members into a printable list."""
    return f"{lead} ({len(members)}): " + ", ".join(members)


def main() -> None:
    """Execute main module operations."""
    nsapi.enable_logging()

    parser = argparse.ArgumentParser(
        description="""
            Determine which nations are deployed.
            Takes roster data from stdin and outputs results to stdout.
        """
    )
    parser.add_argument(
        "leads", nargs="*", metavar="lead", help="Lead nations to check."
    )

    args = parser.parse_args()

    roster = json.load(sys.stdin)

    requester = nsapi.NSRequester(config.userAgent)

    deploys = deployments(requester, args.leads, roster)

    for lead, endos in deploys.items():
        print(format_deployed(lead, endos))


if __name__ == "__main__":
    main()
