#!/bin/bash

opt_dry_run=0
opt_timings=0

# Default CI to false if not set
: "${CI:=false}"

python='false'
cache_dir='.cache'
wheels_cache="$cache_dir/wheels"
downloads_cache="$cache_dir/downloads"

# Usage: parse_opts args "$@"
#
# `$args` will be set to unhandled options and non-option arguments.
#
# Consumed options:
#
# --dry-run/-n: don't execute run/run_eval commands (print them instead)
# --debug/-d: enable `set -x` for debugging script
# --: stop options processing
#
# Tip: to update $@ after the call, use:
# parse_opts args "$@" && set -- "${args[@]}"
parse_opts()
{
  args_varname="$1"
  shift
  local _args=()
  while [ $# -ne 0 ]
  do
    case "$1" in
      --dry-run|-n)
        opt_dry_run=1
        ;;
      --debug|-d)
        set -x
        ;;
      --)
        shift
        _args+=("$@")
        break
        ;;
      *)
        _args+=("$1")
        ;;
    esac
    shift
  done
  eval "$args_varname=(\"\${_args[@]}\")"
}

info()
{
  color=34
  case "$1" in
    -c*)
      color="${1#-c}"
      shift
      ;;
  esac
  if [ -t 2 -o "x$CI" = "xtrue" ]
  then
    echo "[${color}m$@[0m" 1>&2
  else
    echo "$@" 1>&2
  fi
}

err()
{
  info -c31 "$@"
}

die()
{
  code=$?
  if [ $# -ne 0 ]
  then
    code="$1"
    shift
  fi
  if [ $# -ne 0 ]
  then
    err "$@"
  fi
  exit "$code"
}

# Internal runner: first arg must be --normal, --quiet, or --stderr-only
_run_impl() {
  local mode="$1"; shift

  if [ "$mode" != "--quiet" ]; then
    if [ $opt_dry_run -eq 0 -a "x$CI" = "xtrue" ]; then
      echo -n '::group::' 1>&2
    fi

    info "$(printf "%q " "$@")"
  fi

  [ $opt_dry_run -ne 0 ] && return

  if [ $opt_timings -ne 0 ]; then
    case "$mode" in
      --quiet)
        { time "$@" >/dev/null 2>&1; }
        code=$?
        ;;
      --stderr-only)
        { time "$@" >/dev/null; } 2>&1
        code=$?
        ;;
      *)
        time "$@"
        code=$?
        ;;
    esac
  else
    case "$mode" in
      --quiet)
        "$@" >/dev/null 2>&1
        code=$?
        ;;
      --stderr-only)
        "$@" >/dev/null
        code=$?
        ;;
      *)
        "$@"
        code=$?
        ;;
    esac
  fi

  if [ "$mode" != "--quiet" ]; then
    if [ "x$CI" = "xtrue" ]; then
      echo "::endgroup::" 1>&2
    fi
  fi
  return $code
}

run()          { _run_impl --normal "$@"; }
run_quiet()    { _run_impl --quiet  "$@"; }
run_stderr()   { _run_impl --stderr-only "$@"; }

require_env() {
  local name=${1:?}
  if [[ -z "${!name:-}" ]]; then
    echo "❌ Missing required env: $name" >&2
    exit 1
  fi
}

run_eval()
{
  info "$@"
  [ $opt_dry_run -ne 0 ] && return
  if [ $opt_timings -ne 0 ]
  then
    time eval "$@"
  else
    eval "$@"
  fi
}

sha1sum()
{
  kernel="$(uname -s)" || die
  if [ "$kernel" = 'Darwin' ]
  then
    shasum "$@"
  else
    command sha1sum "$@"
  fi
}

get_base_devel()
{
  run "$python" -m plover_build_utils.get_pip -c reqs/constraints.txt -r reqs/bootstrap.txt "$@"
}

install_wheels()
{
  run "$python" -m plover_build_utils.install_wheels --disable-pip-version-check "$@"
}

bootstrap_dist()
{
  wheel="$1"
  shift
  get_base_devel "$wheel" --no-deps "$@" || die
  # Install plover's dependencies
  install_wheels \
    -c reqs/constraints.txt \
    -r reqs/dist.txt \
    -r reqs/dist_extra_gui_qt.txt \
    -r reqs/dist_extra_log.txt \
    "$@" || die

  # Avoid caching Plover's wheel.
  if [ -f "$wheels_cache/$(basename "$wheel")" ]; then
    info "Removing cached wheel: $wheels_cache/$(basename "$wheel")"
    run rm "$wheels_cache/$(basename "$wheel")"
  else
    info "Wheel was not cached so no need to remove it: $wheels_cache/$(basename "$wheel")"
  fi
}

osx_standalone_python()
{
  [[ $# -eq 6 ]] || return 1

  dest="$1"
  py_version="$2"
  py_macos="$3"
  py_sha1="$4"
  reloc_py_url="$5"
  reloc_py_sha1="$6"

  py_framework_dir="$dest/Python.framework"

  [[ ! -e "$py_framework_dir" ]] || return 1

  run mkdir -p "$dest"
  run "$python" -m plover_build_utils.download "https://www.python.org/ftp/python/$py_version/python-$py_version-macos$py_macos.pkg" "$py_sha1"
  reloc_py_zip="$(run "$python" -m plover_build_utils.download "$reloc_py_url" "$reloc_py_sha1")"
  run unzip -d "$dest" "$reloc_py_zip"
  reloc_py_dir="$(echo -n "$dest"/relocatable-python-*/)"
  run "$python" "$reloc_py_dir/make_relocatable_python_framework.py" \
    --baseurl="file://$PWD/$downloads_cache/%s/../python-%s-macos%s.pkg" \
    --python-version="$py_version" --os-version="$py_macos" \
    --destination="$dest" \
    --without-pip \
    ;
  run ln -s 'python3' "$py_framework_dir/Versions/Current/bin/python"
  run rm -rf "$reloc_py_dir"
}

packaging_checks()
{
  run rm -rf dist
  # Check PEP 517/518 support.
  run "$python" -m build --sdist --wheel .
  # Validate distributions.
  run "$python" -m twine check --strict dist/*
  # Check manifest.
  run "$python" -m check_manifest -v
}

git_tree_sha1()
{
  if [ "x$1" = "x-d" ]
  then
    debug=1
    shift
  else
    debug=1
  fi
  refspec="$1"
  shift
  # Build excludes list.
  excludes=()
  for skiplist in "$@"
  do
    IFS=$'\r\n' read -r -d '{EOF}' -a patterns <"$skiplist" || die
    excludes+=("${patterns[@]/#/:!:}")
  done
  if [ $debug -eq 1 ]
  then
    info "excludes [${#excludes[@]}]"
    echo "${excludes[@]}" 1>&2
  fi
  # Build source tree listing.
  IFS=$'\r\n' sources=($(git ls-files "${excludes[@]}")) || die
  if [ $debug -eq 1 ]
  then
    info "sources [${#sources[@]}]:"
    echo "${sources[@]}" 1>&2
  fi
  # Build git tree listing.
  tree="$(git ls-tree "$refspec" "${sources[@]}")" || die
  if [ $debug -eq 1 ]
  then
    info "tree: [$(wc -l <<<"$tree")]"
    echo "${tree}" 1>&2
  fi
  # Calculate tree SHA1.
  sha1="$(sha1sum <<<"$tree")" || die
  sha1="${sha1%% *}"
  if [ $debug -eq 1 ]
  then
    info "sha1: $sha1"
  fi
  echo "$sha1"
}

release_prepare()
{
  [ $# -eq 1 ] || die 1 'expecting one argument: the new version'
  run "$python" setup.py patch_version "$1"
  run git add plover/__init__.py
  run git add doc/conf.py
  run towncrier build --version "$1" --yes
}

release_finalize()
{
  [ $# -eq 0 ] || die 1 'expecting no argument'
  version="$("$python" setup.py --version)"
  message="Release version $version"
  tag="v$version"
  run git commit -m "$message"
  run git tag -m "$message" "$tag"
  cat <<EOF
# now all that's left is to push to GitHub:
# first push the release commit:
git push
# and once the build was successful, assuming \`origin\` is the correct remote, push the tag:
git push origin "$tag"
EOF
}

# If this file is being executed directly (not sourced), parse options
# This avoids running parse_opts during a simple source() from another
# script where $@ may be empty and `set -u` is active, which can lead to
# "unbound variable" errors when expanding arrays.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  parse_opts args "$@"
  set -- "${args[@]}"
fi
