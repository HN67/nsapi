"""Automatically answers all issues on a nation, either randomly, by a pattern, or manually"""

import logging
import random
from typing import Iterable, List, Optional, Tuple

import config
import nsapi

# Set logging level
level = logging.INFO
logging.basicConfig(level=level)
# Name logger
logger = logging.getLogger()
# Change nsapi logging level
nsapi.logger.setLevel(level=level)


def answer_all(
    requester: nsapi.NSRequester,
    name: str,
    autologin: str,
    optionNum: Optional[int] = None,
) -> Iterable[Tuple[int, int, str]]:
    """Answers all available issues on the nation.
    If optionNum is provided, attempts to answer all issues with that option
    (starting at 0, so 0 is the first option).
    If an issue does not have that many options, answers with the last.
    Counts by available options, not all options.
    Returns tuples encoding (id, option, description).
    """
    # Create and add authentication to the nation API object
    nation = requester.nation(name)
    nation.login(autologin)
    # Prepare output list
    output: List[Tuple[int, int, str]] = []
    # Iterate through all available issues
    for issue in nation.issues():
        # Use the option requested
        if optionNum:
            option = list(issue.options.keys())[optionNum]
        # If none, answer randomly
        else:
            option = random.choice(list(issue.options.keys()))
        info = nation.answer_issue(issue=issue.id, option=option)
        # info[1] should be the DESC node
        output.append((issue.id, option, info[1].text if info[1].text else ""))
    return output


def main() -> None:
    """Main function"""

    requester = nsapi.NSRequester(config.userAgent)

    for output in answer_all(requester, "nation", "autologin"):
        print(output)


if __name__ == "__main__":
    main()
