# NSAPI
Hobby project to develop a Python API wrapper for NationStates
https://www.nationstates.net/pages/api.html

Primarily for personal use.

The two files `endorsements.py` and `endorsed.py` check endorsement status among XKI WA members. `endorsements.py` checks the nation chosen by the `endorser` variable and sees which WA members of XKI they have not endorsed, and `endorsed.py` checks the nation chosen by the `target` variable to see which WA members of XKI have not endorsed them.

NOTE: Due to the two above mentioned files loading the entire NS API nations data dump into memory at once, it uses up to 4GB of memory during calculations. I am working on fixing this, but for now the only patch is that the XML tree is deleted as soon as possible so that the results can be viewed without the script using the memory.
