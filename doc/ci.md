# Continuous Integration


The project uses Github Actions (GA), the workflow configuration lives in
`.github/workflows/ci.yml`. Because of the limitation of GA (no YAML
anchors/aliases support, no possibility to re-use actions in composite
actions), in order to reduce duplications, that file is currently generated:

- `.github/workflows/ci/workflow_template.yml` is the
  [Jinja](https://palletsprojects.com/p/jinja/) template.

- `.github/workflows/ci/workflow_context.yml` contains the tests/build jobs
  definitions.

- `.github/workflows/ci/workflow_generate.py` is used to generate the workflow
  configuration: just execute `./.github/workflows/ci/workflow_generate.py` to
  update the workflow configuration after updating one of the files above (the
  script will check whether the output is valid YAML, and that anchors/aliases
  are not used).

- `.github/workflows/ci/helpers.sh` contains the bash functions used by some
  of the steps (e.g. setting up the Python environment, running the tests,
  etc...). Note: this file reuse some of the helpers provided by
  `plover_build_utils/functions.sh`.

The current workflow consists of:

- **Analyze**: a pre-processing job, all other jobs depend on it.
- **Platform tests**: jobs for Linux, macOS, and Windows.
- **Qt GUI test**: specifically for testing the Qt interface.
- **Python tests**: for checking compatibility across all supported versions of Python.
- **Code quality**: runs linting and formatting checks.
- **Packaging**: runs a number of packaging related checks.
- **Platform build**: jobs for Linux, macOS and Windows, dependent on their
    respective platform tests job (so if the `Test (macOS)` job fails, the
    `Build (macOS)` job is skipped).
- **macOS notarization**: handles code signing and Apple notarization for
    the macOS application and disk image.
- **Release**: a final, optional job.


## Analyze job

This job has 2 roles:
- determine if a release will be made (will the final "Release" job be skipped?)
- analyze the source tree to determine if some of the jobs can be skipped

## Release conditions

A release is triggered if the `GITHUB_REF` environment variable starts with
`refs/tags/`, which indicates that the workflow is triggered by a Git tag.


## Skipping Test/Build jobs

First, jobs are never skipped when a release is done.

Otherwise, a special job specific cache is used to determine if a job can be
skipped.

Each job will update that cache as part of their run.

The cache is keyed with:
- the `epoch` defined in `workflow_context`
- the name of the job
- a hash of the relevant part of the source tree

On cache hit, the job is skipped.

### Creating the tree hash

Let's take the example of the "Linux Build" job, the steps used for creating
the skip cache key are:
- a list of exclusion patterns is built, in this case from `skiplist_default.txt`,
  `skiplist_job_build.txt`, and `skiplist_os_linux.txt`
- that list of exclusion patterns is used to create the list of files
   used by the job: `git ls-files [...] ':!:doc/*' [...] ':!:reqs/test.txt' [...]`
- part of the `HEAD` tree object listing is hashed:
  `git ls-tree @ [...] linux/appimage/deps.sh [...] | sha1sum`

Note: the extra `git ls-files` step is needed because exclusion patterns are
not supported by `git ls-tree`.


## Tests / Build jobs

On Linux / Windows, the standard GA action `actions/setup-python` is used
to setup Python: so, for example, configuring a job to use 3.7 will
automatically setup up the most recent 3.7.x version available on the
runner.

On macOS, to support older releases, Python will be setup from an official
installer (see `osx/deps.sh` for the exact version being used). The version
declared in `workflow_context.yml` must match, or an error will be raised
during the job execution (if for example the job is declared to use `3.7`,
but the dependency in `osx/deps.sh` uses `3.6.8`).

Caching is used to speed up the jobs. The cache is keyed with:
- the `epoch` defined `workflow_context`: increasing it can be used to
  force clear all the caches for all the jobs
- the name of the job
- the full Python version setup for the job (so including the patch number)
- a hash of part of the requirements (`reqs/constraints.txt` + the relevant
  `reqs` files for the job in question), and additional files declaring
  extra dependencies for some jobs (e.g. `osx/deps.sh` on macOS)

If the key changes, the cache is cleared/reset, and the Python environment
will be recreated, wheel and extra dependencies re-downloaded, etc...


## macOS Notarization

To ensure that Plover can be run on modern macOS versions without being blocked
by Gatekeeper, the macOS app and DMG are code-signed and notarized by Apple.

This process involves:
- Importing a Developer ID certificate into a temporary keychain.
- Signing the application bundle and the disk image.
- Submitting the artifacts to Apple's notarization service.
- Stapling the notarization ticket to the artifacts.

Because this requires access to sensitive credentials, notarization is only
performed for commits on the `main` branch and `maintenance/*` branches. These
jobs are automatically skipped for all other branches and pull requests from forks.


## Packaging job

This job will run a number of packaging-related checks. See
`packaging_checks` in `functions.sh` for the details.

The resulting source distribution and wheel will also be added
to the artifacts when a release is being created.


## Release job

The final job, only run on a tagged release, and if all the other
jobs completed successfully.


### PyPI release

On *tagged* release, the source distribution and wheel are published
to PyPI via [Trusted Publishing](https://docs.pypi.org/trusted-publishers/).


### GitHub release

On *tagged* release, a new release draft is created on GitHub.

All the artifacts will be included as assets.

The release notes are automatically generated from the last release section in
`NEWS.md` (*tagged* release) and the template in `.github/RELEASE_DRAFT_TEMPLATE.md`.


## Limitations

- Artifacts can only be downloaded when logged-in.
