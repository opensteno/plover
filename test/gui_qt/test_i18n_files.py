import os
import subprocess
import sys
import tempfile
import difflib
import shutil
from pathlib import Path

import pytest

import plover


def filter_i18n_file(lines):
    filtered = []
    for line in lines:
        # Ignore Copyright and Author comments
        if line.startswith("# Copyright (C)"):
            continue
        if line.startswith("# FIRST AUTHOR"):
            continue
        # Ignore volatile header metadata fields that change on every run
        if any(
            field in line
            for field in [
                '"POT-Creation-Date:',
                '"PO-Revision-Date:',
                '"Generated-By:',
                '"Report-Msgid-Bugs-To:',
                '"X-Generator:',
                '"Last-Translator:',
                '"Language-Team:',
            ]
        ):
            continue
        filtered.append(line)
    return filtered


def run_pybabel(args, cwd, env):
    cmd = [sys.executable, "-m", "babel.messages.frontend"] + args
    try:
        return subprocess.check_output(
            cmd,
            cwd=cwd,
            env=env,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        print(f"\nCommand {' '.join(cmd)} failed with output:\n{e.output.decode()}")
        raise


@pytest.mark.gui_qt
def test_i18n_files_up_to_date():
    # Paths setup
    root_dir = Path(__file__).parent.parent.parent.absolute()
    messages_dir = root_dir / "plover" / "messages"
    pot_path = messages_dir / "plover.pot"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir_path = Path(tmpdir)
        # Copy the current messages directory to avoid polluting the workspace
        tmp_messages_dir = tmp_dir_path / "messages"
        shutil.copytree(messages_dir, tmp_messages_dir)

        tmp_pot_path = tmp_messages_dir / "plover.pot"

        env = os.environ.copy()
        # Ensure the project root is in PYTHONPATH
        env["PYTHONPATH"] = str(root_dir)

        # 1. Run extraction into the temp POT
        # Matches settings in plover_build_utils/setup.py:babel_options
        run_pybabel(
            [
                "extract",
                "--project",
                "plover",
                "--version",
                plover.__version__,
                "--add-comments",
                "i18n:",
                "--strip-comments",
                "-o",
                str(tmp_pot_path),
                "plover",
            ],
            cwd=root_dir,
            env=env,
        )

        # 2. Run update_catalog in the temp messages dir
        run_pybabel(
            [
                "update",
                "--domain",
                "plover",
                "-i",
                str(tmp_pot_path),
                "-d",
                str(tmp_messages_dir),
            ],
            cwd=root_dir,
            env=env,
        )

        # 3. Compare POT
        with open(pot_path, "r", encoding="utf-8") as f:
            current_pot_lines = f.readlines()
        with open(tmp_pot_path, "r", encoding="utf-8") as f:
            generated_pot_lines = f.readlines()

        pot_diff = "".join(
            difflib.unified_diff(
                filter_i18n_file(current_pot_lines),
                filter_i18n_file(generated_pot_lines),
                fromfile="plover/messages/plover.pot",
                tofile="newly_extracted.pot",
            )
        )

        # 4. Compare POs
        po_diffs = []
        # Find all PO files in the original messages dir
        for current_po_path in messages_dir.glob("*/LC_MESSAGES/plover.po"):
            relative_path = current_po_path.relative_to(messages_dir)
            generated_po_path = tmp_messages_dir / relative_path

            with open(current_po_path, "r", encoding="utf-8") as f:
                current_po_lines = f.readlines()
            with open(generated_po_path, "r", encoding="utf-8") as f:
                generated_po_lines = f.readlines()

            diff = "".join(
                difflib.unified_diff(
                    filter_i18n_file(current_po_lines),
                    filter_i18n_file(generated_po_lines),
                    fromfile=f"plover/messages/{relative_path}",
                    tofile=f"newly_updated_{relative_path.name}",
                )
            )
            if diff:
                po_diffs.append(diff)

        # Final validation
        if pot_diff or po_diffs:
            error_msg = "Fix with: python setup.py extract_messages update_catalog\n\n"
            if pot_diff:
                error_msg += f"POT Diff:\n{pot_diff}\n"
            for diff in po_diffs:
                error_msg += f"PO Diff:\n{diff}\n"
            assert False, error_msg
