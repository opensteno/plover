#!/bin/bash

set -e

. ./plover_build_utils/functions.sh

opt_incremental=0
opt_installer=0
opt_trim=0
opt_zipdir=0
args=()

while [ $# -ne 0 ]
do
  case "$1" in
    --incremental)
      opt_incremental=1
      ;;
    -i|--installer)
      opt_installer=1
      ;;
    -t|--trim)
      opt_trim=1
      ;;
    -z|--zipdir)
      opt_zipdir=1
      ;;
    -*)
      die 1 "invalid option \`$1\`"
      ;;
    *)
      args+=("$1")
      ;;
  esac
  shift
done

[ ${#args[@]} -eq 3 ] || die 1 "expected 3 arguments, got ${#args[@]}: ${args[*]}"

name="${args[0]}" version="${args[1]}" wheel="${args[2]}"
builddir="build/windist"
distdir="dist/$name-$version-win64"
distzip="$distdir.zip"
installer="$distdir.setup.exe"
python='python'

. ./windows/dist_deps.sh

py_base_ver="${py_version%.*}"
py_base_ver="${py_base_ver//.}"

build_dist()
{(
  # Fetch official python distribution.
  py_zip="$(run "$python" -m plover_build_utils.download "https://www.python.org/ftp/python/$py_version/python-$py_version-amd64.zip" "$py_sha1")" || die
  
  # Setup Python distribution.
  dist_data="$builddir/data"
  run mkdir -p "$dist_data"
  run unzip -d "$dist_data" "$py_zip"

  # Switch to the distribution Python.
  dist_python=("$dist_data/python.exe")

  kernel="$(uname -s)" || die
  if [ "$kernel" = "Linux" ]
  then
    dist_python=(wine "$dist_python")
  fi
  run_eval "dist_python(){ env PYTHONNOUSERSITE=1 "${dist_python[@]}" \"\$@\"; }"
  python='dist_python'

  # Install Plover and dependencies.
  bootstrap_dist "$wheel" --no-warn-script-location

  # Trim the fat...
  if [ $opt_trim -eq 1 ]
  then
    run "$python" -m plover_build_utils.trim "$dist_data" 'windows/dist_blacklist.txt'
  fi

  # Add miscellaneous files: icon, license, ...
  run cp LICENSE.txt "$builddir/"
  run cp plover/assets/plover.ico "$dist_data/"

  # Create launchers.
  run_eval "$python <<EOF
from pip._vendor.distlib.scripts import ScriptMaker
sm = ScriptMaker(source_dir=r'$builddir', target_dir=r'$builddir')
sm.executable = r'data\\python.exe'
sm.variants = set(('',))
sm.make('plover = plover.scripts.dist_main:main', options={'gui': True})
sm.make('plover_console = plover.scripts.dist_main:main', options={'gui': False})
EOF"

  # Fix Visual C++ Redistributable DLL location.
  run mv {"$dist_data","$builddir"}/vcruntime140.dll

  # Make distribution source-less.
  # Keep pip sources, as we need them for pip install
  run "$python" -m plover_build_utils.source_less "$dist_data" "*/site-packages/pip/*"

  # Check requirements.
  run "$python" -I -m plover_build_utils.check_requirements

  run mv "$builddir" "$distdir"
)}

zip_dist()
{
  run "$python" -m plover_build_utils.zipdir "$distdir"
}

build_installer()
{
  # Compute installed size.
  install_size="$($python - "$distdir" <<EOF
import os, sys
size = sum(os.path.getsize(os.path.join(dirpath, f))
           for dirpath, dirnames, filenames
           in os.walk(sys.argv[1]) for f in filenames)
print((size + 1023) // 1024)
EOF
)" || die
  # Create installer.
  run makensis -NOCD \
    -Dsrcdir="$distdir" \
    -Dversion="$version" \
    -Dinstall_size="$install_size" \
    windows/installer.nsi \
    "-XOutFile $installer"
}

artifacts=("$builddir" "$distdir")
if [ $opt_zipdir -eq 1 ]
then
  artifacts+=("$distzip")
fi
if [ $opt_installer -eq 1 ]
then
  artifacts+=("$installer")
fi
if [ $opt_incremental -eq 0 -o ! -e "$distdir" ]
then
  run rm -rf "${artifacts[@]}"
fi

if [ ! -e "$distdir" ]
then
  build_dist
fi
if [ $opt_zipdir -eq 1 -a ! -e "$distzip" ]
then
  zip_dist
fi
if [ $opt_installer -eq 1 -a ! -e "$installer" ]
then
  build_installer
fi
