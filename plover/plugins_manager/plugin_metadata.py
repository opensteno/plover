from collections import namedtuple
from functools import total_ordering

from packaging.version import parse


@total_ordering
class PluginMetadata(
    namedtuple(
        "PluginMetadata",
        """
                                author
                                author_email
                                description
                                description_content_type
                                home_page
                                keywords
                                license
                                name
                                summary
                                version
                                """,
    )
):
    @property
    def requirement(self):
        return f"{self.name}=={self.version}"

    @property
    def parsed_version(self):
        return parse(self.version)

    @classmethod
    def from_dict(cls, d):
        return cls(*(d.get(k, "") for k in cls._fields))

    @classmethod
    def from_kwargs(cls, **kwargs):
        return cls.from_dict(kwargs)

    def to_dict(self):
        return dict(zip(self._fields, self))

    def __eq__(self, other):
        return (self.name.lower(), self.parsed_version) == (
            other.name.lower(),
            other.parsed_version,
        )

    def __lt__(self, other):
        return (self.name.lower(), self.parsed_version) < (
            other.name.lower(),
            other.parsed_version,
        )
