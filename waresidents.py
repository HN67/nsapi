"""Retrieves the WA residents of a region"""

import logging
from typing import Collection, Iterable

import nsapi

# Set logging level
level = logging.WARNING
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)


def residents(requester: nsapi.NSRequester, region: str) -> Collection[str]:
    """Retrieves the WA residents of the given region."""

    # Retrieve residents
    return set(requester.region(region).nations()) & set(
        requester.wa().shard("members").split(",")
    )


def listLinks(nations: Iterable[str]) -> str:
    """Returns a string containing the given nations formatted into links,
    
    seperated by newlines (with trailing)."""

    return (
        "\n".join(f"https://www.nationstates.net/nation={nsapi.clean_format(nation)}" for nation in nations)
        + "\n"
    )


def main() -> None:
    """Main function, mainly for testing purposes."""

    requester = nsapi.NSRequester("HN67 API Reader")

    print(listLinks(residents(requester, "shinka")))


# Call main if this script is the entrypoint
if __name__ == "__main__":
    main()
