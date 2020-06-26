# NSAPI

Hobby project to develop and utilize a Python API wrapper for the [NationStates API](https://www.nationstates.net/pages/api.html).

The heart of this project is `nsapi.py`, which provides the NSRequester class for making API requests, and several other API objects for retrieving more sophisticated data.

`endorsements.py` checks the nation chosen by the `endorser` variable and sees which WA members of their region they have not endorsed.

`endorsed.py` checks the nation chosen by the `target` variable to see which WA members of their region have not endorsed them.

Both scripts interact with the daily nation data dump, which involves downloading a ~40 MB file, updated daily.

`cardsort.py` is a relatively finished script, which will prompt for nations and card rarity, and then parse the decks of the specificed nations, producing a csv file. Designed to be run from command line.

`cardsort.py` relies on `config.py` to specify a *UserAgent*, which should at least identify you to NationStates, and ideally reference `HN67` as well.

## Requirements

- Python 3.6+
- requests
