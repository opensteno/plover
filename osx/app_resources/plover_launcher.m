#import <Cocoa/Cocoa.h>
#include <Python.h>
#include <libgen.h>
#include <limits.h>
#include <unistd.h>

int main(int argc, char *argv[]) {
    @autoreleasepool {
        char python_home[PATH_MAX];
        char app_dir_c[PATH_MAX];
        char *app_dir = realpath(argv[0], NULL);
        app_dir = dirname(dirname(app_dir));
        strncpy(app_dir_c, app_dir, sizeof(app_dir_c) - 1);
        app_dir_c[sizeof(app_dir_c) - 1] = '\0';

        snprintf(python_home, sizeof(python_home), "%s/Frameworks/Python.framework/Versions/Current", app_dir_c);

        // Set PYTHONUSERBASE to enable user plugins
        char *home = getenv("HOME");
        if (home) {
            char python_user_base[PATH_MAX];
            snprintf(python_user_base, sizeof(python_user_base), "%s/Library/Application Support/plover/plugins/mac", home);
            setenv("PYTHONUSERBASE", python_user_base, 1);
        }

        wchar_t *python_home_w = Py_DecodeLocale(python_home, NULL);
        if (python_home_w == NULL) {
            fprintf(stderr, "Fatal error: unable to decode python_home\n");
            return 1;
        }
        Py_SetPythonHome(python_home_w);

        // Set program name
        wchar_t* program = Py_DecodeLocale(argv[0], NULL);
        Py_SetProgramName(program);
        
        Py_Initialize();

        // After this point, we are in a Python interpreter.

        // Prepend the site-packages to sys.path
        char site_packages[PATH_MAX];
        snprintf(site_packages, sizeof(site_packages), "%s/lib/python3.13/site-packages", python_home);
        wchar_t *site_packages_w = Py_DecodeLocale(site_packages, NULL);
        PyObject* sys_path = PySys_GetObject("path");
        PyList_Insert(sys_path, 0, PyUnicode_FromWideChar(site_packages_w, -1));
        PyMem_RawFree(site_packages_w);

        // Run the main script
        PyObject* pName = PyUnicode_FromString("plover.scripts.main");
        PyObject* pModule = PyImport_Import(pName);
        Py_DECREF(pName);

        if (pModule != NULL) {
            PyObject* pFunc = PyObject_GetAttrString(pModule, "main");
            if (pFunc && PyCallable_Check(pFunc)) {
                // Prepare arguments for main()
                wchar_t** py_argv = (wchar_t**)PyMem_Malloc(sizeof(wchar_t*) * argc);
                for (int i = 0; i < argc; i++) {
                    py_argv[i] = Py_DecodeLocale(argv[i], NULL);
                }
                PySys_SetArgv(argc, py_argv);

                // Call main()
                PyObject* pResult = PyObject_CallObject(pFunc, NULL);

                for (int i = 0; i < argc; i++) {
                    PyMem_RawFree(py_argv[i]);
                }
                PyMem_RawFree(py_argv);

                if (pResult == NULL) {
                    PyErr_Print();
                    fprintf(stderr, "Call to main failed.\n");
                    return 1;
                }
                Py_DECREF(pResult);

            } else {
                if (PyErr_Occurred()) PyErr_Print();
                fprintf(stderr, "Cannot find function \"main\"\n");
            }
            Py_XDECREF(pFunc);
            Py_DECREF(pModule);
        } else {
            PyErr_Print();
            fprintf(stderr, "Failed to load \"plover.scripts.main\"\n");
            return 1;
        }

        Py_Finalize();
        PyMem_RawFree(python_home_w);
        PyMem_RawFree(program);
        return 0;
    }
}
