#!/usr/bin/env python3
# Copyright (c) 2010 Joshua Harlan Lifton.
# See LICENSE.txt for details.

import os
import re
import subprocess
import sys

from setuptools import setup
from packaging.version import Version

sys.path.insert(0, os.path.dirname(__file__))

__software_name__ = "plover"

# TODO: load metadata without exec (e.g., dedicated metadata module).
__version__ = ""
__description__ = ""
__url__ = ""
__download_url__ = ""
__license__ = ""

with open(os.path.join(__software_name__, "__init__.py")) as fp:
    exec(fp.read())

from plover_build_utils.setup import BuildPy, BuildUi, Command, Develop, babel_options


Develop.build_dependencies.append("build_py")
BuildPy.build_dependencies.append("build_ui")
cmdclass = {
    "build_py": BuildPy,
    "build_ui": BuildUi,
    "develop": Develop,
}
options = {}

PACKAGE = "%s-%s" % (
    __software_name__,
    __version__,
)

# Helpers. {{{


def get_version():
    if not os.path.exists(".git"):
        return None

    version = __version__

    # extend version with git revision if no tag is available - used for builds during development
    git_version = (
        subprocess.check_output("git describe --tags --match=v[0-9]*".split())
        .strip()
        .decode()
    )
    m = re.match(r"^v(\d[\d.]*(?:(?:\.dev|rc)\d+)?)(-\d+-g[a-f0-9]*)?$", git_version)
    assert m is not None, git_version
    if m.group(2) is not None:
        version += "+" + m.group(2)[1:].replace("-", ".")

    return version


# }}}

# `bdist_win` command. {{{


class BinaryDistWin(Command):
    description = "create distribution(s) for MS Windows"
    user_options = [
        ("trim", "t", "trim the resulting distribution to reduce size"),
        ("zipdir", "z", "create a zip of the resulting directory"),
        (
            "installer",
            "i",
            "create an executable installer for the resulting distribution",
        ),
        ("bash=", None, "bash executable to use for running the build script"),
    ]
    boolean_options = ["installer", "trim", "zipdir"]
    extra_args = []

    def initialize_options(self):
        self.bash = None
        self.installer = False
        self.trim = False
        self.zipdir = False

    def finalize_options(self):
        pass

    def run(self):
        cmd = [self.bash or "bash", "windows/dist_build.sh"]
        if self.installer:
            cmd.append("--installer")
        if self.trim:
            cmd.append("--trim")
        if self.zipdir:
            cmd.append("--zipdir")
        cmd.extend((__software_name__, __version__, self.bdist_wheel()))
        if self.verbose:
            print("running", " ".join(cmd))
        subprocess.check_call(cmd)


if sys.platform.startswith("win32"):
    cmdclass["bdist_win"] = BinaryDistWin

# }}}

# `launch` command. {{{


class Launch(Command):
    description = "run %s from source" % __software_name__.capitalize()
    command_consumes_arguments = True
    user_options = []

    def initialize_options(self):
        self.args = None

    def finalize_options(self):
        pass

    def run(self):
        with self.project_on_sys_path():
            python_path = os.environ.get("PYTHONPATH", "").split(os.pathsep)
            python_path.insert(0, sys.path[0])
            os.environ["PYTHONPATH"] = os.pathsep.join(python_path)
            cmd = [sys.executable, "-m", "plover.scripts.main"] + self.args
            if sys.platform.startswith("win32"):
                # Workaround https://bugs.python.org/issue19066
                subprocess.Popen(cmd, cwd=os.getcwd())
                sys.exit(0)
            os.execv(cmd[0], cmd)


cmdclass["launch"] = Launch

# }}}

# `patch_version` command. {{{


class PatchVersion(Command):
    description = "patch package version from VCS"
    command_consumes_arguments = True
    user_options = []

    def initialize_options(self):
        self.args = []

    def finalize_options(self):
        assert 0 <= len(self.args) <= 1

    def patch_version(
        self, version_file_path, regex_pattern, regex_replacement, version
    ):
        with open(version_file_path, "r") as fp:
            contents = fp.read().split("\n")
        contents = [
            re.sub(regex_pattern, regex_replacement % version, line)
            for line in contents
        ]
        with open(version_file_path, "w") as fp:
            fp.write("\n".join(contents))

    def run(self):
        if self.args:
            version = self.args[0]
            # Ensure it's valid.
            Version(version)
        else:
            version = get_version()
            if version is None:
                sys.exit(1)
        if self.verbose:
            print("patching version to", version)

        plover_init_file_path = os.path.join("plover", "__init__.py")
        self.patch_version(
            plover_init_file_path, r"^__version__ = .*$", '__version__ = "%s"', version
        )

        doc_conf_file_path = os.path.join("doc", "conf.py")
        self.patch_version(
            doc_conf_file_path, r"^release = .*$", 'release = "%s"', version
        )


cmdclass["patch_version"] = PatchVersion

# }}}

# `bdist_app` and `bdist_dmg` commands. {{{


class BinaryDistApp(Command):
    description = "create an application bundle for Mac"
    user_options = []
    extra_args = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        cmd = ["bash", "osx/make_app.sh", self.bdist_wheel()]
        if self.verbose:
            print("running", " ".join(cmd))
        subprocess.check_call(cmd)


class BinaryDistDmg(Command):
    user_options = [
        (
            "skip-app-build",
            None,
            "skip building the app; assume dist/Plover.app already exists",
        ),
    ]
    boolean_options = ["skip-app-build"]

    def initialize_options(self):
        self.skip_app_build = False

    def finalize_options(self):
        pass

    def run(self):
        # Build the app first unless the user asked for DMG-only.
        if not self.skip_app_build:
            self.run_command("bdist_app")

        app_path = "dist/Plover.app"
        if not os.path.isdir(app_path):
            raise SystemExit(
                "Plover.app not found in 'dist/'. Build the app first or omit --skip-app-build."
            )

        # Determine targeted macOS platform
        from setuptools.command.bdist_wheel import get_platform

        platform = get_platform(app_path)

        cmd = ["bash", "osx/make_dmg.sh", platform, PACKAGE]
        if self.verbose:
            print("running", " ".join(cmd))
        subprocess.check_call(cmd)


class NotarizeApp(Command):
    user_options = []
    extra_args = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        cmd = ["bash", "osx/notarize_app.sh"]
        if self.verbose:
            print("running", " ".join(cmd))
        subprocess.check_call(cmd)


class NotarizeDmg(Command):
    user_options = []
    extra_args = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import glob

        # Locate the DMG we want to notarize
        dmgs = sorted(glob.glob("dist/*.dmg"))
        if not dmgs:
            raise SystemExit(
                "No DMG found in 'dist/'. Build the DMG first (bdist_dmg)."
            )
        if len(dmgs) > 1:
            raise SystemExit(
                "Multiple DMGs found in 'dist/': "
                + ", ".join(os.path.basename(p) for p in dmgs)
            )
        dmg_path = dmgs[0]

        cmd = ["bash", "osx/notarize_dmg.sh", dmg_path]
        if self.verbose:
            print("running", " ".join(cmd))
        subprocess.check_call(cmd)


if sys.platform.startswith("darwin"):
    cmdclass["bdist_app"] = BinaryDistApp
    cmdclass["bdist_dmg"] = BinaryDistDmg
    cmdclass["notarize_app"] = NotarizeApp
    cmdclass["notarize_dmg"] = NotarizeDmg

# }}}

# `bdist_appimage` command. {{{


class BinaryDistAppImage(Command):
    description = "create AppImage distribution for Linux"
    user_options = [
        ("docker", None, "use docker to run the build script"),
        (
            "no-update-tools",
            None,
            "don't try to update AppImage tools, only fetch missing ones",
        ),
    ]
    boolean_options = ["docker", "no-update-tools"]

    def initialize_options(self):
        self.docker = False
        self.no_update_tools = False

    def finalize_options(self):
        pass

    def run(self):
        cmd = ["./linux/appimage/build.sh"]
        if self.docker:
            cmd.append("--docker")
        else:
            cmd.extend(("--python", sys.executable))
        if self.no_update_tools:
            cmd.append("--no-update-tools")
        cmd.extend(("--wheel", self.bdist_wheel()))
        if self.verbose:
            print("running", " ".join(cmd))
        subprocess.check_call(cmd)


if sys.platform.startswith("linux"):
    cmdclass["bdist_appimage"] = BinaryDistAppImage

# }}}

# i18n support. {{{

options.update(babel_options(__software_name__))

BuildPy.build_dependencies.append("compile_catalog")
BuildUi.hooks.append("plover_build_utils.pyqt:gettext")

# }}}


def reqs(name):
    with open(os.path.join("reqs", name + ".txt")) as fp:
        return fp.read()


setup(
    name=__software_name__,
    version=__version__,
    description=__description__,
    url=__url__,
    download_url=__download_url__,
    license=__license__,
    options=options,
    cmdclass=cmdclass,
    install_requires=reqs("dist"),
    extras_require={
        "gui_qt": reqs("dist_extra_gui_qt"),
        "log": reqs("dist_extra_log"),
    },
)

# vim: foldmethod=marker
