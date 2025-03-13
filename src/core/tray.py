import sys
import os
import threading
import time
import pystray
from PIL import Image, ImageDraw
from src.core.utils import RUNNING, logger
import tkinter as tk

def create_tray_icon(app):
    """
    Create a system tray icon for the application with a menu for restore and exit.
    
    Args:
        app: The BatteryMonitorApp instance.
    
    Returns:
        tuple: (tray object, thread object for running the tray)
    """
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__file__)
    icon_path = os.path.join(base_path, "..", "..", "icon.png")
    print(f"Looking for icon at: {icon_path}")  # Debug print to verify path
    try:
        if os.path.exists(icon_path) and os.path.getsize(icon_path) > 0:
            icon = Image.open(icon_path)
            icon = icon.resize((32, 32), Image.Resampling.LANCZOS)
            logger.info(f"Loaded tray icon from {icon_path}")
        else:
            logger.warning(f"Icon file {icon_path} not found or empty. Creating fallback icon.")
            icon = Image.new("RGBA", (32, 32), (245, 245, 245, 255))  # Gray background
            draw = ImageDraw.Draw(icon)
            draw.text((10, 10), "SMC", fill="black")  # Add "SMC" text as fallback
    except Exception as e:
        logger.error(f"Failed to load tray icon: {e}")
        icon = Image.new("RGBA", (32, 32), (245, 245, 245, 255))  # Gray background
        draw = ImageDraw.Draw(icon)
        draw.text((10, 10), "SMC", fill="black")  # Fallback with text

    menu = pystray.Menu(
        pystray.MenuItem("Restore", lambda: restore_app(app)),
        pystray.MenuItem("Exit", lambda: quit_app(app))
    )
    tray = pystray.Icon("SaveMyCell", icon, "Save My Cell", menu)
    def run_tray():
        tray.run()
    return tray, threading.Thread(target=run_tray, daemon=True)

def restore_app(app):
    """
    Schedule the restoration of the application window from the tray.
    
    Args:
        app: The BatteryMonitorApp instance.
    """
    logger.info(f"Attempting to restore app from tray. Current app.minimized_to_tray: {app.minimized_to_tray}")
    if not app.minimized_to_tray:
        logger.info("App is not minimized, skipping restore.")
        return
    # Schedule restoration in the Tkinter main thread to avoid threading issues
    logger.info("Scheduling restoration in Tkinter main thread...")
    app.root.after(0, lambda: _restore_app_internal(app))
    logger.info("Restore scheduled in main thread.")

def _restore_app_internal(app):
    try:
        logger.info("Starting restoration process...")
        if not app.root.winfo_exists():
            logger.error("Root window does not exist. Cannot restore.")
            app.minimized_to_tray = False
            return

        logger.info(f"Window state before deiconify: {app.root.state()}")
        app.root.deiconify()
        logger.info(f"Window state after deiconify: {app.root.state()}")

        # Reintroduce geometry and fade-in
        screen_width = app.root.winfo_screenwidth()
        screen_height = app.root.winfo_screenheight()
        x = (screen_width - 400) // 2
        y = (screen_height - 500) // 2
        logger.info(f"Setting geometry to 400x500+{x}+{y}")
        app.root.geometry(f"400x500+{x}+{y}")
        for alpha in range(0, 21):
            app.root.attributes('-alpha', alpha / 20)
            app.root.update()
            time.sleep(0.01)
        app.root.attributes('-alpha', 0.95)

        app.root.lift()
        app.root.focus_force()
        app.root.attributes('-topmost', True)
        app.root.update_idletasks()
        app.root.attributes('-topmost', False)
        app.root.update()

        logger.info("Checking for unplug prompt on restore...")
        app.check_unplug_prompt_on_restore()

        logger.info("Setting app.minimized_to_tray to False...")
        app.minimized_to_tray = False
        logger.info("App restored from tray successfully.")
    except Exception as e:
        logger.error(f"Failed to restore app from tray: {e}")
        app.minimized_to_tray = False


def quit_app(app):
    """
    Quit the application, stopping the tray and destroying the root window.
    
    Args:
        app: The BatteryMonitorApp instance.
    """
    logger.info("Quitting app...")
    RUNNING = False
    app.minimized_to_tray = False
    if app.tray:
        app.tray.stop()
    if app.root:
        app.root.destroy()
    logger.info("App quit successfully.")

def restore_app(app):
    logger.info(f"Attempting to restore app from tray. Current app.minimized_to_tray: {app.minimized_to_tray}")
    if not app.minimized_to_tray:
        logger.info("App is not minimized, skipping restore.")
        return
    if not app.root:
        logger.warning("Root window is None. Recreating root window...")
        app.root = tk.Tk()
        app.__init__(app.root)  # Reinitialize the app
    logger.info("Scheduling restoration in Tkinter main thread...")
    app.root.after(0, lambda: _restore_app_internal(app))
    logger.info("Restore scheduled in main thread.")