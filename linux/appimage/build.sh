#!/bin/bash

set -e

. ./plover_build_utils/functions.sh

topdir="$PWD"
distdir="$topdir/dist"
builddir="$topdir/build/appimage"
appdir="$builddir/plover.AppDir"
cachedir="$topdir/.cache/appimage"
wheel=''
python='python3'
update_tools=1
use_docker=0

while [ $# -ne 0 ]
do
  case "$1" in
    -p|--python)
      python="$2"
      shift
      ;;
    -w|--wheel)
      wheel="$2"
      shift
      ;;
    --no-update-tools)
      update_tools=0
      ;;
    --docker)
      use_docker=1
      ;;
    -*)
      err "invalid option: $1"
      exit 1
      ;;
  esac
  shift
done

# Helper to make a copy of the current git checkout (sans ignored/others).
copy_git_checkout()
{(
  src="$1"
  dst="$2"
  mkdir "$2" &&
  cd "$1" &&
  git ls-files -z |
  xargs -0 cp -a --no-dereference --parents --target-directory="$2"
)}

# Helper to extract an AppImage so it can be used without needing fuse.
extract_appimage()
{(
  appimage="$1"
  destdir="$2"

  tmpdir="$(mktemp -d "$(dirname "$destdir")/squashfs-root.XXXXXXXXXX")"
  cd "$tmpdir"
  chmod +x "$appimage"
  "$appimage" --appimage-extract >/dev/null
  mv squashfs-root "$destdir"
  cd ..
  rmdir "$tmpdir"
)}

run rm -rf "$builddir"
run mkdir -p "$builddir" "$cachedir" "$distdir"

version="$("$python" -c 'exec(open("plover/__init__.py").read()); print(__version__)')"
appimage="$distdir/plover-$version-x86_64.AppImage"

if [ $use_docker -eq 1 ]
then
  docker_image='plover:appimage'
  docker_workdir="$topdir/build/appimage/docker"
  docker_srcdir="$docker_workdir/src"
  docker_cache="$cachedir/docker"
  run mkdir -p "$docker_workdir" "$docker_cache"
  if [ -n "$wheel" ]
  then
    run cp "$wheel" "$docker_workdir/${wheel##*/}"
    docker_wheel="../${wheel##*/}"
  else
    docker_wheel=''
  fi
  # Build docker image.
  docker build -t "$docker_image" linux/appimage
  # Create a copy of the current checkout.
  run copy_git_checkout "$topdir" "$docker_srcdir"
  # Setup cache.
  run ln -s /cache "$docker_srcdir/.cache"
  # Create a dedicated user so there are no issues
  # accessing the files generated during the docker
  # run.
  run tee "$docker_workdir/entrypoint.sh" <<EOF
#!/bin/sh
set -ex
useradd -u $(id -u) '$USER'
usermod -a -G sudo '$USER' 2>/dev/null || :
usermod -a -G wheel '$USER' 2>/dev/null || :
usermod -a -G adm '$USER' 2>/dev/null || :
export HOME='/home/$USER'
exec chroot --skip-chdir --userspec='$USER' / "\$@"
EOF
  run chmod a+x "$docker_workdir/entrypoint.sh"
  docker run \
    --entrypoint=/work/entrypoint.sh \
    --network=host \
    --rm=true \
    --tty=true \
    --volume "$docker_cache:/cache" \
    --volume "$docker_workdir:/work" \
    --workdir /work/src \
    "$docker_image" \
    bash "${0#$topdir}" --wheel "$docker_wheel" --python "$python"
    mv "$docker_srcdir/dist/${appimage##*/}" "$appimage"
    exit
fi

# Fetch some helpers.
# Note:
# - extract AppImages so FUSE is not needed.
# - we start with zsync2 and do two passes
#   so it can update itself as needed.
. ./linux/appimage/deps.sh
while read tool url;
do
  [ -n "$url" ] || die 1 "missing URL for $tool"
  if [ ! -r "$cachedir/$tool" ]
  then
    # Initial fetch.
    run wget -O "$cachedir/$tool" "$url"
  else
    # Update using zsync2.
    if [ "$update_tools" -eq 1 -a -n "$zsync2" ]
    then
      run_eval "(cd '$cachedir' && '$zsync2' -o '$cachedir/$tool' '$url.zsync')"
    fi
  fi
  run extract_appimage "$cachedir/$tool" "$builddir/$tool"
  run_eval "$tool='$builddir/$tool/AppRun'"
done <<EOF
zsync2        $zsync2_url
zsync2        $zsync2_url
linuxdeploy   $linuxdeploy_url
appimagetool  $appimagetool_url
EOF

# Generate Plover wheel.
if [ -z "$wheel" ]
then
  run "$python" setup.py bdist_wheel
  wheel="$distdir/plover-$version-py3-none-any.whl"
fi

# Setup Python distribution.
pydist="$appdir/usr"
metadata="$("$python" linux/appimage/pyinfo.py)"
run_eval "$metadata"
run mkdir -p "$pydist/"{bin,lib,"$pystdlib"/..,"$pyinclude"/..}
run cp "$pyexe" "$pydist/bin/python"
run cp -a "$pyprefix/$pyinclude" "$pydist/$pyinclude/../"
run cp -a "$pyprefix/lib/$pyldlib"* "$pyprefix/lib/$pypy3lib" "$pydist/lib/"
run_eval "(cd '$pyprefix' && find '$pystdlib' \\( -name __pycache__ -o -path '$pypurelib' -o -path '$pyplatlib' \\) -prune -o -type f -not -name '*.py[co]' -print0 | xargs -0 cp --parents -t '$pydist')"
run rm -f "$pydist/$pystdlib/sytecustomize.py"
run mkdir -p "$pydist/"{"$pypurelib","$pyplatlib"}

# Switch to AppDir python.
run cp linux/appimage/apprun.sh "$appdir/AppRun"
run_eval "appdir_python(){ env PYTHONNOUSERSITE=1 '$appdir/AppRun' --python \"\$@\"; }"
python='appdir_python'

"$python" --version

# Install boostrap requirements.
get_base_devel

# Copy log_dbus system dependencies.
run cp -Lv /usr/lib/x86_64-linux-gnu/libdbus-1.so "$appdir/usr/lib"

# Trim the fat, first pass.
run cp linux/appimage/blacklist.txt "$builddir/blacklist.txt"
run sed -e "s/\${pyversion}/$pyversion/g" -i "$builddir/blacklist.txt"
run "$python" -m plover_build_utils.trim "$appdir" "$builddir/blacklist.txt"

# Finalize the base AppDir.
# Note: we use a custom launcher that does not change the working directory.
run "$linuxdeploy" \
  --desktop-file='linux/plover.desktop' \
  --icon-file='plover/assets/plover.png' \
  --appdir="$appdir" \
  --verbosity=2

# Install Plover and dependencies.
bootstrap_dist "$wheel"

# Reinstall hidapi with the hidraw backend; libusb reports usage/usage_page as 0,
# which results in HID keyboards not being detected by Plover.
run "$python" -m pip uninstall -y hidapi || true
run_eval "HIDAPI_WITH_HIDRAW=1 HIDAPI_WITH_LIBUSB=0 $python -m pip install --no-binary :all: --no-cache-dir hidapi"

# Trim the fat, second pass.
run "$python" -m plover_build_utils.trim "$appdir" "$builddir/blacklist.txt"

# Make distribution source-less.
# Keep pip sources, as we need them for pip install
run "$python" -m plover_build_utils.source_less "$pydist/$purelib" "$pydist/$platlib" "*/site-packages/pip/*"

# Avoid possible permission errors.
run chmod u+w -R "$appdir"

# Remove empty directories.
remove_emptydirs()
{
  find "$appdir" -type d -empty -print0 |
  xargs -0 --no-run-if-empty rmdir -vp --ignore-fail-on-non-empty
}
run remove_emptydirs

# Check requirements.
run env -i "$appdir/AppRun" --python -I -m plover_build_utils.check_requirements

# Create the AppImage.
run env VERSION="$version" "$appimagetool" --no-appstream "$appdir" "$appimage"
