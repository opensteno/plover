from Cocoa import (
    NSApplicationActivateIgnoringOtherApps,
    NSRunningApplication,
    NSWorkspace,
)


def GetForegroundWindow():
    return NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier()


def SetForegroundWindow(pid):
    target_window = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
    target_window.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
