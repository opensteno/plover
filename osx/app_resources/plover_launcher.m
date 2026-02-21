#import <Cocoa/Cocoa.h>
#include <libgen.h>
#include <limits.h>
#include <unistd.h>

int main(int argc, char *argv[]) {
    @autoreleasepool {
        char python_path[PATH_MAX];
        char *app_dir;

        // Get this app bundle directory.
        app_dir = realpath(argv[0], NULL);
        app_dir = dirname(dirname(app_dir));

        // Get path to the Python interpreter.
        snprintf(
            python_path, sizeof(python_path),
            "%s/Frameworks/Python.framework/Versions/Current/bin/python",
            app_dir);

        NSString *pythonExecutable = [NSString stringWithUTF8String:python_path];
        
        NSMutableArray *arguments = [NSMutableArray arrayWithObjects:@"-s", @"-m", @"plover.scripts.dist_main", nil];
        for (int i = 1; i < argc; i++) {
            [arguments addObject:[NSString stringWithUTF8String:argv[i]]];
        }

        [NSTask launchedTaskWithLaunchPath:pythonExecutable arguments:arguments];

        return NSApplicationMain(argc, (const char **)argv);
    }
}
