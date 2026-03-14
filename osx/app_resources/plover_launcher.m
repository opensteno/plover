#import <Cocoa/Cocoa.h>
#include <Python.h>
#include <libgen.h>
#include <limits.h>
#include <unistd.h>

/**
 * Plover macOS Launcher
 *
 * Entry point for the Plover application bundle. It initializes the bundled 
 * Python interpreter and runs the Plover GUI or a specified CLI module.
 * It remains in the same process to ensure the macOS menu bar works correctly.
 */

int main(int argc, char *argv[]) {
    @autoreleasepool {
        // --- 1. Locate the Bundle ---
        // Resolve the absolute path to find bundled Frameworks relative to the executable.
        char *argv0_realpath = realpath(argv[0], NULL);
        if (argv0_realpath == NULL) {
            fprintf(stderr, "Fatal error: unable to resolve executable path.\n");
            return 1;
        }

        // Move up from MacOS/plover_launcher to the 'Contents' directory.
        char *contents_dir = dirname(dirname(argv0_realpath));

        char python_home[PATH_MAX];
        snprintf(python_home, sizeof(python_home), "%s/Frameworks/Python.framework/Versions/Current", contents_dir);

        // --- 2. Environment Setup ---
        // Redirect user plugins to 'Application Support/plover' to follow macOS conventions.
        char *home = getenv("HOME");
        if (home) {
            char p[PATH_MAX];
            snprintf(p, sizeof(p), "%s/Library/Application Support/plover/plugins/mac", home);
            setenv("PYTHONUSERBASE", p, 1);
        }

        // --- 3. Interpreter Configuration ---
        PyConfig config;
        PyConfig_InitPythonConfig(&config);

        wchar_t *w_home = Py_DecodeLocale(python_home, NULL);
        if (w_home == NULL) {
            fprintf(stderr, "Fatal error: failed to decode Python home path.\n");
            free(argv0_realpath);
            return 1;
        }
        // Set Python's home directory (equivalent to PYTHONHOME).
        PyStatus status = PyConfig_SetString(&config, &config.home, w_home);
        PyMem_RawFree(w_home);
        if (PyStatus_Exception(status)) goto fatal_error;

        // --- 4. Argument Handling ---
        // Forward arguments as-is if -m or -c is used; otherwise, default to the GUI entry point.
        if (argc >= 2 && (strcmp(argv[1], "-m") == 0 || strcmp(argv[1], "-c") == 0)) {
            status = PyConfig_SetBytesArgv(&config, argc, argv);
        } else {
            // Transform 'plover [args]' into 'python -m plover.scripts.main [args]'.
            char **n_argv = malloc(sizeof(char*) * (argc + 2));
            if (n_argv == NULL) {
                fprintf(stderr, "Fatal error: out of memory while preparing arguments.\n");
                free(argv0_realpath);
                return 1;
            }
            n_argv[0] = argv[0];
            n_argv[1] = "-m";
            n_argv[2] = "plover.scripts.main";
            for (int i = 1; i < argc; i++) {
                n_argv[i+2] = argv[i];
            }
            status = PyConfig_SetBytesArgv(&config, argc + 2, n_argv);
            free(n_argv);
        }
        if (PyStatus_Exception(status)) goto fatal_error;

        // --- 5. Initialization ---
        status = Py_InitializeFromConfig(&config);
        PyConfig_Clear(&config);
        if (PyStatus_Exception(status)) goto fatal_error;

        // --- 6. Site-Packages Injection ---
        // Prepend the bundled site-packages to sys.path to ensure bundled dependencies are prioritized.
        PyObject* sys_path = PySys_GetObject("path");
        if (sys_path != NULL) {
            char sp[PATH_MAX];
            snprintf(sp, sizeof(sp), "%s/lib/python3.13/site-packages", python_home);
            wchar_t *w_sp = Py_DecodeLocale(sp, NULL);
            if (w_sp) {
                PyObject* p_sp = PyUnicode_FromWideChar(w_sp, -1);
                if (p_sp) {
                    PyList_Insert(sys_path, 0, p_sp);
                    Py_DECREF(p_sp);
                }
                PyMem_RawFree(w_sp);
            }
        }

        // --- 7. Execution ---
        // Run the interpreter; returns the exit code of the Python process.
        free(argv0_realpath);
        return Py_RunMain();

    fatal_error:
        Py_ExitStatusException(status);
        return 1;
    }
}
