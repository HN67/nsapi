"""Testing utilities."""

import logging

from nsapi import api
from nsapi import core


core.configure_logger(logging.getLogger(), level=logging.INFO)


def main() -> None:
    """Main function; only for testing"""

    requester: api.NSRequester = api.NSRequester("HN67 API Reader")
    print(requester.request("?a=useragent").text)


# script-only __main__ paradigm, for testing
if __name__ == "__main__":
    main()
