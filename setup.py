#!/usr/bin/env python3


import os
import platform
import stat
import sys
import tarfile
import zipfile
from distutils.command.build import build as orig_build
from distutils.core import Command
from pathlib import Path

from setuptools import setup
from setuptools.command.install import install as orig_install

SHELLCHECK_VERSION = "0.10.0"


class build(orig_build):
    sub_commands = orig_build.sub_commands + [("fetch_executables", None)]


class install(orig_install):
    sub_commands = orig_install.sub_commands + [("install_executable", None)]


class fetch_executables(Command):
    build_temp = None

    def initialize_options(self):
        pass

    def finalize_options(self):
        self.set_undefined_options("build", ("build_temp", "build_temp"))

    def run(self):
        # Save executable to self.build_temp
        compressed_path = self._get_compressed_executable_path()
        self._extract_executable(compressed_path)

    def _get_compressed_executable_path(self):
        executables = Path(__file__).parent.resolve() / "executables"
        sys_platform = sys.platform
        platform_machine = platform.machine()

        if sys_platform == "darwin" and platform_machine == "arm64":
            platform_machine = "aarch64"
        elif sys_platform == "linux" and platform_machine == "armv7l":
            platform_machine = "armv6hf"

        if (executables / f"shellcheck-v{SHELLCHECK_VERSION}.{sys_platform}.{platform_machine}.tar.xz").exists():
            return executables / f"shellcheck-v{SHELLCHECK_VERSION}.{sys_platform}.{platform_machine}.tar.xz"
        elif (
            (sys_platform == "win32" and platform_machine in ("AMD64", "ARM64"))
            or (sys_platform == "cygwin" and platform_machine == "x86_64")
        ) and (executables / f"shellcheck-v{SHELLCHECK_VERSION}.zip").exists():
            return executables / f"shellcheck-v{SHELLCHECK_VERSION}.zip"
        else:
            raise RuntimeError(f"Unsupported platform: {sys_platform} {platform_machine}")

    def _extract_executable(self, compressed_path):
        if ".tar" in compressed_path.suffixes:
            with tarfile.open(str(compressed_path)) as tar:
                for member in tar.getmembers():
                    if member.isfile() and member.name.endswith("shellcheck"):
                        self._save_executable(tar.extractfile(member).read())
                        return
        elif compressed_path.suffix == ".zip":
            with zipfile.ZipFile(str(compressed_path)) as zip:
                for info in zip.infolist():
                    if info.filename.endswith(".exe"):
                        self._save_executable(zip.read(info.filename))
                        return
        raise RuntimeError(
            f"File has unsupported compressed format or no executable was found inside: {str(compressed_path)}"
        )

    def _save_executable(self, data):
        exe_name = "shellcheck" if sys.platform not in ("win32", "cygwin") else "shellcheck.exe"
        exe_path = Path(self.build_temp) / exe_name
        Path(self.build_temp).mkdir(parents=True, exist_ok=True)

        with exe_path.open("wb") as fp:
            fp.write(data)

        # Mark as executable.
        # https://stackoverflow.com/a/14105527
        mode = os.stat(str(exe_path)).st_mode
        mode |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        os.chmod(str(exe_path), mode)


class install_executable(Command):
    description = "install the executable"
    outfiles = ()
    build_dir = install_dir = None

    def initialize_options(self):
        pass

    def finalize_options(self):
        # this initializes attributes based on other commands' attributes
        self.set_undefined_options("build", ("build_temp", "build_dir"))
        self.set_undefined_options("install", ("install_scripts", "install_dir"))

    def run(self):
        self.outfiles = self.copy_tree(self.build_dir, self.install_dir)

    def get_outputs(self):
        return self.outfiles


cmdclass = {
    "install": install,
    "install_executable": install_executable,
    "build": build,
    "fetch_executables": fetch_executables,
}


try:
    from wheel.bdist_wheel import bdist_wheel as orig_bdist_wheel
except ImportError:
    pass
else:

    class bdist_wheel(orig_bdist_wheel):
        def finalize_options(self):
            orig_bdist_wheel.finalize_options(self)
            # Mark us as not a pure python package
            self.root_is_pure = False

        def get_tag(self):
            _, _, plat = orig_bdist_wheel.get_tag(self)
            # We don't contain any python source, nor any python extensions
            return "py2.py3", "none", plat

    cmdclass["bdist_wheel"] = bdist_wheel


setup(cmdclass=cmdclass)
