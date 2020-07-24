"""Iterates through the nations of a region to check who is involved in trading cards"""

from typing import Sequence

import config
import nsapi


def check_region(requester: nsapi.NSRequester, region: str) -> Sequence[str]:
    """Checks all nations in the specified region for trading card activity.
    Makes 1 + region population requests (1 for each nation).
    """
    participants = []

    residents = requester.region(region).shard("nations").split(":")
    for nation in residents:
        info = requester.nation(nation).deck_info()
        if info.numCards > 0 or info.bank > 0 or info.lastValued or info.lastPackOpened:
            participants.append(nation)

    return participants


def main() -> None:
    """Main function"""

    requester = nsapi.NSRequester(config.userAgent)

    region = "10000_islands"

    participants = check_region(requester, region)

    with open(nsapi.absolute_path("participants.txt"), "w") as file:
        for participant in participants:
            print(f"[nation]{participant}[/nation]", file=file)


if __name__ == "__main__":
    main()
