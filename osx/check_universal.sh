#!/bin/bash
# Verify all binaries in a Python.framework are universal (arm64 + x86_64).
# Usage: check_universal.sh <framework_path> <python_base_version>
# Example: check_universal.sh .../Python.framework 3.13

set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 <framework_path> <python_base_version>"
    exit 1
fi

framework_path="$1"
python_version="$2"

if [[ $python_version != *"3."* ]]; then
    echo "Invalid Python version: $python_version"
    exit 1
fi

STATUS=0

# Ensure all .so and .dylib files are universal.
LIB_COUNT=$(find "$framework_path" -name "*.so" -or -name "*.dylib" | wc -l)
UNIVERSAL_COUNT=$(find "$framework_path" -name "*.so" -or -name "*.dylib" | xargs file | grep "2 architectures" | wc -l)
if [ "$LIB_COUNT" != "$UNIVERSAL_COUNT" ]; then
    echo "$LIB_COUNT libraries (*.so and *.dylib) found in the framework; only $UNIVERSAL_COUNT are universal!"
    echo "The following libraries are not universal:"
    find "$framework_path" -name "*.so" -or -name "*.dylib" | xargs file | grep -v "2 architectures" | grep -v "(for architecture"
    STATUS=1
fi

# Check key binaries in the framework.
KEY_BINARIES="$framework_path/Versions/Current/Python
$framework_path/Versions/Current/bin/python$python_version"

for TESTFILE in $KEY_BINARIES; do
    ARCH_TEST=$(file "$TESTFILE" | grep "2 architectures")
    if [ "$ARCH_TEST" == "" ]; then
        echo "$TESTFILE is not universal!"
        STATUS=1
    fi
done

# The Python.app binary may have been moved by make_app.sh (line 40) before
# this script runs, so skip it with a warning if absent.
PYTHON_APP_BINARY="$framework_path/Versions/$python_version/Resources/Python.app/Contents/MacOS/Python"
if [ ! -f "$PYTHON_APP_BINARY" ]; then
    echo "Warning: $PYTHON_APP_BINARY not found (likely moved by make_app.sh), skipping."
else
    ARCH_TEST=$(file "$PYTHON_APP_BINARY" | grep "2 architectures")
    if [ "$ARCH_TEST" == "" ]; then
        echo "$PYTHON_APP_BINARY is not universal!"
        STATUS=1
    fi
fi

[[ $STATUS == 0 ]] && echo "All files are universal!" || exit $STATUS
