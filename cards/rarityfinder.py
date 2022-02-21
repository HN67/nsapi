"""Private utility script for generating JSON lists of cards of a certain rarity"""

import json
import os
from typing import Mapping, Sequence

import config
import nsapi


def resolve_path(rarity: str) -> str:
    """Generates an absolute path using the rarity name"""
    return f"{rarity}Cards.json"


def verify_rarity_data(requester: nsapi.NSRequester, rarity: str) -> None:
    """Ensures that the rarity data has been generated."""
    if not os.path.isfile(resolve_path(rarity)):
        find_rarities(requester, rarity)


def load_rarity_data(rarity: str) -> Sequence[Mapping[str, str]]:
    """Attempts to load the given rarity data. The data should be
    verified with `verify_rarity_data` first.
    """
    with open(resolve_path(rarity), encoding="utf-8") as file:
        return json.load(file)


def find_rarities(requester: nsapi.NSRequester, rarity: str) -> None:
    """Searches both card dumps for cards of the specified rarity
    and saves the id/season to a file of the same name"""

    # Goes through each dump, grabbing any CardStandard that has the right rarity
    # store season with it, since the CardStandard does not have season
    cards = []
    for card in requester.dumpManager().cards(season="1"):
        if card.rarity == rarity:
            cards.append((card, "1"))
    for card in requester.dumpManager().cards(season="2"):
        if card.rarity == rarity:
            cards.append((card, "2"))

    # Dump everything as strings so its easier to use
    with open(resolve_path(rarity), "w", encoding="utf-8") as file:
        json.dump(
            [
                {"cardid": str(card.id), "season": season, "name": card.name}
                for card, season in cards
            ],
            file,
        )


def main() -> None:
    """Main method for standalone"""

    requester = nsapi.NSRequester(config.userAgent)

    rarity = input("Rarity to search for: ")

    find_rarities(requester, rarity)

    print(f"Saved results to `{rarity}Cards.json`")


if __name__ == "__main__":
    main()
