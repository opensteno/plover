#!/usr/bin/env python3
"""Query PyPI to find packages that have macOS-specific binary wheels but lack
a universal2 variant for the given Python version.

Outputs a comma-separated list suitable for pip's ``--no-binary`` flag.
Diagnostic details are printed to stderr.

Usage: find_non_universal_wheels.py <python_base_version> <constraints_file>
Example: find_non_universal_wheels.py 3.13 reqs/constraints.txt
"""

import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def parse_constraints(path):
    """Return {normalized_name: version} from a pip constraints file."""
    result = {}
    for line in Path(path).read_text().splitlines():
        line = line.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            result[name.strip().lower()] = version.strip()
    return result


def check_package(name, version, py_version):
    """Return the package name if it needs ``--no-binary``, else ``None``.

    A package needs ``--no-binary`` when PyPI hosts macOS wheels for our
    CPython version (or stable ABI) but none of them are universal2.
    Packages with *no* macOS wheels at all are fine — they are either pure
    Python or will be built from source automatically.
    """
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None  # Network error — assume OK; check_universal.sh is the safety net.

    cp_tag = f"cp{py_version.replace('.', '')}"
    has_macos_wheel = False
    has_universal2 = False

    for file_info in data.get("urls", []):
        fn = file_info.get("filename", "")
        if "macosx" not in fn:
            continue
        # Must be compatible with our Python version (exact cpXY or stable ABI).
        if cp_tag not in fn and "abi3" not in fn:
            continue
        has_macos_wheel = True
        if "universal2" in fn:
            has_universal2 = True
            break

    if has_macos_wheel and not has_universal2:
        return name
    return None


def main():
    if len(sys.argv) != 3:
        print(
            f"Usage: {sys.argv[0]} <python_base_version> <constraints_file>",
            file=sys.stderr,
        )
        sys.exit(1)

    py_version = sys.argv[1]  # e.g. "3.13"
    constraints = parse_constraints(sys.argv[2])

    no_binary = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(check_package, name, version, py_version): name
            for name, version in constraints.items()
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                no_binary.append(result)

    no_binary.sort()
    for pkg in no_binary:
        version = constraints.get(pkg, "?")
        print(
            f"  {pkg}=={version}: no universal2 wheel on PyPI, will build from source",
            file=sys.stderr,
        )

    # stdout: comma-separated list consumed by make_app.sh
    if no_binary:
        print(",".join(no_binary))


if __name__ == "__main__":
    main()
