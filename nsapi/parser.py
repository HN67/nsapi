"""Tools for parsing XML data into Python models."""

import typing as t

import xml.etree.ElementTree as etree

T = t.TypeVar("T")


# # XMLTransformer/Parser logic
# """Tools for describing the transformation from XML to Python"""
class NodeParse:
    """Class to ease the transformation from XML data to a Python object."""

    def __init__(self, node: etree.Element) -> None:
        """Wraps a root node"""
        self.node = node

        child_tags: t.MutableMapping[str, t.MutableSequence[etree.Element]] = {}
        for child in node:
            if child.tag in child_tags:
                child_tags[child.tag].append(child)
            else:
                child_tags[child.tag] = [child]

        # 'Freeze' the child tags attribute so that it appears immutable
        self.child_tags: t.Mapping[str, t.Sequence[etree.Element]] = child_tags

    def has_name(self, name: str) -> bool:
        """Checks whether the given name is a tag of one of the child nodes."""
        return name in self.child_tags

    def from_name(self, name: str) -> t.Sequence[etree.Element]:
        """Returns a sequence of all nodes that have
        the given parameter as a tag.
        Runs in O(1) time since a map is pre-created.
        Raises KeyError if the tag doesnt exist.
        """
        return self.child_tags[name]

    def first(self, name: str) -> etree.Element:
        """Returns the first node with the given tag.
        O(1) time complexity.
        """
        return self.from_name(name)[0]

    def simple(self, name: str) -> str:
        """Returns the text content of the first subnode with a matching tag"""
        return content(self.first(name))


def label_children(node: etree.Element) -> t.Mapping[str, etree.Element]:
    """Returns a mapping from node tag name to node
    for each child node of the parameter.
    Note that if there are multiple children with the same tag,
    the last one will overwrite previous ones in the returned map.
    """
    return {child.tag: child for child in node}


def content(node: etree.Element) -> str:
    """Function to parse simple tags that contain the data as text"""
    return node.text if node.text else ""


def sequence(node: etree.Element, key: t.Callable[[etree.Element], T]) -> t.Sequence[T]:
    """Traverses the subnodes of a given node,
    retrieving the result from the key function for each child.
    """
    return [key(sub) for sub in node]
