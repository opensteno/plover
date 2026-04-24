#!/usr/bin/env bash
set -e

# Sign and notarize + staple a .dmg image.
# Enabled with:
#   MACOS_NOTARIZE_ENABLED=1
# Required envs when notarization is enabled:
#   MACOS_CODESIGN_IDENTITY
#   MACOS_NOTARIZE_TEAM_ID
#   MACOS_NOTARIZE_KEY_ID
#   MACOS_NOTARIZE_ISSUER_ID
#   MACOS_NOTARIZE_KEY_CONTENTS
# Optional:
#   MACOS_CODESIGN_KEYCHAIN, e.g. plover-dev.keychain

topdir="$PWD"
builddir="$topdir/build/osxapp"
APP="$topdir/dist/Plover.app"

notarize_enabled="${MACOS_NOTARIZE_ENABLED:-0}"
if [[ "$notarize_enabled" != "1" ]]; then
  echo "ℹ️ Skipping notarization of $APP (MACOS_NOTARIZE_ENABLED=$notarize_enabled)"
  return 0
fi

. ./plover_build_utils/functions.sh
. ./osx/notarize_common.sh

# --- Codesign ---
require_env MACOS_CODESIGN_IDENTITY
echo "Signing with identity: $MACOS_CODESIGN_IDENTITY ..."
# Make sure the build directory exists for the entitlements file
mkdir -p "$builddir"
ent_plist="$builddir/entitlements.plist"
cat >"$ent_plist" <<'EOS'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.cs.allow-jit</key><true/>
  <key>com.apple.security.cs.allow-unsigned-executable-memory</key><true/>
  <key>com.apple.security.cs.disable-library-validation</key><true/>
</dict>
</plist>
EOS

# Build common codesign args
cs_args=(--force --timestamp --options runtime --entitlements "$ent_plist" -s "$MACOS_CODESIGN_IDENTITY")
if [[ -n "${MACOS_CODESIGN_KEYCHAIN:-}" ]]; then
  cs_args+=(--keychain "$MACOS_CODESIGN_KEYCHAIN")
  echo "Using keychain: $MACOS_CODESIGN_KEYCHAIN"
fi

# 1) Sign all Mach-O binaries first: *.dylib, *.so, and the actual executables inside
#    framework Versions directories. This ensures their _CodeSignature folders exist
#    before we sign the framework bundle itself, preventing resource seal mismatches.
while IFS= read -r -d '' f; do
  run_quiet /usr/bin/codesign "${cs_args[@]}" "$f"
done < <(find "$APP/Contents" -type f \
            \( -name "*.dylib" -o -name "*.so" -o \
               \( -path "*/*.framework/Versions/*" -perm -111 \) \
            \) -print0)

# 2) Now sign framework bundles depth-first, after their contents are signed.
while IFS= read -r -d '' fw; do
  run_quiet /usr/bin/codesign "${cs_args[@]}" "$fw"
done < <(find "$APP/Contents" -depth -type d -name "*.framework" -print0)

# 3) Sign the main executable and then the app bundle.
run_quiet /usr/bin/codesign "${cs_args[@]}" "$APP/Contents/MacOS/Plover"
run_quiet /usr/bin/codesign "${cs_args[@]}" "$APP"

echo "Verifying signature..."
run_quiet /usr/bin/codesign --verify --deep --strict "$APP"
run_quiet /usr/bin/codesign --verify --deep --strict "$APP/Contents/Frameworks/Python.framework"
echo "✅ Code signing complete"
# --- End codesign ---

# Notarize & staple app
notarize_and_staple "$APP"
