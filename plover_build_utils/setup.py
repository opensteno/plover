import contextlib
import importlib
import os
import subprocess
import sys

from setuptools.command.build_py import build_py
from setuptools.command.develop import develop
import setuptools
from importlib.metadata import distribution, PackageNotFoundError


class Command(setuptools.Command):
    def build_in_place(self):
        self.run_command("build_py")
        self.reinitialize_command("build_ext", inplace=1)
        self.run_command("build_ext")

    @contextlib.contextmanager
    def project_on_sys_path(self, build=True):
        ei_cmd = self.get_finalized_command("egg_info")
        if build:
            self.build_in_place()
        else:
            ei_cmd.run()
        old_path = sys.path[:]
        old_modules = sys.modules.copy()
        try:
            sys.path.insert(0, os.path.abspath(ei_cmd.egg_base))
            dist = distribution(ei_cmd.egg_name)
            if dist is None:
                raise PackageNotFoundError(f"Package {ei_cmd.egg_name} not found")
            yield
        finally:
            sys.path[:] = old_path
            sys.modules.clear()
            sys.modules.update(old_modules)

    def bdist_wheel(self):
        """Run bdist_wheel and return resulting wheel file path."""
        whl_cmd = self.get_finalized_command("bdist_wheel")
        whl_cmd.run()
        for cmd, py_version, dist_path in whl_cmd.distribution.dist_files:
            if cmd == "bdist_wheel":
                return dist_path
        raise Exception("could not find wheel path")


# i18n support. {{{


def babel_options(package, resource_dir=None):
    if resource_dir is None:
        localedir = "%s/messages" % package
    else:
        localedir = "%s/%s" % (package, resource_dir)
    template = "%s/%s.pot" % (localedir, package)
    return {
        "compile_catalog": {
            "domain": package,
            "directory": localedir,
        },
        "extract_messages": {
            "add_comments": ["i18n:"],
            "output_file": template,
            "strip_comments": True,
        },
        "init_catalog": {
            "domain": package,
            "input_file": template,
            "output_dir": localedir,
        },
        "update_catalog": {
            "domain": package,
            "input_file": template,
            "output_dir": localedir,
        },
    }


# }}}

# UI generation. {{{


class BuildUi(Command):
    description = "build UI files"
    user_options = [
        ("force", "f", "force re-generation of all UI files"),
    ]

    hooks = """
    plover_build_utils.qt_ui_hooks:remove_ui_autoconnection
    """.split()

    def initialize_options(self):
        self.force = False

    def finalize_options(self):
        pass

    def _build_ui(self, src):
        dst = os.path.splitext(src)[0] + "_ui.py"
        if (
            not self.force
            and os.path.exists(dst)
            and os.path.getmtime(dst) >= os.path.getmtime(src)
        ):
            return
        if self.verbose:
            print("generating", dst)

        subprocess.check_call(["pyside6-uic", "--from-imports", src, "-o", dst])

        if sys.platform.startswith("win32"):
            platform_encoding = "cp1252"
        else:
            platform_encoding = "utf-8"

        for hook in self.hooks:
            mod_name, attr_name = hook.split(":")
            mod = importlib.import_module(mod_name)
            hook_fn = getattr(mod, attr_name)
            with open(dst, "r", encoding=platform_encoding) as fp:
                contents = fp.read()
            contents = hook_fn(contents)
            with open(dst, "w", encoding="utf-8") as fp:
                fp.write(contents)

    def _build_resources(self, src):
        dst = os.path.splitext(src)[0] + "_rc.py"
        # Skip if up‑to‑date unless --force was requested
        if (
            not self.force
            and os.path.exists(dst)
            and os.path.getmtime(dst) >= os.path.getmtime(src)
        ):
            return
        if self.verbose:
            print("compiling", src, "->", dst)
        subprocess.check_call(["pyside6-rcc", "-o", dst, src])

    def run(self):
        self.run_command("egg_info")
        std_hook_prefix = __package__ + ".qt_ui_hooks:"
        hooks_info = [
            h[len(std_hook_prefix) :] if h.startswith(std_hook_prefix) else h
            for h in self.hooks
        ]
        if self.verbose:
            print("generating UI using hooks:", ", ".join(hooks_info))
        ei_cmd = self.get_finalized_command("egg_info")

        for src in ei_cmd.filelist.files:
            if src.endswith(".qrc"):
                self._build_resources(src)
            if src.endswith(".ui"):
                self._build_ui(src)


# }}}


# Patched `build_py` command. {{{


class BuildPy(build_py):
    build_dependencies = []

    def run(self):
        for command in self.build_dependencies:
            self.run_command(command)
        build_py.run(self)


# }}}

# Patched `develop` command. {{{


class Develop(develop):
    build_dependencies = []

    def run(self):
        for command in self.build_dependencies:
            self.run_command(command)
        develop.run(self)


# }}}
