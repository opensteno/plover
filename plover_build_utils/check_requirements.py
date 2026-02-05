#!/usr/bin/env python3

from importlib.metadata import distributions, requires, PackageNotFoundError
from packaging.requirements import Requirement


def sorted_requirements(requirements):
    return sorted(requirements, key=lambda r: str(r).lower())


# Find all available distributions.
all_requirements = [
    Requirement(f"{dist.metadata['Name']}=={dist.version}") for dist in distributions()
]

# Find Plover requirements.
plover_deps = set()
try:
    plover_requires = requires("plover") or []
    for req in plover_requires:
        plover_deps.add(Requirement(req))
except PackageNotFoundError:
    print("Plover is not installed.")
    plover_requires = []

# List requirements.
print("# plover")
for requirement in sorted_requirements(plover_deps):
    print(requirement)
print("# other")
for requirement in sorted_requirements(all_requirements):
    if requirement not in plover_deps:
        print(requirement)
print("# vim: ft=cfg commentstring=#\\ %s list")
