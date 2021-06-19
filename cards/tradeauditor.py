"""Reports any legendary card trades involving Card Coop Members"""

import datetime
import logging

import requests

import config
import nsapi
from cards import rarityfinder

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)

requester = nsapi.NSRequester(config.userAgent)

# load legendary cards
rarityfinder.verify_rarity_data(requester, "legendary")
cards = rarityfinder.load_rarity_data("legendary")

# load member nations
response = requests.get(
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vSem15AVLXgdjxWBZOnWRFnF6NwkY0gVKPYI8"
    "aWuHJzlbyILBL3o1F5GK1hSK3iiBlXLIZBI5jdpkVr/pub?gid=1588413756&single=true&output=tsv"
)
members = {
    nsapi.clean_format(line.split("\t")[0]) for line in response.text.split("\r\n")
}

print("Enter the timestamp to check trading since,")
print("or press enter to default to the first day of the previous month.")
boundInput = input("Timestamp: ")

if boundInput:
    bound = int(boundInput)
else:
    # first day, first second (12:00 AM) (UTC) of last month
    lastMonth: int = int(
        (
            # Gets a datetime in the previous month
            # by subtracting 1 day from the first day of this month
            datetime.datetime.now(datetime.timezone.utc).replace(day=1)
            - datetime.timedelta(days=1)
        )
        # Replace the day with first day, and time with 0
        .replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
    )

    bound = lastMonth

output = input("Enter the file name to generate output in (will override existing): ")

# check trades of each card
trades = []
for card in cards:
    for trade in requester.card(
        cardid=int(card["cardid"]), season=card["season"]
    ).trades(safe=False, sincetime=str(bound)):
        if (
            nsapi.clean_format(trade.buyer) in members
            or nsapi.clean_format(trade.seller) in members
        ):
            trades.append((card, trade))

# display filtered trades
with open(nsapi.absolute_path(output), "w") as file:
    for card, trade in trades:
        print(
            f"{card['name']} "
            "(https://www.nationstates.net/page=deck/card=926511/season=1/trades_history=1): "
            f"Sold from {trade.seller} to {trade.buyer}.",
            file=file,
        )
