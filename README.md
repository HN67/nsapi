# NSAPI

Hobby project to develop and utilize a Python API wrapper for the [NationStates API](https://www.nationstates.net/pages/api.html).

The heart of this project is `nsapi.py`, which provides the NSRequester class for making API requests, and several other API objects for retrieving more sophisticated data.

In order to use any of the scripts, both `nsapi.py` and `config.py` must be included in the same directory, and `config.py` must specify a *descriptive* User Agent, such as your nation name.

Some scripts interact with NationStates data dumps, which may involve downloading files up to 40MB in size. When using any card related scripts, it is recommended to also include the `cardlist` gz files from this repo to ensure that the scripts can access non-corrupted data.

## Requirements

- Python 3.6+
- requests

## Utilities
The following list is incomplete. Information on scripts can also be found in the docstring (first line) of the file.

`endorsements.py` checks the nation chosen by the `endorser` variable and sees which WA members of their region they have not endorsed.

`endorsed.py` checks the nation chosen by the `target` variable to see which WA members of their region have not endorsed them.

`cardsort.py` is a relatively finished script, which will prompt for nations and card rarity, and then parse the decks of the specificed nations, producing a csv file. Designed to be run from command line.
