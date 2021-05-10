"""Parses a report"""

import dataclasses
import logging
import typing as t

import nsapi

# Setup logger
_level = logging.INFO
logger = logging.getLogger(__name__)
logger.setLevel(level=_level)
logger.addHandler(logging.StreamHandler())
# Change nsapi logging level
nsapi.logger.setLevel(level=_level)


@dataclasses.dataclass
class Report:
    """Dataclass containing report data"""

    members: t.Iterable[str]
    cwe: str
    name: str
    tag: str


def parse_report(raw: str) -> Report:
    """Parses a plaintext report into an object"""


def convert_name(common: str) -> str:
    """Converts a informal name to an official one,
    prompting if the informal is unknown.
    """


def main() -> None:
    """Main function"""

    # requester = nsapi.NSRequester(config.userAgent)


# entry point
if __name__ == "__main__":
    main()
