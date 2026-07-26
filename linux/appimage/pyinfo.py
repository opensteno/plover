import sys
from distutils import sysconfig

print(
    "; ".join(
        f"py{k}={v!r}"
        for k, v in sorted(
            {
                "exe": sys.executable,
                "prefix": getattr(sys, "base_prefix", sys.prefix),
                "version": sysconfig.get_python_version(),
                "include": sysconfig.get_python_inc(prefix=""),
                "ldlib": sysconfig.get_config_var("LDLIBRARY"),
                "py3lib": sysconfig.get_config_var("PY3LIBRARY"),
                "stdlib": sysconfig.get_python_lib(standard_lib=1, prefix=""),
                "purelib": sysconfig.get_python_lib(plat_specific=0, prefix=""),
                "platlib": sysconfig.get_python_lib(plat_specific=1, prefix=""),
            }.items()
        )
    )
)
