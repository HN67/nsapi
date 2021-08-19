# NSAPI

Hobby project to develop and utilize a Python API wrapper for the [NationStates API](https://www.nationstates.net/pages/api.html).

The heart of this project is the `nsapi` package, which provides the `NSRequester` class for making API requests, and several other API objects for retrieving more sophisticated data.

In order to use any of the scripts, both `config.py` and the `nsapi` folder must be included in the same directory, and `config.py` must specify a *descriptive* User Agent, such as your nation name.

Example:

```python
"""Must provide an identifying user agent"""

userAgent = "HN67"
```

Some scripts interact with NationStates data dumps, which may involve downloading files up to 50MB in size.

## Dependencies

- [Python 3.6+](https://www.python.org/downloads/)
- `requests`

The recommended method to gather dependencies other than Python is to use [poetry](https://python-poetry.org/)
with the included `pyproject.toml` file (typically by running `poetry install` in the project directory).

When installing Python, make sure to install pip as well, and to add Python to PATH/Environment Variables.

## Utilities

The following list is incomplete. Information on scripts can also be found in the docstring (first line) of the file.

Running most of these scripts should be possible with `python -m <script_name>`, but some also support a command line interface.

If `poetry` was used to install dependencies, use `poetry run python -m <script_name>` instead.

`autologin` takes a list of nations from a text file and uses the API to register a login, preventing ceasing to exist from inactivity. The file most pair each nation with a password, or autologin keys. The script will optionally output a file with autologin keys after running, which can then be used instead of the original file, allowing you to avoid storing passwords in plaintext long-term. Nation names may contain any character other than a comma (which NationStates disallows regardless), and passwords and keys can contain any character. The file should have one nation, password pair per line, and may have optional blank lines for readability. All nations in the file must have either passwords or autologin keys, not a mixture.

Example: `passwords.txt`

```text
Testlandia,myPassword123
TestlandiaPuppet,myOtherPassword456
```

`wa.endorsements` checks the nation chosen by the `endorser` variable and sees which WA members of their region they have not endorsed.

`wa.endorsed` checks the nation chosen by the `target` variable to see which WA members of their region have not endorsed them.

`cards.cardsort` is a relatively finished script, which will prompt for nations and card rarity, and then parse the decks of the specificed nations, producing a csv file. Designed to be run from command line.
