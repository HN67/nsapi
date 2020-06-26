"""Parses the trading card decks of nations"""

# Import types
from typing import Iterable, Mapping, MutableMapping, MutableSequence

# Import core modules
import logging

# Core library
import nsapi

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)


def sorted_cards(
    requester: nsapi.NSRequester, nations: Iterable[str]
) -> Mapping[str, Mapping[str, Iterable[nsapi.Card]]]:
    """Searchs the trading card decks of the given nations (by name), and sorts by rarity
    Returns a mapping with {rarity: {nation: [cards...]}} structure.
    Always includes exactly `common`, `uncommon`, `rare`, `ultra-rare`, `epic`, and `legendary`
    """
    # Prepare output structure with rarities
    # empty string key should catch any Card objects that dont have a category for some reason
    out: MutableMapping[str, MutableMapping[str, MutableSequence[nsapi.Card]]] = {
        "common": {},
        "uncommon": {},
        "rare": {},
        "ultra-rare": {},
        "epic": {},
        "legendary": {},
        "": {},
    }
    # Sort the deck of each nation
    for nation in nations:
        # Retrieve the deck of the nation (1 request)
        deck = requester.nation(nation).deck()
        # Parse each card in the deck, sorting into appropriate rarity bin
        for card in deck:
            # We dont wrap the out[] indexing in a try, since there should never be a error:
            # if for some reason the card doesnt have a category, it should have "" and
            # get placed in that bin
            rarityDict = out[card.category]
            # creates the nation: list key-value pair if it doesnt exist, otherwise
            # appends this card id
            try:
                rarityDict[nation].append(card)
            except KeyError:
                rarityDict[nation] = [card]

    return out


def main() -> None:
    """Main function"""

    # Provide proper user agent to api requester
    requester = nsapi.NSRequester("HN67 API Reader")

    # Function arguments, could be connected to command line, etc

    # Actually run the bulk logic
    data = sorted_cards(requester, ["hn67", "agilhn"])
    print("Ultra-Rare:")
    for nation in data["ultra-rare"]:
        print(f"{nation}:")
        for card in data["ultra-rare"][nation]:
            print(
                f"https://www.nationstates.net/page=deck/card={card.id}/season={card.season}"
            )


# Main function convention
if __name__ == "__main__":
    main()
