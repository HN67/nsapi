"""Reads plaintext of the roster and converts to JSON"""

import json
import re
import sys
import typing as t

import nsapi


def read_plain(lines: t.Iterable[str]) -> t.Mapping[str, str]:
    """Converts each line into a nation: wa pair"""
    output = {}
    for line in lines:
        # Try to find the two matches
        waMatch = re.search(
            r'\[a href="https://www.nationstates.net/nation=(.*?)"\]', line
        )
        nationMatch = re.search(r"\](.*?)\[", line)
        # If both succeed add the pair
        if waMatch and nationMatch:
            output[nsapi.clean_format(nationMatch[1])] = nsapi.clean_format(waMatch[1])
    return output


def main() -> None:
    """Main function"""

    # Read input
    data = read_plain(sys.stdin.readlines())

    # Write output
    json.dump(data, sys.stdout)


if __name__ == "__main__":
    main()
