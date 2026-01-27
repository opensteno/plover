# Environment setup

You need Python installed.
It is recommended to install the same Python version that is packaged in the official installer files.
You can look up this version in the file `.github/workflows/ci/workflow_context.yml` in the vars section (`default_python`).

Tox simplifies the process of creating and managing isolated virtual environments,
handling dependency installation, and running the test suite in isolation. This
ensures a clean and consistent testing environment.

However, it is still recommended to install and run tox within a Python virtual
environment created using tools like [venv](https://docs.python.org/3/library/venv.html).
This helps keep your global Python environment clean, avoids project conflicts, and
isolates tox and its dependencies.

You also need [CMake](https://cmake.org) to build [hidapi](https://github.com/libusb/hidapi) from source which is required for Plover HID support.

A typical development setup looks like this, assuming that `python` has the correct version:

## Linux/macOS (Bash):

```bash
cd path/to/plover
python -m venv .venv
source .venv/bin/activate 
pip install -c reqs/constraints.txt -r reqs/dev.txt
pre-commit install
pre-commit run --all-files
tox
tox -e launch -- -l debug
```

## Windows (PowerShell):

This assumes that you installed a Git version that includes Git Bash.

```powershell
cd path\to\plover
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -c reqs\constraints.txt -r reqs\dev.txt
pre-commit install
pre-commit run --all-files
& "C:\Program Files\Git\bin\bash.exe" -lc "tox"
& "C:\Program Files\Git\bin\bash.exe" -lc "tox -e launch -- -l debug"
```

Some features require a Bash shell, which is why on Windows you need to run commands through Git Bash or similar.

## Read the Docs build (Docker)

To reproduce the Read the Docs build locally, use the official RTD build image.
The image defaults to a non-root user, so run as root to install packages.

```bash
docker run --rm -it --platform=linux/amd64 -u root -v "$PWD":/work -w /work readthedocs/build:ubuntu-24.04-2024.06.17 bash

apt-get update
apt-get install -y python3 python3-venv python3-dev build-essential
python3 -m venv .venv-rtd
. .venv-rtd/bin/activate
python -m pip install --upgrade pip setuptools
python -m pip install -c reqs/constraints.txt -r reqs/dist.txt
python -m pip install -r doc/requirements.txt
python -m sphinx -b html -W doc doc/_build/html
```

The HTML output is in `doc/_build/html/index.html`.

## Tox

The command for using tox is: `tox {-e envlist} {-- arguments}`. Use `tox -a
-v` to get a list of available environments.

The same virtual environment is reused by the following tox environments:

- `tox -e test -- ARGS`: run the testsuite. This is the default environment
  when not provided.
  
  Example: `tox -e test -- test/gui_qt`
- `tox -e launch -- ARGS`: run Plover from source.

  Example: `tox -e launch -- -l debug`
- `tox -e setup -- COMMAND`: run `./setup.py COMMAND` to create a binary 
  distribution. See also section below.

  Example: `tox -e setup -- bdist_appimage`
- `tox -e packaging_checks`: run the same packaging checks as the CI (add `--
-n` to see a dry-run of the exact checks).
- `tox -e plugins_install -- ARGS`: install the plugins specified in `ARGS`, where
  plugins are separated by space. You can also specify plugin versions. Note that
  this process uses pip directly for installation, not the plugins manager.

  Example: `tox -e plugins_install -- some_plugin==1.0.0 another_plugin`
- `tox -e release_prepare -- NEW_VERSION`: execute all the steps necessary for
  preparing a new release: patch the version to `NEW_VERSION` and update
  `NEWS.md`, staging all the changes for review.
- `tox -e release_finalize`: finalize the release: commit the staged changes,
  create an annotated tag, and print the git command necessary for pushing the
  release to GitHub.

The virtual environment created by tox lives in `.tox/dev`, and can be [activated like
any other virtual environment](https://virtualenv.pypa.io/en/latest/user_guide.html#activators).

The configuration also provides support for lightweight tests only environment:
`pyX`, where `X` is the version of the Python interpreter to use. E.g. running
`tox -e 'py3,py310,py311,py312` will execute the testsuite for each version
of Python we support.

# Creating a binary distribution

A number of commands are provided by `setup.py` for creating binary
distributions (which include all the necessary dependencies):

- `bdist_appimage`: Linux only, create an [AppImage](https://appimage.org/).
- `bdist_app`: macOS only, build an **application bundle**.
- `bdist_dmg`: macOS only, create a **disk image**.
- `bdist_win`: Windows only, create a portable version.

Use `bdist_xxx --help` to get more information on each command supported options.

# Making a pull request

When making a pull request, please include a short summary of the changes
and a reference to any issue tickets that the PR is intended to solve.
All PRs with code changes should include tests. All changes should include a
changelog entry.

Plover uses [towncrier](https://pypi.org/project/towncrier) for changelog
management, so when making a PR, please add a news fragment in the `news.d/`
folder. Changelog files are written in Markdown and should be a 1 or 2 sentence
description of the substantive changes in the PR.

They should be named `<section>/<pr_number>.<category>.md`, where the sections
/ categories are:

- `feature`: New features:

  - `core`: Core changes.
  - `dict`: Updates to the default dictionaries.
  - `ui`: Changes to the user interface.
  - `linux`: Linux specific changes.
  - `osx`: macOS specific changes.
  - `windows`: Windows specific changes.

- `bugfix`: For bugfixes, support the same categories as for `feature`.

- `api`: For documenting changes to the public/plugins API:

  - `break`: For breaking (backward incompatible) changes.
  - `dnr`: For deprecations of an existing feature or behavior.
  - `new`: For other (backward compatible) changes, like new APIs.

A pull request may have more than one of these components, for example a code
change may introduce a new feature that deprecates an old feature, in which
case two fragments should be added. It is not necessary to make a separate
documentation fragment for documentation changes accompanying the relevant
code changes. See the following for an example news fragment:

```bash
$ cat news.d/bugfix/1041.ui.md
Fix possible crash when changing machine parameters in the configuration dialog.
```
