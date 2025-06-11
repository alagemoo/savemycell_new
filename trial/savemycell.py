import psutil
import platform
import getpass
import socket
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont
import threading
import time
import queue
import logging
import os
import winreg
from PIL import Image, ImageTk
from typing import Optional, Dict, Any
import json
import sys
import pystray
import darkdetect # For light/dark mode detection

# Import constants
import constants

# Detect idle time on Windows
try:
    import win32api
    import win32con
except ImportError:
    win32api = None
    win32con = None

# Configure logging
if not os.path.exists(constants.APP_DATA_PATH):
    os.makedirs(constants.APP_DATA_PATH)
logging.basicConfig(filename=constants.LOG_FILE_PATH, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global flags and constants (some of these are now imported from constants.py)
RUNNING = True
MINIMIZED_TO_TRAY = False
UNPLUG_PROMPT_ACTIVE = False
PROMPT_QUEUE = queue.Queue()

# Utility Functions
def calculate_battery_time(battery: Optional[psutil.sensors_battery]) -> str:
    if not battery:
        return "Time: N/A"
    if not battery.power_plugged:
        if battery.secsleft == psutil.POWER_TIME_UNKNOWN:
            return "Time to Discharge: Estimating..."
        elif battery.secsleft == psutil.POWER_TIME_UNLIMITED:
            return "Time to Discharge: Unlimited"
        else:
            hours = battery.secsleft // 3600
            minutes = (battery.secsleft % 3600) // 60
            return f"Time to Discharge: {hours}h {minutes}m"
    if battery.power_plugged:
        # psutil doesn't directly provide time to full, so we estimate or show status
        if battery.percent >= 99: # Consider 99% as full for practical purposes
             return "Time to Full Charge: Fully Charged"
        else:
            # This is a rough estimation, actual charging rate varies.
            # You might need a more sophisticated algorithm if you want accuracy here.
            # For now, it shows "Charging..." or "Time to Full Charge: Estimating..."
            return "Time to Full Charge: Charging..."


def get_system_details() -> Dict[str, str]:
    # Cache system details that don't change frequently
    if not hasattr(get_system_details, "cached_details"):
        get_system_details.cached_details = {
            "System Name": socket.gethostname(),
            "Laptop Model Number": platform.machine(), # This is actually architecture, not model
            "System Username": getpass.getuser(),
            "Operating System": f"{platform.system()} {platform.release()} ({platform.version()})",
            "Processor": platform.processor(),
            "Python Version": platform.python_version()
        }

    # Update battery-related details dynamically
    battery = psutil.sensors_battery()
    if battery:
        get_system_details.cached_details.update({
            "Battery Percentage": f"{battery.percent}%",
            "Battery Status": "Charging" if battery.power_plugged else "Discharging",
            "Power Plugged": "Yes" if battery.power_plugged else "No",
            # "Battery Cell Type" is usually not available via psutil
            "Battery Health": "N/A (requires specialized tools)",
            "Time to Full Charge": calculate_battery_time(battery) if battery.power_plugged else "N/A",
            "Time to Complete Discharge": calculate_battery_time(battery) if not battery.power_plugged else "N/A"
        })
    else:
        get_system_details.cached_details.update({
            "Battery Percentage": "N/A",
            "Battery Status": "N/A",
            "Power Plugged": "N/A",
            "Battery Health": "N/A",
            "Time to Full Charge": "N/A",
            "Time to Complete Discharge": "N/A"
        })
    return get_system_details.cached_details

def set_auto_start(enabled: bool) -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, constants.AUTO_START_REG_KEY, 0, winreg.KEY_ALL_ACCESS)
        app_name = constants.AUTO_START_APP_NAME
        if enabled:
            if getattr(sys, 'frozen', False):
                # Path for bundled executable
                executable_path = sys.executable
            else:
                # Path for script when run directly
                python_exe = sys.executable
                script_path = os.path.abspath(__file__)
                executable_path = f'"{python_exe}" "{script_path}"'

            logger.info(f"Setting auto-start with value: {executable_path}")
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, executable_path)
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                logger.info(f"Auto-start entry for {app_name} not found, no deletion needed.")
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.error(f"Failed to set auto-start: {str(e)}")
        messagebox.showerror("Auto-Start Error", f"Failed to modify auto-start settings.\nReason: {e}\n\n"
                                                  "Please ensure the application is run as Administrator if this issue persists.")
        return False

def is_auto_start_enabled() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, constants.AUTO_START_REG_KEY, 0, winreg.KEY_READ)
        app_name = constants.AUTO_START_APP_NAME
        try:
            value, _ = winreg.QueryValueEx(key, app_name)
            if getattr(sys, 'frozen', False):
                current_path = sys.executable
            else:
                current_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
            
            # Remove quotes for comparison if present in registry value
            value = value.strip('"') 
            current_path = current_path.strip('"')

            is_enabled = value == current_path
            logger.info(f"Auto-start check: Current: '{current_path}', Registry: '{value}', Enabled: {is_enabled}")
            winreg.CloseKey(key)
            return is_enabled
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception as e:
        logger.error(f"Failed to check auto-start: {e}")
        return False

def get_idle_time() -> float:
    if win32api is None or win32con is None:
        logger.warning("pywin32 not installed. Idle time detection disabled.")
        return 0
    try:
        last_input = win32api.GetLastInputInfo()
        current_time = win32api.GetTickCount()
        idle_time_ms = current_time - last_input
        return idle_time_ms / 1000.0
    except Exception as e:
        logger.error(f"Failed to get idle time: {e}")
        return 0

# Monitoring Logic
class BatteryMonitor:
    def __init__(self, app):
        self.app = app
        self.last_battery = None
        self.last_unplug_prompt_time = 0
        self.last_update = 0
        self.lock = threading.Lock()
        self.last_percent = None
        self.last_plugged = None

    def run(self):
        global RUNNING, UNPLUG_PROMPT_ACTIVE, MINIMIZED_TO_TRAY
        while RUNNING:
            try:
                battery = psutil.sensors_battery()
                if not battery:
                    logger.warning("Battery status unavailable.")
                    time.sleep(10)
                    continue

                with self.lock:
                    current_time = time.time()
                    
                    # Determine sleep interval based on app state and battery
                    sleep_interval = constants.DEFAULT_REFRESH_INTERVAL_SECONDS # Default
                    if MINIMIZED_TO_TRAY and (not battery.power_plugged or battery.percent < self.app.unplug_threshold):
                        sleep_interval = constants.TRAY_MINIMIZED_REFRESH_INTERVAL_SECONDS
                    elif self.app.power_saving_mode:
                        sleep_interval = constants.POWER_SAVING_REFRESH_INTERVAL_SECONDS
                    elif battery.power_plugged and battery.percent >= self.app.unplug_threshold:
                        sleep_interval = 5 # Faster check if plugged in and above threshold

                    # Prompt logic
                    if battery.percent >= self.app.unplug_threshold and battery.power_plugged:
                        if not UNPLUG_PROMPT_ACTIVE:
                            # Trigger prompt if charger was just plugged in above threshold,
                            # or if enough time has passed since last prompt.
                            if (self.last_battery and not self.last_battery.power_plugged and battery.power_plugged) or \
                               (current_time - self.last_unplug_prompt_time >= 300 or self.last_unplug_prompt_time == 0):
                                logger.info("Triggering unplug prompt.")
                                PROMPT_QUEUE.put(True)
                                self.last_unplug_prompt_time = current_time
                    elif self.last_battery and not battery.power_plugged and self.last_battery.power_plugged:
                        # Reset prompt cooldown if charger unplugged and battery is below threshold
                        if battery.percent < self.app.unplug_threshold:
                            self.last_unplug_prompt_time = 0
                            logger.info("Charger unplugged and below threshold, resetting prompt cooldown.")

                    self.last_battery = battery

                    # Update UI on main screen if not minimized and significant change
                    if self.app.root.winfo_exists() and not MINIMIZED_TO_TRAY and self.app.current_screen == "main":
                        if self.last_percent is None or self.last_plugged is None or \
                           abs(battery.percent - self.last_percent) >= 1 or battery.power_plugged != self.last_plugged:
                            self.app.root.after(0, lambda: self.app.update_main_screen_ui(battery.percent, battery.power_plugged))
                            self.last_percent = battery.percent
                            self.last_plugged = battery.power_plugged
                    
                    # Update system stats periodically (e.g., for diagnostics screen)
                    if current_time - self.last_update >= 300: # Every 5 minutes
                        # self.app.update_system_stats() # This function is currently a placeholder
                        self.last_update = current_time
                
                time.sleep(sleep_interval)
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(10) # Wait longer on error

# System Tray
def create_tray_icon(app):
    global MINIMIZED_TO_TRAY
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__file__)
    icon_path = os.path.join(base_path, constants.ICON_FILE_NAME)
    try:
        if os.path.exists(icon_path) and os.path.getsize(icon_path) > 0:
            icon = Image.open(icon_path)
            # Ensure icon is suitable for tray (typically small, e.g., 64x64 or 32x32)
            icon = icon.resize((64, 64), Image.Resampling.LANCZOS)
            logger.info(f"Loaded tray icon from {icon_path}")
        else:
            logger.warning(f"Icon file {icon_path} not found or empty. Using fallback.")
            # Create a simple fallback icon if file is missing or invalid
            icon = Image.new("RGBA", (64, 64), (245, 245, 245, 255))
    except Exception as e:
        logger.error(f"Failed to load tray icon: {e}")
        icon = Image.new("RGBA", (64, 64), (245, 245, 245, 255)) # Fallback on error as well

    menu = pystray.Menu(
        pystray.MenuItem("Restore", lambda: restore_app(app)),
        pystray.MenuItem("Exit", lambda: quit_app(app))
    )
    tray = pystray.Icon("SaveMyCell", icon, "Save My Cell", menu)
    
    def run_tray():
        tray.run()
    
    return tray, threading.Thread(target=run_tray, daemon=True)

def restore_app(app):
    global MINIMIZED_TO_TRAY
    logger.info("Attempting to restore app from tray...")
    if not MINIMIZED_TO_TRAY:
        logger.info("App is not minimized, skipping restore.")
        return
    # Schedule the actual UI operation on the main Tkinter thread
    app.root.after(0, lambda: app.show_screen("main"))
    logger.info("Restore scheduled in main thread.")

def quit_app(app):
    global RUNNING, MINIMIZED_TO_TRAY
    logger.info("Quitting app...")
    RUNNING = False
    MINIMIZED_TO_TRAY = False
    if app.tray:
        app.tray.stop()
    if app.root:
        app.root.destroy()
    logger.info("App quit successfully.")

# UI Class
class BatteryMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Save My Cell")
        self.root.geometry(f"{constants.WINDOW_WIDTH}x{constants.WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.style = ttk.Style()
        self.style.theme_use('clam') # 'clam' provides a neutral base for customization

        # Default settings - will be overwritten by loaded settings
        self.unplug_threshold = constants.DEFAULT_UNPLUG_THRESHOLD
        self.refresh_interval = constants.DEFAULT_REFRESH_INTERVAL_SECONDS
        self.power_saving_mode = False
        self.display_name = getpass.getuser() # Default display name
        self.custom_logo_path = ""
        self.selected_theme_mode = "System" # "System", "Light", "Dark"

        self.load_settings_from_file() # Load settings first to get preferred theme

        self.apply_theme_colors() # Apply colors based on loaded settings/system preference
        self.configure_styles() # Configure styles with current colors

        # Apply acrylic effect and rounded corners (Windows 11 style)
        # Note: True acrylic effect is complex and requires C++ integration or
        # using libraries like win32mica. This is a basic simulation.
        self.root.attributes('-alpha', 0.95) # Slight transparency
        # Set a transparent color that matches the background for a "frameless" feel
        self.root.wm_attributes('-transparentcolor', self.current_bg) 


        # Main layout: Left sidebar, Right content area
        self.root.columnconfigure(0, weight=0) # Sidebar column
        self.root.columnconfigure(1, weight=1) # Content column
        self.root.rowconfigure(0, weight=1) # Single row

        # Sidebar Frame
        self.sidebar_frame = ttk.Frame(self.root, style="Sidebar.TFrame")
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self._build_sidebar()

        # Content Frame
        self.content_frame = ttk.Frame(self.root, style="Content.TFrame")
        self.content_frame.grid(row=0, column=1, sticky="nsew")

        # System Tray setup
        self.tray, self.tray_thread = create_tray_icon(self)
        self.tray_thread.start()

        # Battery Monitoring Thread
        self.monitor = BatteryMonitor(self)
        self.monitor_thread = threading.Thread(target=self.monitor.run, daemon=True)
        self.monitor_thread.start()

        self.current_screen = "main" # Keep track of the active screen
        self.show_screen("main") # Display initial main screen

        self.check_prompt_queue() # Start checking for unplug prompts

        # Monitor theme changes for "System" mode
        self.root.after(1000, self.check_system_theme_change)

    def apply_theme_colors(self):
        """Determine and apply colors based on selected_theme_mode and system detection."""
        if self.selected_theme_mode == "Dark":
            self.is_dark_mode = True
        elif self.selected_theme_mode == "Light":
            self.is_dark_mode = False
        else: # "System" mode
            self.is_dark_mode = darkdetect.isDark()

        if self.is_dark_mode:
            self.current_bg = constants.DEFAULT_DARK_MODE_BG
            self.current_text_color = constants.DEFAULT_DARK_MODE_TEXT
            self.current_secondary_bg = constants.DEFAULT_DARK_MODE_SECONDARY_BG
        else:
            self.current_bg = constants.DEFAULT_LIGHT_MODE_BG
            self.current_text_color = constants.DEFAULT_LIGHT_MODE_TEXT
            self.current_secondary_bg = constants.DEFAULT_LIGHT_MODE_SECONDARY_BG
        
        self.root.configure(bg=self.current_bg) # Apply to root window
        self.configure_styles() # Reconfigure styles with new colors

    def check_system_theme_change(self):
        """Check for system theme changes and update UI if in 'System' mode."""
        if self.selected_theme_mode == "System":
            new_theme = darkdetect.isDark()
            if new_theme != self.is_dark_mode:
                logger.info(f"System theme changed to {'Dark' if new_theme else 'Light'}. Updating UI.")
                self.is_dark_mode = new_theme
                self.apply_theme_colors()
                # Re-render current screen to apply new colors
                self.show_screen(self.current_screen) 
        self.root.after(1000, self.check_system_theme_change)

    def configure_styles(self):
        """Configure Tkinter styles dynamically based on colors and font."""
        self.style.configure("Main.TFrame", background=self.current_bg)
        self.style.configure("Sidebar.TFrame", background=self.current_secondary_bg)
        self.style.configure("Content.TFrame", background=self.current_bg)
        # New style for placeholder bars that need background color
        self.style.configure("Placeholder.TFrame", background=self.current_secondary_bg)


        # Labels
        self.style.configure("Title.TLabel",
                             font=(constants.DEFAULT_FONT_TYPE, 14, "bold"),
                             foreground=self.current_text_color,
                             background=self.current_bg)
        self.style.configure("Heading.TLabel", # For section headings like "General", "Customization"
                             font=(constants.DEFAULT_FONT_TYPE, 12, "bold"),
                             foreground=self.current_text_color,
                             background=self.current_bg)
        self.style.configure("Body.TLabel",
                             font=(constants.DEFAULT_FONT_TYPE, 10),
                             foreground=self.current_text_color,
                             background=self.current_bg)
        self.style.configure("Small.TLabel",
                             font=(constants.DEFAULT_FONT_TYPE, 9),
                             foreground="#666666" if not self.is_dark_mode else "#AAAAAA",
                             background=self.current_bg)
        self.style.configure("BatteryPercent.TLabel",
                             font=(constants.DEFAULT_FONT_TYPE, 80, "bold"),
                             foreground=self.current_text_color,
                             background=self.current_bg,
                             anchor="center")
        self.style.configure("BatteryStatus.TLabel",
                             font=(constants.DEFAULT_FONT_TYPE, 14),
                             foreground="#666666" if not self.is_dark_mode else "#AAAAAA",
                             background=self.current_bg,
                             anchor="center")
        self.style.configure("BatteryTime.TLabel",
                             font=(constants.DEFAULT_FONT_TYPE, 14),
                             foreground=self.current_text_color,
                             background=self.current_bg,
                             anchor="center")
        self.style.configure("Prompt.TLabel",
                             font=(constants.DEFAULT_FONT_TYPE, 20, "bold"),
                             foreground="#D83B01", # Fixed error color
                             background=self.current_bg)
        self.style.configure("Info.TLabel",
                             font=(constants.DEFAULT_FONT_TYPE, 11),
                             foreground="#666666" if not self.is_dark_mode else "#AAAAAA",
                             background=self.current_bg,
                             wraplength=600)
        self.style.configure("Countdown.TLabel",
                             font=(constants.DEFAULT_FONT_TYPE, 14, "bold"),
                             foreground=self.accent_color,
                             background=self.current_bg)

        # Buttons
        self.style.configure("Sidebar.TButton",
                             font=(constants.DEFAULT_FONT_TYPE, 11),
                             background=self.current_secondary_bg,
                             foreground=self.current_text_color,
                             borderwidth=0,
                             relief="flat",
                             padding=[10, 15]) # Padding for vertical alignment
        self.style.map("Sidebar.TButton",
                       background=[("active", self.accent_color), ("selected", self.accent_color)],
                       foreground=[("active", "#FFFFFF"), ("selected", "#FFFFFF")])
        
        self.style.configure("Accent.TButton", # Primary action buttons
                             font=(constants.DEFAULT_FONT_TYPE, 11, "bold"),
                             padding=[15, 10],
                             background=self.accent_color,
                             foreground="#FFFFFF",
                             borderwidth=0,
                             relief="flat")
        self.style.map("Accent.TButton",
                       background=[("active", "#005BA1")])

        self.style.configure("Back.TButton",
                             font=(constants.DEFAULT_FONT_TYPE, 10),
                             padding=[10, 8],
                             background=self.current_bg, # Match content frame bg
                             foreground=self.current_text_color,
                             borderwidth=0,
                             relief="flat")
        self.style.map("Back.TButton",
                       background=[("active", self.current_secondary_bg)])
        
        # Entry widgets
        self.style.configure("TEntry",
                             fieldbackground=self.current_secondary_bg,
                             foreground=self.current_text_color,
                             insertcolor=self.current_text_color,
                             borderwidth=0,
                             relief="flat",
                             padding=5)
        self.style.map("TEntry",
                       fieldbackground=[('focus', self.current_secondary_bg)],
                       foreground=[('focus', self.current_text_color)])

        # Scale widget
        self.style.configure("Horizontal.TScale",
                             background=self.current_bg,
                             foreground=self.accent_color,
                             troughcolor=self.current_secondary_bg)
        self.style.map("Horizontal.TScale",
                       background=[('active', self.accent_color)])

        # Radiobuttons
        self.style.configure("TRadiobutton",
                             background=self.current_bg,
                             foreground=self.current_text_color,
                             font=(constants.DEFAULT_FONT_TYPE, 10))
        self.style.map("TRadiobutton",
                       background=[('active', self.current_bg)]) # Prevent changing background on hover

        # Text widget for info displays
        self.style.configure("TText",
                             background=self.current_secondary_bg,
                             foreground=self.current_text_color,
                             borderwidth=0,
                             relief="flat",
                             padding=10)

    def save_settings_to_file(self):
        """Save settings, including UI customizations, to a JSON file."""
        try:
            settings = {
                "unplug_threshold": self.unplug_threshold,
                "refresh_interval": self.refresh_interval,
                "power_saving_mode": self.power_saving_mode,
                "display_name": self.display_name,
                "custom_logo_path": self.custom_logo_path,
                "selected_theme_mode": self.selected_theme_mode # "System", "Light", "Dark"
            }
            with open(constants.SETTINGS_FILE_PATH, "w") as f:
                json.dump(settings, f, indent=4)
            logger.info(f"Settings saved to {constants.SETTINGS_FILE_PATH}: {settings}")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            messagebox.showerror("Error", "Failed to save settings. Check logs for details.")

    def load_settings_from_file(self):
        """Load settings, including UI customizations, from a JSON file."""
        try:
            if not os.path.exists(constants.SETTINGS_FILE_PATH):
                logger.warning(f"Settings file not found at {constants.SETTINGS_FILE_PATH}. Using defaults.")
                # If no settings file, save defaults to create it
                self.save_settings_to_file() 
                return
            
            with open(constants.SETTINGS_FILE_PATH, "r") as f:
                settings = json.load(f)
                self.unplug_threshold = settings.get("unplug_threshold", constants.DEFAULT_UNPLUG_THRESHOLD)
                self.refresh_interval = settings.get("refresh_interval", constants.DEFAULT_REFRESH_INTERVAL_SECONDS)
                self.power_saving_mode = settings.get("power_saving_mode", False)
                self.display_name = settings.get("display_name", getpass.getuser())
                self.custom_logo_path = settings.get("custom_logo_path", "")
                self.selected_theme_mode = settings.get("selected_theme_mode", "System")
                logger.info(f"Settings loaded from {constants.SETTINGS_FILE_PATH}: {settings}")
        except FileNotFoundError:
            logger.error(f"Settings file not found at {constants.SETTINGS_FILE_PATH}. Using defaults.")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse settings file {constants.SETTINGS_FILE_PATH}: {e}. Using defaults.")
            messagebox.showerror("Error", f"Corrupt settings file detected. Using defaults. Details: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading settings from {constants.SETTINGS_FILE_PATH}: {e}. Using defaults.")
            messagebox.showerror("Error", f"Failed to load settings. Using defaults. Details: {e}")
        
        # Ensure auto-start is set on startup if it's not already
        if not is_auto_start_enabled():
            logger.info("Auto-start not enabled, attempting to enable it.")
            set_auto_start(True)

    def _clear_content_frame(self):
        """Destroys all widgets in the content frame."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _build_sidebar(self):
        """Builds the persistent left sidebar navigation."""
        self.sidebar_frame.columnconfigure(0, weight=1) # Center items horizontally
        self.sidebar_frame.rowconfigure(0, weight=0) # Profile image
        self.sidebar_frame.rowconfigure(1, weight=0) # Username
        self.sidebar_frame.rowconfigure(2, weight=1) # Spacer for nav buttons
        self.sidebar_frame.rowconfigure(3, weight=0) # Settings button
        self.sidebar_frame.rowconfigure(4, weight=0) # Bottom padding

        # Profile Image Placeholder
        profile_img_label = ttk.Label(self.sidebar_frame, background=self.current_secondary_bg)
        profile_img_label.grid(row=0, column=0, pady=(20, 5), sticky="n")
        # You would load an actual image here, e.g., default user icon or custom
        # For now, a grey circle placeholder
        self._create_circular_placeholder(profile_img_label, 60, "gray") # 60px diameter circle
        
        # Display Name
        self.display_name_label = ttk.Label(
            self.sidebar_frame,
            text=self.display_name,
            font=(constants.DEFAULT_FONT_TYPE, 10, "bold"),
            foreground=self.current_text_color,
            background=self.current_secondary_bg
        )
        self.display_name_label.grid(row=1, column=0, pady=(0, 20), sticky="n")

        # Navigation Buttons
        nav_button_frame = ttk.Frame(self.sidebar_frame, style="Sidebar.TFrame")
        nav_button_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 20))
        nav_button_frame.columnconfigure(0, weight=1)

        self.main_nav_button = ttk.Button(nav_button_frame, text="Home", command=lambda: self.show_screen("main"), style="Sidebar.TButton")
        self.main_nav_button.grid(row=0, column=0, pady=(0, 5), sticky="ew")

        self.diagnostics_nav_button = ttk.Button(nav_button_frame, text="System Diagnostics", command=lambda: self.show_screen("diagnostics"), style="Sidebar.TButton")
        self.diagnostics_nav_button.grid(row=1, column=0, pady=(0, 5), sticky="ew")

        self.about_nav_button = ttk.Button(nav_button_frame, text="About Save My Cell", command=lambda: self.show_screen("about"), style="Sidebar.TButton")
        self.about_nav_button.grid(row=2, column=0, pady=(0, 5), sticky="ew")

        # Settings Gear Icon/Button at bottom
        self.settings_icon_label = ttk.Label(self.sidebar_frame, background=self.current_secondary_bg)
        self.settings_icon_label.grid(row=3, column=0, pady=(10, 10), sticky="s") # Use sticky 's' to push to bottom
        self._create_settings_gear_icon(self.settings_icon_label, 30)
        self.settings_icon_label.bind("<Button-1>", lambda e: self.show_screen("settings")) # Make it clickable
        self.settings_icon_label.bind("<Enter>", lambda e: self.settings_icon_label.config(cursor="hand2"))
        self.settings_icon_label.bind("<Leave>", lambda e: self.settings_icon_label.config(cursor=""))

    def _create_circular_placeholder(self, parent_label, size, color):
        """Creates a circular image placeholder for the profile picture."""
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0)) # Transparent background
        # Create a circle in the center
        for x in range(size):
            for y in range(size):
                if (x - size/2)**2 + (y - size/2)**2 < (size/2 - 2)**2: # -2 for slight border
                    # FIX: Changed (1,) to (1,1) in Image.new to resolve ValueError
                    image.putpixel((x, y), Image.new("RGB", (1, 1), color).getpixel((0,0)) + (255,)) # Fill with color, full opacity
        
        # Optional: Add a subtle border
        for x in range(size):
            for y in range(size):
                dist_sq = (x - size/2)**2 + (y - size/2)**2
                if (size/2 - 3)**2 < dist_sq < (size/2)**2:
                     current_color = image.getpixel((x,y))
                     if current_color[3] > 0: # Only if it's not transparent
                        image.putpixel((x,y), (100, 100, 100, 255) if self.is_dark_mode else (200,200,200,255)) # Darker border
        
        photo = ImageTk.PhotoImage(image)
        parent_label.config(image=photo)
        parent_label.image = photo # Keep reference

    def _create_settings_gear_icon(self, parent_label, size):
        """Creates a simple gear icon placeholder using drawing or a basic image."""
        # A simple way is to use a unicode character or a font icon library.
        # For true Fluent Design, you'd use Segoe Fluent Icons font or load an SVG.
        # As a placeholder, I'll use a text label with a large font size.
        parent_label.config(text="\u2699", # Unicode gear symbol
                            font=("Segoe UI Symbol", size),
                            foreground=self.current_text_color,
                            background=self.current_secondary_bg,
                            width=1) # Keep width minimal to center
        # If you have an icon.png, you could load it here and display.
        # Example using PIL if you have a gear image:
        # try:
        #     gear_image = Image.open(os.path.join(base_path, "gear_icon.png")).resize((size, size), Image.Resampling.LANCZOS)
        #     gear_photo = ImageTk.PhotoImage(gear_image)
        #     parent_label.config(image=gear_photo)
        #     parent_label.image = gear_photo
        # except Exception as e:
        #     logger.warning(f"Could not load gear icon: {e}")


    def show_screen(self, screen_name: str):
        """Manages which screen is shown in the content frame."""
        logger.info(f"Switching to screen: {screen_name}")
        self._clear_content_frame()
        self.current_screen = screen_name

        # Update sidebar button styling to indicate active screen
        for btn in [self.main_nav_button, self.diagnostics_nav_button, self.about_nav_button]:
            btn.state(['!selected'])
        if screen_name == "main":
            self.main_nav_button.state(['selected'])
        elif screen_name == "diagnostics":
            self.diagnostics_nav_button.state(['selected'])
        elif screen_name == "about":
            self.about_nav_button.state(['selected'])


        if screen_name == "main":
            self._build_main_screen()
        elif screen_name == "diagnostics":
            self._build_diagnostics_screen()
        elif screen_name == "about":
            self._build_about_screen()
        elif screen_name == "settings":
            self._build_settings_screen()
        else:
            logger.error(f"Unknown screen name: {screen_name}")
            self._build_main_screen() # Fallback

        # Ensure root transparency is updated if background changed
        self.root.wm_attributes('-transparentcolor', self.current_bg) 

    def _add_back_button_and_title(self, frame, title_text):
        """Helper to add back button and title for sub-screens."""
        top_bar = ttk.Frame(frame, style="Main.TFrame")
        top_bar.pack(fill="x", pady=(10, 10), padx=10)
        top_bar.columnconfigure(0, weight=0) # Back button
        top_bar.columnconfigure(1, weight=1) # Title

        # Back button (Arrow icon)
        back_button = ttk.Button(top_bar, text="\u2190", command=lambda: self.show_screen("main"), style="Back.TButton")
        back_button.grid(row=0, column=0, padx=(0, 10), sticky="w")

        title_label = ttk.Label(top_bar, text=title_text, style="Title.TLabel")
        title_label.grid(row=0, column=1, sticky="w")
        return top_bar # Return the top bar frame for further packing if needed

    def _build_main_screen(self):
        """Builds the main battery monitoring screen in the content frame."""
        logger.info("Building main screen (content frame)...")
        
        # Center elements vertically and horizontally
        self.content_frame.columnconfigure(0, weight=1) 
        self.content_frame.rowconfigure(0, weight=1) # Pushes battery label down
        self.content_frame.rowconfigure(1, weight=0) # Battery percentage
        self.content_frame.rowconfigure(2, weight=0) # Status
        self.content_frame.rowconfigure(3, weight=0) # Time
        self.content_frame.rowconfigure(4, weight=1) # Pushes content up

        battery = psutil.sensors_battery()
        initial_percent = f"{battery.percent}%" if battery else "N/A"
        self.battery_label = ttk.Label(self.content_frame, text=initial_percent, style="BatteryPercent.TLabel")
        self.battery_label.grid(row=1, column=0, pady=(0, 5), sticky="nsew")

        status = "Charging" if (battery and battery.power_plugged) else "Discharging"
        self.battery_status = ttk.Label(self.content_frame, text=status, style="BatteryStatus.TLabel")
        self.battery_status.grid(row=2, column=0, pady=(0, 5), sticky="ew")

        self.battery_time = ttk.Label(self.content_frame, text=calculate_battery_time(battery), style="BatteryTime.TLabel")
        self.battery_time.grid(row=3, column=0, pady=(0, 0), sticky="ew") # No bottom padding to stay closer to status

        # Add placeholder bars for remaining content from screenshot
        # Placeholder for small bar below percentage (e.g., charge level indicator)
        placeholder_bar1 = ttk.Frame(self.content_frame, height=5, style="Placeholder.TFrame") # Use style
        placeholder_bar1.grid(row=3, column=0, pady=(20, 5), padx=80, sticky="ew")
        
        # Placeholder for lines of text below
        placeholder_text_lines_frame = ttk.Frame(self.content_frame, style="Main.TFrame")
        placeholder_text_lines_frame.grid(row=4, column=0, pady=(5, 0), padx=80, sticky="new")
        for i in range(3):
            bar_width = 150 if i == 0 else (120 if i == 1 else 100) # Vary length
            placeholder_line = ttk.Frame(placeholder_text_lines_frame, height=5, width=bar_width, style="Placeholder.TFrame") # Use style
            placeholder_line.pack(pady=3, anchor="w", fill="x", expand=False)
        
        self.update_main_screen_ui(battery.percent if battery else 0, battery.power_plugged if battery else False)
        logger.info("Main screen built successfully.")

    def update_main_screen_ui(self, percent: float, plugged: bool):
        """Update UI elements on the main battery screen."""
        if self.battery_label.winfo_exists(): # Check if widget exists before updating
            self.battery_label.config(text=f"{percent:.0f}%")
            self.battery_status.config(text="Charging" if plugged else "Discharging")
            self.battery_time.config(text=calculate_battery_time(psutil.sensors_battery()))

    def _build_diagnostics_screen(self):
        """Builds the System Diagnostics screen."""
        logger.info("Building System Diagnostics screen.")
        self._add_back_button_and_title(self.content_frame, "System Diagnostics")

        details = get_system_details()
        details_text = "\n".join(f"{key}: {value}" for key, value in details.items())
        
        self.diagnostics_text = tk.Text(self.content_frame, wrap="word", font=(constants.DEFAULT_FONT_TYPE, 10), 
                                       bg=self.current_secondary_bg, fg=self.current_text_color, 
                                       relief="flat", borderwidth=0, padx=15, pady=15)
        self.diagnostics_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.diagnostics_text.insert(tk.END, details_text)
        self.diagnostics_text.config(state="disabled") # Make it read-only
        logger.info("System Diagnostics screen displayed.")

    def _build_about_screen(self):
        """Builds the About Save My Cell screen."""
        logger.info("Building About Save My Cell screen.")
        self._add_back_button_and_title(self.content_frame, "About Save My Cell")

        version_text = "Pro Version" if constants.VERSION == "PRO" else "Free Version"
        about_text = f"Save My Cell\n\nDeveloped by: Gideon Aniechi\nVersion: MVP ({version_text})\nPowered by ValionTech\n\n" \
                     f"This application helps you prolong your laptop's battery life by reminding you to unplug " \
                     f"your charger when the battery reaches a customizable threshold. Keep your battery healthy " \
                     f"and reduce energy consumption!"
        
        self.about_text = tk.Text(self.content_frame, wrap="word", font=(constants.DEFAULT_FONT_TYPE, 10), 
                                  bg=self.current_secondary_bg, fg=self.current_text_color, 
                                  relief="flat", borderwidth=0, padx=15, pady=15)
        self.about_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.about_text.insert(tk.END, about_text)
        self.about_text.config(state="disabled") # Make it read-only
        logger.info("About Save My Cell screen displayed.")

    def _build_settings_screen(self):
        """Builds the Settings screen with UI customization options."""
        logger.info("Building settings screen.")
        self._add_back_button_and_title(self.content_frame, "Settings")

        # Scrollable area for settings
        canvas = tk.Canvas(self.content_frame, bg=self.current_bg, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_frame, orient="vertical", command=canvas.yview)
        self.settings_scrollable_frame = ttk.Frame(canvas, style="Main.TFrame")

        self.settings_scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.settings_scrollable_frame, anchor="nw", width=self.content_frame.winfo_width())
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=5)
        scrollbar.pack(side="right", fill="y", pady=5)

        # Ensure canvas width updates with content_frame
        self.content_frame.bind("<Configure>", lambda e: canvas.itemconfig(canvas.find_withtag("all")[0], width=e.width))


        # --- General Section ---
        ttk.Label(self.settings_scrollable_frame, text="General", style="Heading.TLabel").pack(pady=(15, 5), anchor="w", padx=10)

        # Profile image upload (placeholder)
        profile_img_frame = ttk.Frame(self.settings_scrollable_frame, style="Main.TFrame")
        profile_img_frame.pack(fill="x", pady=5, padx=10)
        
        current_logo_path = self.custom_logo_path if self.custom_logo_path and os.path.exists(self.custom_logo_path) else None
        
        self.user_logo_label = ttk.Label(profile_img_frame, background=self.current_secondary_bg)
        self.user_logo_label.pack(side="left", padx=5)
        if current_logo_path:
            try:
                logo_img = Image.open(current_logo_path)
                logo_img = logo_img.resize((60, 60), Image.Resampling.LANCZOS)
                logo_photo = ImageTk.PhotoImage(logo_img)
                self.user_logo_label.config(image=logo_photo)
                self.user_logo_label.image = logo_photo
            except Exception as e:
                logger.error(f"Error loading custom logo for settings: {e}")
                self._create_circular_placeholder(self.user_logo_label, 60, "gray")
        else:
            self._create_circular_placeholder(self.user_logo_label, 60, "gray")

        upload_button_frame = ttk.Frame(profile_img_frame, style="Main.TFrame")
        upload_button_frame.pack(side="left", padx=10)
        ttk.Label(upload_button_frame, text="Upload Profile Picture", style="Body.TLabel").pack(anchor="w")
        ttk.Button(upload_button_frame, text="Upload", command=self._browse_custom_logo, style="Accent.TButton").pack(anchor="w", pady=(5,0))

        # Display Name
        display_name_frame = ttk.Frame(self.settings_scrollable_frame, style="Main.TFrame")
        display_name_frame.pack(fill="x", pady=5, padx=10)
        ttk.Label(display_name_frame, text="Display name", style="Body.TLabel").pack(anchor="w")
        self.display_name_entry = ttk.Entry(display_name_frame, font=(constants.DEFAULT_FONT_TYPE, 10))
        self.display_name_entry.insert(0, self.display_name)
        self.display_name_entry.pack(fill="x", pady=(2, 0))

        # Unplug Threshold
        threshold_frame = ttk.Frame(self.settings_scrollable_frame, style="Main.TFrame")
        threshold_frame.pack(fill="x", pady=5, padx=10)
        ttk.Label(threshold_frame, text="Unplug Threshold", style="Body.TLabel").pack(anchor="w")
        self.unplug_threshold_label = ttk.Label(threshold_frame, text=f"{self.unplug_threshold}%", style="Body.TLabel", foreground=self.accent_color)
        self.unplug_threshold_label.pack(anchor="e")
        self.unplug_threshold_slider = ttk.Scale(
            threshold_frame,
            from_=0, to=100,
            orient="horizontal",
            command=self._update_threshold_label,
            style="Horizontal.TScale"
        )
        self.unplug_threshold_slider.set(self.unplug_threshold)
        self.unplug_threshold_slider.pack(fill="x", pady=(0, 5))
        
        # Min/Max labels for slider
        slider_labels_frame = ttk.Frame(threshold_frame, style="Main.TFrame")
        slider_labels_frame.pack(fill="x")
        ttk.Label(slider_labels_frame, text="0", style="Small.TLabel").pack(side="left")
        ttk.Label(slider_labels_frame, text="100", style="Small.TLabel").pack(side="right")


        # --- Customization Section ---
        ttk.Label(self.settings_scrollable_frame, text="Customization", style="Heading.TLabel").pack(pady=(15, 5), anchor="w", padx=10)

        # Theme mode selection (Light/Dark mode)
        theme_mode_frame = ttk.Frame(self.settings_scrollable_frame, style="Main.TFrame")
        theme_mode_frame.pack(fill="x", pady=5, padx=10)
        
        self.theme_mode_var = tk.StringVar(value=self.selected_theme_mode)

        # Light Mode Option
        light_mode_option_frame = ttk.Frame(theme_mode_frame, style="Main.TFrame", relief="solid", borderwidth=1,
                                            width=120, height=80)
        light_mode_option_frame.pack(side="left", padx=5, pady=5)
        
        # Placeholder for light mode visual
        ttk.Frame(light_mode_option_frame, background=constants.DEFAULT_LIGHT_MODE_BG, width=100, height=50).pack(pady=5)
        ttk.Radiobutton(light_mode_option_frame, text="Light mode", variable=self.theme_mode_var, value="Light", style="TRadiobutton").pack(pady=(0,5))
        
        # Dark Mode Option
        dark_mode_option_frame = ttk.Frame(theme_mode_frame, style="Main.TFrame", relief="solid", borderwidth=1,
                                           width=120, height=80)
        dark_mode_option_frame.pack(side="left", padx=5, pady=5)
        
        # Placeholder for dark mode visual
        ttk.Frame(dark_mode_option_frame, background=constants.DEFAULT_DARK_MODE_BG, width=100, height=50).pack(pady=5)
        ttk.Radiobutton(dark_mode_option_frame, text="Dark mode", variable=self.theme_mode_var, value="Dark", style="TRadiobutton").pack(pady=(0,5))

        # System Mode Option (New)
        system_mode_option_frame = ttk.Frame(theme_mode_frame, style="Main.TFrame", relief="solid", borderwidth=1,
                                            width=120, height=80)
        system_mode_option_frame.pack(side="left", padx=5, pady=5)
        
        # Placeholder for system mode visual (can be split or generic)
        ttk.Frame(system_mode_option_frame, background=constants.DEFAULT_LIGHT_MODE_BG, width=50, height=50).pack(side="left",pady=5)
        ttk.Frame(system_mode_option_frame, background=constants.DEFAULT_DARK_MODE_BG, width=50, height=50).pack(side="right",pady=5)

        ttk.Radiobutton(system_mode_option_frame, text="System default", variable=self.theme_mode_var, value="System", style="TRadiobutton").pack(pady=(0,5))


        # Apply Button
        apply_button = ttk.Button(self.settings_scrollable_frame, text="Apply", command=self._apply_settings, style="Accent.TButton")
        apply_button.pack(pady=(20, 10), padx=10, fill="x")

    def _update_threshold_label(self, value):
        """Updates the label next to the unplug threshold slider."""
        self.unplug_threshold_label.config(text=f"{int(float(value))}%")

    def _browse_custom_logo(self):
        """Opens a file dialog for custom logo path."""
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif")])
        if file_path:
            self.custom_logo_path = file_path
            # Update the settings screen's logo display
            if hasattr(self, 'user_logo_label') and self.user_logo_label.winfo_exists():
                try:
                    logo_img = Image.open(file_path)
                    logo_img = logo_img.resize((60, 60), Image.Resampling.LANCZOS)
                    logo_photo = ImageTk.PhotoImage(logo_img)
                    self.user_logo_label.config(image=logo_photo)
                    self.user_logo_label.image = logo_photo
                except Exception as e:
                    logger.error(f"Failed to load selected custom logo: {e}")
                    messagebox.showerror("Error", "Could not load selected image. Please choose a valid image file.")
                    self._create_circular_placeholder(self.user_logo_label, 60, "gray")
            logger.info(f"Custom logo path selected: {self.custom_logo_path}")

    def _apply_settings(self):
        """Applies and saves settings from the settings screen."""
        try:
            new_threshold = int(self.unplug_threshold_slider.get())
            new_display_name = self.display_name_entry.get().strip()
            new_theme_mode = self.theme_mode_var.get()

            if not 0 <= new_threshold <= 100:
                raise ValueError("Unplug threshold must be between 0 and 100.")
            if not new_display_name:
                raise ValueError("Display name cannot be empty.")

            self.unplug_threshold = new_threshold
            self.display_name = new_display_name
            self.selected_theme_mode = new_theme_mode

            # Update display name label in sidebar immediately
            self.display_name_label.config(text=self.display_name)

            # Re-apply theme based on new selection
            self.apply_theme_colors()
            self.configure_styles() # Reconfigure styles to ensure all widgets update

            self.save_settings_to_file()
            messagebox.showinfo("Settings Saved", "Your settings have been applied successfully!")
            self.show_screen("main") # Go back to main screen after saving
        except ValueError as ve:
            messagebox.showerror("Invalid Input", str(ve))
        except Exception as e:
            logger.error(f"Error applying settings: {e}")
            messagebox.showerror("Error", f"An unexpected error occurred while applying settings: {e}")

    def show_unplug_prompt(self):
        """Show the unplug prompt window with optional custom logo."""
        global UNPLUG_PROMPT_ACTIVE
        if UNPLUG_PROMPT_ACTIVE:
            logger.info("Unplug prompt already active, skipping.")
            return
        logger.info("Showing unplug prompt...")
        UNPLUG_PROMPT_ACTIVE = True
        
        self.unplug_window = tk.Toplevel(self.root)
        self.unplug_window.title("Battery Full - Action Required")
        self.unplug_window.geometry(f"{constants.PROMPT_WINDOW_WIDTH}x{constants.PROMPT_WINDOW_HEIGHT}")
        self.unplug_window.resizable(False, False)
        self.unplug_window.overrideredirect(True) # Remove title bar
        self.unplug_window.configure(bg=self.current_bg)
        self.unplug_window.attributes('-topmost', True)
        self.unplug_window.attributes('-alpha', 0.95) # Acrylic effect

        screen_width = self.unplug_window.winfo_screenwidth()
        screen_height = self.unplug_window.winfo_screenheight()
        x = (screen_width - constants.PROMPT_WINDOW_WIDTH) // 2
        y = (screen_height - constants.PROMPT_WINDOW_HEIGHT) // 2
        self.unplug_window.geometry(f"+{x}+{y}")

        # Fade-in animation
        if not self.power_saving_mode:
            self.unplug_window.attributes('-alpha', 0)
            for alpha in range(0, 21):
                self.unplug_window.attributes('-alpha', alpha / 20)
                self.unplug_window.update_idletasks() # Ensure window updates
                time.sleep(0.01)
            self.unplug_window.attributes('-alpha', 0.95)

        main_frame_prompt = ttk.Frame(self.unplug_window, style="Main.TFrame")
        main_frame_prompt.pack(fill="both", expand=True, padx=20, pady=20)
        main_frame_prompt.columnconfigure(0, weight=1)
        for i in range(5):
            main_frame_prompt.rowconfigure(i, weight=0)

        row = 0
        logo_photo = None
        if self.custom_logo_path and os.path.exists(self.custom_logo_path):
            try:
                logo_img = Image.open(self.custom_logo_path)
                original_width, original_height = logo_img.size
                target_size = 100
                ratio = min(target_size / original_width, target_size / original_height)
                new_width = int(original_width * ratio)
                new_height = int(original_height * ratio)
                logo_img = logo_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logo_photo = ImageTk.PhotoImage(logo_img)
                logo_label = ttk.Label(main_frame_prompt, image=logo_photo, background=self.current_bg)
                logo_label.image = logo_photo # Keep reference
                logo_label.grid(row=row, column=0, pady=(0, 8), sticky="n")
                row += 1
                logger.info(f"Custom logo loaded for prompt from {self.custom_logo_path}")
            except Exception as e:
                logger.error(f"Failed to load custom logo for prompt: {e}")

        prompt_label = ttk.Label(main_frame_prompt, text="Battery Full!\nPlease Unplug Charger", style="Prompt.TLabel", anchor="center", justify="center")
        prompt_label.grid(row=row, column=0, pady=(0 if row > 0 else 16, 8), sticky="nsew")
        row += 1

        info_label = ttk.Label(main_frame_prompt, text="Unplugging your charger when the battery is fully charged:\n"
                                                            "- Extends battery lifespan by preventing overcharging.\n"
                                                            "- Reduces energy waste and lowers your carbon footprint.\n"
                                                            "- Protects your device from potential heat damage.",
                               style="Info.TLabel", anchor="center", justify="center")
        info_label.grid(row=row, column=0, pady=(0, 16), sticky="nsew")
        row += 1

        countdown_label = ttk.Label(main_frame_prompt, text=f"Auto-close in {constants.PROMPT_TIMEOUT_SECONDS}s", style="Countdown.TLabel", anchor="center")
        countdown_label.grid(row=row, column=0, pady=(0, 16), sticky="nsew")
        row += 1

        # This method needs to be defined in a way that it can be called later
        def add_close_button_after_timeout():
            if self.unplug_window and self.unplug_window.winfo_exists():
                close_button = ttk.Button(main_frame_prompt, text="Close", command=self.close_unplug_prompt, style="Accent.TButton")
                close_button.grid(row=row, column=0, pady=(0, 16), sticky="nsew")
                logger.info("Close button added to prompt after timeout.")
                self.unplug_window.bind("<Escape>", lambda event: self.close_unplug_prompt()) # Allow ESC to close
                main_frame_prompt.rowconfigure(row, weight=0) # Ensure row is configured

        self.prompt_start_time = time.time()
        self.unplug_window.after(int(constants.PROMPT_TIMEOUT_SECONDS * 1000), add_close_button_after_timeout)
        self.monitor_unplug(countdown_label)
        logger.info("Unplug prompt displayed.")

    def close_unplug_prompt(self):
        """Close the unplug prompt manually with fade-out."""
        global UNPLUG_PROMPT_ACTIVE
        if self.unplug_window and self.unplug_window.winfo_exists():
            for alpha in range(20, -1, -1):
                self.unplug_window.attributes('-alpha', alpha / 20)
                self.unplug_window.update_idletasks()
                time.sleep(0.01)
            self.unplug_window.destroy()
            UNPLUG_PROMPT_ACTIVE = False
            logger.info("Unplug prompt closed manually.")

    def monitor_unplug(self, countdown_label):
        """Monitor battery status and idle time to close the unplug prompt."""
        global UNPLUG_PROMPT_ACTIVE
        try:
            if not self.unplug_window.winfo_exists():
                logger.info("Unplug window no longer exists, stopping monitor_unplug.")
                UNPLUG_PROMPT_ACTIVE = False
                return

            battery = psutil.sensors_battery()
            idle_time = get_idle_time() # This will be 0 if pywin32 is not installed

            if battery and not battery.power_plugged:
                logger.info("Charger unplugged, closing prompt.")
                self.close_unplug_prompt()
                return
            elif idle_time >= constants.IDLE_TIMEOUT_SECONDS:
                logger.info(f"System idle for {constants.IDLE_TIMEOUT_SECONDS} seconds, closing prompt.")
                self.close_unplug_prompt()
                return
            else:
                if not hasattr(self, "prompt_start_time"): # Fallback in case it's not set
                    self.prompt_start_time = time.time()
                
                elapsed_time = time.time() - self.prompt_start_time
                remaining_seconds = max(0, constants.PROMPT_TIMEOUT_SECONDS - int(elapsed_time))
                countdown_label.config(text=f"Auto-close in {remaining_seconds}s")
                
                # Close automatically after a grace period if prompt_timeout is reached
                if elapsed_time >= constants.PROMPT_TIMEOUT_SECONDS + 10: # 10 seconds grace period
                    logger.warning("Prompt stuck after timeout grace period, force closing.")
                    self.close_unplug_prompt()
                    return

            self.unplug_window.after(500, lambda: self.monitor_unplug(countdown_label)) # Check every 0.5 seconds
        except Exception as e:
            logger.error(f"Error in monitor_unplug: {e}")
            if self.unplug_window.winfo_exists():
                self.unplug_window.after(500, lambda: self.monitor_unplug(countdown_label))

    def minimize_to_tray(self):
        """Minimize the app to the system tray with fade-out."""
        global MINIMIZED_TO_TRAY
        logger.info("Minimizing to tray...")
        MINIMIZED_TO_TRAY = True
        if not self.power_saving_mode: # Only animate if not in power saving mode
            for alpha in range(20, -1, -1):
                self.root.attributes('-alpha', alpha / 20)
                self.root.update_idletasks()
                time.sleep(0.01)
        self.root.withdraw() # Hide the window
        if self.tray:
            self.tray.update_menu() # Ensure tray icon is visible
        logger.info("Minimized to tray successfully.")


if __name__ == "__main__":
    root = tk.Tk()
    app = BatteryMonitorApp(root)
    root.mainloop()