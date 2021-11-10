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
    # FORMAT_STRING = "%(levelname)s - %(name)s - %(message)s"
    FORMAT_STRING = "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s"
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


def same_nation(first: str, second: str) -> bool:
    """Determine if two strings reference the same nation.

    Performs a case insensitive comparison,
    and considers space (' ') and underscore ('_') the same.

    Implemented by comparing clean_format of both.
    """
    return clean_format(first) == clean_format(second)


class Name(str):
    """A name, insensitive in string equality after normalization."""

    @staticmethod
    def normal(string: str) -> str:
        """Normalize the given string."""
        # str is not neccesary for clean_format
        # (since .lower(), etc return str)
        # but we must ensure that normal returns str
        # not Name, to avoid recursion loops
        return str(clean_format(string))

    def __eq__(self, other: object) -> bool:
        """Acts as normalized form for equality checks."""
        # If the other object is a string we can normalize it
        if isinstance(other, str):
            return self.normal(self) == self.normal(other)
        # Otherwise default to normal string comparison
        # This looks a bit weird, but super()
        # creates a proxy object that redirects
        # the .eq call in the correct MRO spot
        return super() == other

    def __hash__(self) -> int:
        """Hash the normalized form."""
        return hash(self.normal(self))
