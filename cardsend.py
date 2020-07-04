"""Reads a specifically-formatted file and sends multiple cards"""

import csv
import logging
from typing import MutableMapping

import config
import nsapi


# Set logging level
level = logging.WARNING
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)


def send_card(link: str, sender: nsapi.Nation, receiver: str) -> None:
    """Sends a trading card on NationStates.
    link: a link to the page of a trading card,
    eg https://www.nationstates.net/page=deck/card=926511/season=1
    sender: a Nation, neccesary to allow repetitive calling of this method for the same nation
    receiver: the receiving nation, as a string
    """
    # Parse link into cardid and season
    # this may or may not be the best way to do this
    # alternatives considered:
    # regex: seems overly complex
    # urlparsing (urllib?): not actually neccesarily useful, since the data
    # isnt actually params, its part of the path so a url lib might not do much.
    # We split on / to grab the path pieces, and then keep anything with `=` in it
    # because those are what contains the data.
    # then we simply split on = into key-value
    data: MutableMapping[str, str] = {}
    for piece in link.split("/"):
        if "=" in piece:
            # Only 1 to easily turn into key-value.
            # there should only be 1 anyways
            key, value = piece.split("=", maxsplit=1)
            data[key] = value
    # Now we can grab cardid and season
    # Send the card. Technically we are inefficiently casting to int here
    # and then str in the function, but I dont really care. that is not the bottleneck.
    sender.gift_card(cardid=int(data["card"]), season=int(data["season"]), to=receiver)


def main() -> None:
    """Main function"""

    # Create requester
    requester = nsapi.NSRequester(config.userAgent)

    print("Provide a data file to work through.")
    print(
        "Ideally, the file should be a csv-type text format, with each row in this format:"
    )
    print("<card_link>,<sender>,<receiver>,<sender_password>")
    print(
        "e.g.: 'https://www.nationstates.net/page=deck/card=926511/season=1,hn67,hn67_ii,aPassword"
    )
    print("Technically, only the 'card=num/season=num' part of the link is required.")
    print("Also, the password is only required for the first occurence of a nation.")
    print(
        "If your password contains a comma (','), it should be enclosed with double quotes (\")."
    )
    print(
        "The path to the file is relative to this script. If the file is in the same directory,"
    )
    print("just enter the name (e.g. 'gifts.csv')")
    dataPath = input("Data file: ")

    print(
        "\nInstead of saving your password in the file,"
        " you can alternatively provide an API autologin,"
    )
    print("which is a encrypted by NationStates version.")
    print(
        "Enter 'yes'/'y' to interpret the passwords as autologins,"
        " or 'no' (or anything else) to not."
    )
    autologinInput = input("Interpret password fields as autologin? ").lower()
    if autologinInput in ("yes", "y"):
        autologin = True
        print("Interpreting password field as autologins.")
    else:
        autologin = False

    # We save Nation objects so that they can all use the same Auth, i.e. pin
    nations: MutableMapping[str, nsapi.Nation] = {}

    with open(nsapi.absolute_path(dataPath), "r", newline="") as file:
        csvReader = csv.reader(file)
        for row in csvReader:
            try:
                # We need to prepare or find the nation object first (of the sender)
                nation = nsapi.clean_format(row[1])
                if nation not in nations:
                    nations[nation] = requester.nation(nation)
                # Update the nation auth using given password (or autologin)
                # the password is the 4 column, but is not neccesary
                # remember, 4th column == 3rd index
                if len(row) >= 4:
                    # Autologin is True if the passwords are actually autologins
                    if autologin:
                        nations[nation].login(row[3])
                    else:
                        nations[nation].auth = nsapi.Auth(password=row[3])
                # Now we can delegate to the function
                send_card(link=row[0], sender=nations[nation], receiver=row[2])
                print(f"Sent {row[0]} from {nation} to {row[2]}")
            # Broad error cause we want to catch anything, so the whole
            # program doesnt crash. logs the message
            except Exception as exception:  # pylint: disable=broad-except
                print("Failed to send a card. Error:", exception)


if __name__ == "__main__":
    main()
