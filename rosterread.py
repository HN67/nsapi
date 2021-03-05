"""Reads plaintext of the roster and converts to JSON"""

import nsapi

import json
import re
import typing as t


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

    inputPath = input("Input file: ")
    outputPath = input("Output file: ")

    # Read input
    with open(inputPath, "r") as file:
        data = read_plain(file.readlines())

    # Write output
    with open(outputPath, "w") as file:
        json.dump(data, file)


if __name__ == "__main__":
    main()
