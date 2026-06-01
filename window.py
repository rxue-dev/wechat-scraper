"""macOS window management for WeChat Desktop."""

import subprocess
import time

import Quartz
from AppKit import NSWorkspace, NSRunningApplication


WECHAT_BUNDLE_ID = "com.tencent.xinWeChat"


def find_wechat_window():
    """Find the WeChat Desktop window and return its bounds (x, y, w, h).

    Returns None if WeChat is not running or window not found.
    """
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )

    for window in window_list:
        owner_name = window.get(Quartz.kCGWindowOwnerName, "")
        if owner_name == "WeChat" or owner_name == "微信":
            bounds = window.get(Quartz.kCGWindowBounds, {})
            if bounds.get("Width", 0) > 100 and bounds.get("Height", 0) > 100:
                return {
                    "x": int(bounds["X"]),
                    "y": int(bounds["Y"]),
                    "width": int(bounds["Width"]),
                    "height": int(bounds["Height"]),
                    "window_id": window.get(Quartz.kCGWindowNumber),
                    "owner_pid": window.get(Quartz.kCGWindowOwnerPID),
                }

    return None


def focus_wechat():
    """Bring WeChat to the foreground. Returns True if successful."""
    workspace = NSWorkspace.sharedWorkspace()
    running_apps = workspace.runningApplications()

    for app in running_apps:
        if app.bundleIdentifier() == WECHAT_BUNDLE_ID:
            app.activateWithOptions_(
                NSRunningApplication.NSApplicationActivateIgnoringOtherApps
            )
            time.sleep(0.5)
            return True

    return False


def get_chat_area_bounds(window_bounds):
    """Estimate the message area within the WeChat window.

    WeChat Desktop layout:
    - Left sidebar: ~70px (icons)
    - Chat list: ~250px
    - Right panel: remaining width (messages)
    - Top bar in right panel: ~60px (chat name, buttons)
    - Bottom input area: ~150px

    Returns (x, y, width, height) of the message display area.
    """
    sidebar_width = 320
    top_bar_height = 60
    bottom_bar_height = 150

    x = window_bounds["x"] + sidebar_width
    y = window_bounds["y"] + top_bar_height
    width = window_bounds["width"] - sidebar_width
    height = window_bounds["height"] - top_bar_height - bottom_bar_height

    if width < 100 or height < 100:
        x = window_bounds["x"]
        y = window_bounds["y"]
        width = window_bounds["width"]
        height = window_bounds["height"]

    return {"x": x, "y": y, "width": width, "height": height}


def click_chat_by_name(chat_name, window_bounds):
    """Click on a chat in the sidebar by name using AppleScript.

    This searches the WeChat chat list for the given name and clicks it.
    Returns True if the chat was found and clicked.
    """
    script = f'''
    tell application "System Events"
        tell process "WeChat"
            set frontmost to true
            delay 0.3
            -- Use CMD+F to search for the chat
            keystroke "f" using command down
            delay 0.5
            keystroke "{chat_name}"
            delay 1.0
            keystroke return
            delay 0.5
            -- Press Escape to close search
            key code 53
            delay 0.3
        end tell
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=10)
        time.sleep(1.0)
        return True
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False


def is_wechat_running():
    """Check if WeChat Desktop is currently running."""
    workspace = NSWorkspace.sharedWorkspace()
    for app in workspace.runningApplications():
        if app.bundleIdentifier() == WECHAT_BUNDLE_ID:
            return True
    return False
