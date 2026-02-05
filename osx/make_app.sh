#!/usr/bin/env bash

set -e

. ./plover_build_utils/functions.sh

topdir="$PWD"
builddir="$topdir/build/osxapp"
appdir="$builddir/Plover.app"
distdir="$topdir/dist/Plover.app"
python='python3'
plover_wheel="$1"

. ./osx/deps.sh

py_version="$py_installer_version"
bundle_id="org.openstenoproject.plover"

echo "Making Plover.app with Plover wheel $plover_wheel."

run rm -rf "$builddir" "$distdir"
run mkdir -p "$appdir"

# Make skeleton.
macos_dir="$appdir/Contents/MacOS"
resources_dir="$appdir/Contents/Resources"
frameworks_dir="$appdir/Contents/Frameworks"
py_home="$frameworks_dir/Python.framework/Versions/Current"
run mkdir -p "$frameworks_dir" "$resources_dir" "$macos_dir"

# Create the Python framework.
run osx_standalone_python "$frameworks_dir" "$py_installer_version" "$py_installer_macos" "$py_installer_sha1" "$reloc_py_url" "$reloc_py_sha1"

py_binary="$py_home/bin/python${py_version%.*}"

# Extract Python binary from launcher and fix its references.
run mv "$py_home/Resources/Python.app/Contents/MacOS/Python" "$py_binary"

echo "Rewrite runtime search path of Python binary with install_name_tool..."
run_quiet install_name_tool -rpath "@executable_path/../../../../../../" "@executable_path/../../../" "$py_binary"
echo "Rewrite runtime search path complete"

echo "Ad-hoc signing the Python binary after install_name_tool invalidated signature..."
run_quiet /usr/bin/codesign -s - --force "$py_binary"
echo "Ad-hoc signing complete"

run tee "$py_home/bin/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>${bundle_id}</string>
</dict>
</plist>
EOF

# Switch to target Python.
SSL_CERT_FILE="$("$python" -m certifi)"
run_eval "appdir_python() { env PYTHONNOUSERSITE=1 \"$py_home/bin/python\" \"\$@\"; }"
run_eval "export SSL_CERT_FILE='$SSL_CERT_FILE'"
run_eval "unset __PYVENV_LAUNCHER__"
python='appdir_python'

# Install Plover and dependencies.
bootstrap_dist "$plover_wheel"

# Create launcher.
run gcc -Wall -O2 -arch x86_64 -arch arm64 'osx/app_resources/plover_launcher.c' -o "$macos_dir/Plover"

# Copy icon.
run cp 'osx/app_resources/plover.icns' "$resources_dir/plover.icns"

# Get Plover's version.
plover_version="$("$python" -c 'print(__import__("plover").__version__)')"

# Setup PList for Plover.
run cp 'osx/app_resources/Info.plist' "$appdir/Contents/Info.plist"
year="$(date '+%Y')"
run sed -e "s/\$version/$plover_version/" -e "s/\$year/$year/" -i '' "$appdir/Contents/Info.plist"

# Trim superfluous content.
run cp osx/app_resources/dist_blacklist.txt "$builddir/dist_blacklist.txt"
run sed -e "s/\$python_version/$py_version/" -e "s/\$python_base_version/${py_version%.*}/" -i '' "$builddir/dist_blacklist.txt"
run "$python" -m plover_build_utils.trim "$py_home" "$builddir/dist_blacklist.txt"

# Make distribution source-less.
# Keep pip sources, as we need them for pip install
run "$python" -m plover_build_utils.source_less "$py_home/lib" "*/site-packages/pip/*"

# Check requirements.
run "$python" -I -m plover_build_utils.check_requirements

# Ad-hoc signing to satisfy Gatekeeper.
run /usr/bin/codesign -s - --deep --force "$appdir"

# Move the finished app to dist.
run mv "$appdir" "$distdir"
