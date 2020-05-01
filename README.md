# NSAPI

Hobby project to develop and utilize a Python API wrapper for the [NationStates API](https://www.nationstates.net/pages/api.html).

Primarily for personal use.

The two files `endorsements.py` and `endorsed.py` check endorsement status among regional members. `endorsements.py` checks the nation chosen by the `endorser` variable and sees which WA members of their region they have not endorsed, and `endorsed.py` checks the nation chosen by the `target` variable to see which WA members of their region have not endorsed them.

Both scripts interact with the daily nation data dump, which involves downloading a ~40 MB file, updated daily.
