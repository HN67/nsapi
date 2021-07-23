"""Core mechanisms and wrappers for interacting with the NS API
See https://www.nationstates.net/pages/api.html for NS API details
"""

# Reconsider absolute_path:
# Linking everything to a __file__ based path has several problems,
# in that it works well when nsapi.py is a script, but gives the user less control than cwd
# essentially trades control for convience (not all users may understand cwd)
# Users not understanding cwd is unlikely to be a problem; e.g. running a script
# on windows by double clicking it typically makes the cwd the location of the script
# If a user ends up using cmd, cwd will still be somewhere sane (user root?) unless in administrator
# output files should probably be largely put into cwd, but perhaps __file__ is better
# for data files that the end user doesnt need to see.
# However, it can break completely when doing things such as compiling with pyinstaller,
# and probably wont work if trying to make a package.
# The probably conclusion is that abs_path is useful for scripts, but not the kind
# of package/library nsapi is becoming.
# A related concept is the data dumps, since they produce the most files (at decently large ones).
# Ideally, there should be an easy way to remove a dump, maybe automatically?
# Not sure how that would look, maybe once its done iterating it removes it.


# Standard library modules
# Code quality
import logging
import typing as t

from nsapi.api import NSRequester

# Setup logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def configure_logger(
    loggerObject: logging.Logger,
    *,
    level: t.Union[int, str] = logging.WARNING,
    force: bool = True,
) -> logging.Logger:
    """Performs standard configuration on the provided logger.

    Can be used to configure this modules logger or any user modules logger.

    Adds a default stream handler with a format string containing level, name, and message.

    Returns the logger passed.
    """
    # Add formatted handler
    FORMAT_STRING = "%(levelname)s - %(name)s - %(message)s"
    # Only add the handler if forced or none exist
    if force or len(loggerObject.handlers) == 0:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(FORMAT_STRING))
        loggerObject.addHandler(handler)
    # Set logging level
    loggerObject.setLevel(level)
    # Chain object
    return loggerObject


def enable_logging(level: t.Union[int, str] = logging.INFO) -> logging.Logger:
    """Configure root logger using `configure_logger`.
    
    Returns the root logger.
    """
    return configure_logger(logging.getLogger(), level=level)


def clean_format(string: str) -> str:
    """Casts the string to lowercase and replaces spaces with underscores"""
    return string.lower().replace(" ", "_")


def main() -> None:
    """Main function; only for testing"""

    requester: NSRequester = NSRequester("HN67 API Reader")
    print(requester.request("?a=useragent").text)


# script-only __main__ paradigm, for testing
if __name__ == "__main__":
    main()
