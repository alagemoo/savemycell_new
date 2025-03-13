import psutil
import platform
import getpass
import socket
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont  # Added import for font handling
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
import darkdetect  # For light/dark mode detection

# Detect idle time on Windows
try:
    import win32api
    import win32con
except ImportError:
    win32api = None
    win32con = None

# Define version flag
VERSION = "FREE"  # Can be "FREE" or "PRO"

# Configure logging
log_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "SaveMyCell")
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file = os.path.join(log_dir, "SaveMyCell.log")
logging.basicConfig(filename=log_file, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global flags and constants
RUNNING = True
MINIMIZED_TO_TRAY = False
UNPLUG_PROMPT_ACTIVE = False
PROMPT_QUEUE = queue.Queue()
WINDOW_WIDTH, WINDOW_HEIGHT = 400, 500
UNPLUG_THRESHOLD = 90
REFRESH_INTERVAL = 120
POWER_SAVING_REFRESH_INTERVAL = 600
IDLE_TIMEOUT = 120
PROMPT_TIMEOUT = 30

# Utility Functions
def calculate_battery_time(battery: Optional[psutil.sensors_battery]) -> str:
    if not battery:
        return "Time: N/A"
    if not battery.power_plugged:
        if battery.secsleft == psutil.POWER_TIME_UNKNOWN:
            return "Time: Estimating..."
        hours = battery.secsleft // 3600
        minutes = (battery.secsleft % 3600) // 60
        return f"Time to Discharge: {hours}h {minutes}m"
    if battery.power_plugged:
        current_percent = battery.percent
        remaining_percent = 100 - current_percent
        charging_rate = 40.0 + (60.0 - 40.0) * (1 - current_percent / 100)
        hours_to_full = remaining_percent / charging_rate
        total_seconds = int(hours_to_full * 3600)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"Time to Full Charge: {hours}h {minutes}m" if remaining_percent > 0 else "Time to Full Charge: Fully Charged"

def get_system_details() -> Dict[str, str]:
    if not hasattr(get_system_details, "cached_details"):
        get_system_details.cached_details = {
            "System Name": socket.gethostname(),
            "Laptop Model Number": platform.machine(),
            "System Username": getpass.getuser(),
            "Operating System": f"{platform.system()} {platform.release()}",
            "Processor": platform.processor()
        }
    battery = psutil.sensors_battery()
    if battery:
        get_system_details.cached_details.update({
            "Battery Percentage": f"{battery.percent}%",
            "Battery Status": "Charging" if battery.power_plugged else "Discharging",
            "Power Plugged": str(battery.power_plugged),
            "Battery Cell Type": "Unknown",
            "Time to Full Charge": "N/A",
            "Time to Complete Discharge": "N/A"
        })
        time_text = calculate_battery_time(battery)
        if "Full Charge" in time_text:
            get_system_details.cached_details["Time to Full Charge"] = time_text.replace("Time to Full Charge: ", "")
        elif "Discharge" in time_text:
            get_system_details.cached_details["Time to Complete Discharge"] = time_text.replace("Time to Discharge: ", "")
    else:
        get_system_details.cached_details.update({
            "Battery Percentage": "N/A",
            "Battery Status": "N/A",
            "Power Plugged": "N/A",
            "Battery Cell Type": "N/A",
            "Time to Full Charge": "N/A",
            "Time to Complete Discharge": "N/A"
        })
    return get_system_details.cached_details

def set_auto_start(enabled: bool) -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
        app_name = "SaveMyCellbyValionTech"
        if enabled:
            if getattr(sys, 'frozen', False):
                executable_path = sys.executable
                if not os.path.exists(executable_path):
                    logger.error(f"Executable path does not exist: {executable_path}")
                    winreg.CloseKey(key)
                    return False
                if os.path.dirname(executable_path).lower() == os.path.join(os.environ.get("ProgramFiles", "").lower(), "SaveMyCell").lower():
                    installed_path = os.path.join(os.environ.get("ProgramFiles", ""), "SaveMyCell", "SaveMyCell.exe")
                    if os.path.exists(installed_path):
                        executable_path = installed_path
                registry_value = f'"{executable_path}"'
            else:
                python_exe = sys.executable
                script_path = os.path.abspath(__file__)
                if not os.path.exists(python_exe) or not os.path.exists(script_path):
                    logger.error(f"Python or script path not found: {python_exe}, {script_path}")
                    winreg.CloseKey(key)
                    return False
                registry_value = f'"{python_exe}" "{script_path}"'
            logger.info(f"Setting auto-start with value: {registry_value}")
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, registry_value)
        else:
            winreg.DeleteValue(key, app_name)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.error(f"Failed to set auto-start: {str(e)}")
        return False

def is_auto_start_enabled() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        app_name = "SaveMyCellbyValionTech"
        try:
            winreg.QueryValueEx(key, app_name)
            winreg.CloseKey(key)
            return True
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
                    if MINIMIZED_TO_TRAY and (not battery.power_plugged or battery.percent < self.app.unplug_threshold):
                        sleep_interval = 300
                    elif self.app.power_saving_mode:
                        sleep_interval = POWER_SAVING_REFRESH_INTERVAL
                    elif battery.power_plugged and battery.percent >= self.app.unplug_threshold:
                        sleep_interval = 5
                    else:
                        sleep_interval = self.app.refresh_interval
                    if battery.percent >= self.app.unplug_threshold and battery.power_plugged:
                        if not UNPLUG_PROMPT_ACTIVE:
                            if self.last_battery and not self.last_battery.power_plugged and battery.power_plugged:
                                logger.info("Charger replugged above threshold, triggering prompt...")
                                PROMPT_QUEUE.put(True)
                            elif current_time - self.last_unplug_prompt_time >= 300 or not self.last_unplug_prompt_time:
                                logger.info("Triggering unplug prompt...")
                                PROMPT_QUEUE.put(True)
                                self.last_unplug_prompt_time = current_time
                    elif self.last_battery and not battery.power_plugged and self.last_battery.power_plugged:
                        if battery.percent < self.app.unplug_threshold:
                            self.last_unplug_prompt_time = 0
                            logger.info("Charger unplugged and below threshold, resetting cooldown.")
                    self.last_battery = battery
                    if self.app.root.winfo_exists() and not MINIMIZED_TO_TRAY:
                        if self.last_percent is None or self.last_plugged is None or \
                           abs(battery.percent - self.last_percent) >= 1 or battery.power_plugged != self.last_plugged:
                            self.app.root.after(0, lambda: self.app.update_ui(battery.percent, battery.power_plugged))
                            self.last_percent = battery.percent
                            self.last_plugged = battery.power_plugged
                    if current_time - self.last_update >= 300:
                        self.app.update_system_stats()
                        self.last_update = current_time
                time.sleep(sleep_interval)
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(10)

# System Tray
def create_tray_icon(app):
    global MINIMIZED_TO_TRAY
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(__file__)
    icon_path = os.path.join(base_path, "icon.png")
    try:
        if os.path.exists(icon_path) and os.path.getsize(icon_path) > 0:
            icon = Image.open(icon_path)
            icon = icon.resize((32, 32), Image.Resampling.LANCZOS)
            logger.info(f"Loaded tray icon from {icon_path}")
        else:
            logger.warning(f"Icon file {icon_path} not found or empty. Using fallback.")
            icon = Image.new("RGBA", (32, 32), (245, 245, 245, 255))
    except Exception as e:
        logger.error(f"Failed to load tray icon: {e}")
        icon = Image.new("RGBA", (32, 32), (245, 245, 245, 255))
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
    app.root.after(0, lambda: app.show_main_screen())
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
    def __init__(self, root, unplug_threshold=UNPLUG_THRESHOLD, refresh_interval=REFRESH_INTERVAL):
        self.root = root
        self.root.title("Save My Cell")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Initialize settings and theme first
        self.unplug_threshold = unplug_threshold
        self.refresh_interval = refresh_interval
        self.power_saving_mode = False
        self.background_color = "#F3F3F3"  # Default light mode Mica-like color
        self.font_type = "Segoe UI Variable" if "Segoe UI Variable" in tkfont.families() else "Segoe UI"
        self.text_color = "#000000"  # Default light mode
        self.custom_logo_path = ""
        self.accent_color = "#0078D4"  # Windows 11 default accent color
        self.is_dark_mode = darkdetect.isDark()  # Initialize theme detection first
        self.update_theme()  # Apply initial theme

        # Load settings after theme initialization
        self.load_settings_from_file()

        # Apply acrylic effect and rounded corners (Windows 11 style)
        self.root.attributes('-alpha', 0.95)  # Slight transparency for acrylic effect
        self.root.wm_attributes('-transparentcolor', 'gray')  # Simulate Mica/acrylic background

        # Main UI setup
        self.main_frame = ttk.Frame(self.root, style="Main.TFrame")
        self.alt_frame = None
        self.tray, self.tray_thread = create_tray_icon(self)
        self.tray_thread.start()
        self.monitor = BatteryMonitor(self)
        self.monitor_thread = threading.Thread(target=self.monitor.run, daemon=True)
        self.monitor_thread.start()
        self._build_main_screen()
        self.check_prompt_queue()

        # Monitor theme changes
        self.root.after(1000, self.check_theme_change)

    def update_theme(self):
        """Update colors based on system theme (light/dark mode)."""
        if self.is_dark_mode:
            self.background_color = "#2D2D2D"  # Windows 11 dark mode Mica-like color
            self.text_color = "#FFFFFF"       # White text for dark mode
            self.secondary_bg = "#3B3B3B"     # Slightly lighter for contrast
        else:
            self.background_color = "#F3F3F3"  # Windows 11 light mode Mica-like color
            self.text_color = "#000000"       # Black text for light mode
            self.secondary_bg = "#E6E6E6"     # Slightly darker for contrast
        self.root.configure(bg=self.background_color)
        self.configure_styles()

    def check_theme_change(self):
        """Check for system theme changes and update UI."""
        new_theme = darkdetect.isDark()
        if new_theme != self.is_dark_mode:
            self.is_dark_mode = new_theme
            self.update_theme()
            self.show_main_screen()  # Refresh UI
        self.root.after(1000, self.check_theme_change)

    def configure_styles(self):
        """Configure Tkinter styles dynamically based on settings and theme."""
        self.style.configure("Main.TFrame", background=self.background_color)
        self.style.configure("Custom.TButton",
                             font=(self.font_type, 11),
                             padding=10,
                             background=self.accent_color,
                             foreground="#FFFFFF",
                             borderwidth=0,
                             relief="flat",
                             bordercolor=self.accent_color)
        self.style.map("Custom.TButton",
                       background=[("active", "#005BA1")],
                       foreground=[("active", "#FFFFFF")])
        self.style.configure("Stop.TButton",
                             font=(self.font_type, 11),
                             padding=10,
                             background="#D83B01",
                             foreground="#FFFFFF",
                             borderwidth=0,
                             relief="flat")
        self.style.map("Stop.TButton",
                       background=[("active", "#A12D00")],
                       foreground=[("active", "#FFFFFF")])
        self.style.configure("Back.TButton",
                             font=(self.font_type, 10),
                             padding=10,
                             background=self.secondary_bg,
                             foreground=self.text_color,
                             borderwidth=0,
                             relief="flat")
        self.style.map("Back.TButton",
                       background=[("active", "#D0D0D0" if not self.is_dark_mode else "#404040")],
                       foreground=[("active", self.text_color)])
        self.style.configure("Title.TLabel",
                             font=(self.font_type, 14, "bold"),
                             foreground=self.text_color,
                             background=self.background_color)
        self.style.configure("Prompt.TLabel",
                             font=(self.font_type, 20, "bold"),
                             foreground="#D83B01",
                             background=self.background_color)
        self.style.configure("Info.TLabel",
                             font=(self.font_type, 11),
                             foreground="#666666" if not self.is_dark_mode else "#AAAAAA",
                             background=self.background_color,
                             wraplength=600)

    def save_settings_to_file(self):
        """Save settings, including UI customizations, to a JSON file."""
        try:
            settings = {
                "unplug_threshold": self.unplug_threshold,
                "refresh_interval": self.refresh_interval,
                "power_saving_mode": self.power_saving_mode,
                "ui_settings": {
                    "custom_logo_path": self.custom_logo_path,
                    "background_color": self.background_color,
                    "text_color": self.text_color
                }
            }
            with open(os.path.join(log_dir, "settings.json"), "w") as f:
                json.dump(settings, f)
            logger.info(f"Settings saved to settings.json: {settings}")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            messagebox.showerror("Error", "Failed to save settings. Check logs for details.")

    def load_settings_from_file(self):
        """Load settings, including UI customizations, from a JSON file."""
        settings_file = os.path.join(log_dir, "settings.json")
        try:
            if not os.path.exists(settings_file):
                logger.warning(f"Settings file not found at {settings_file}. Using defaults.")
                raise FileNotFoundError(f"Settings file not found at {settings_file}")
            
            with open(settings_file, "r") as f:
                settings = json.load(f)
                self.unplug_threshold = settings.get("unplug_threshold", UNPLUG_THRESHOLD)
                self.refresh_interval = settings.get("refresh_interval", REFRESH_INTERVAL)
                self.power_saving_mode = settings.get("power_saving_mode", False)
                ui_settings = settings.get("ui_settings", {})
                self.custom_logo_path = ui_settings.get("custom_logo_path", "")
                self.background_color = ui_settings.get("background_color", "#F3F3F3")  # Default light mode
                self.text_color = ui_settings.get("text_color", "#000000")  # Default light mode
                self.update_theme()  # Apply loaded colors
                self.configure_styles()
                logger.info(f"Settings loaded from {settings_file}: {settings}")
        except FileNotFoundError as e:
            logger.error(f"Failed to load settings due to file not found: {e}")
            messagebox.showerror("Error", f"Failed to load settings. Using defaults. Details: {e}")
            self.unplug_threshold = UNPLUG_THRESHOLD
            self.refresh_interval = REFRESH_INTERVAL
            self.power_saving_mode = False
            self.custom_logo_path = ""
            self.background_color = "#F3F3F3"
            self.text_color = "#000000"
            self.update_theme()
            self.configure_styles()
            self.save_settings_to_file()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse settings file {settings_file}: {e}")
            messagebox.showerror("Error", f"Failed to load settings due to invalid JSON. Using defaults. Details: {e}")
            self.unplug_threshold = UNPLUG_THRESHOLD
            self.refresh_interval = REFRESH_INTERVAL
            self.power_saving_mode = False
            self.custom_logo_path = ""
            self.background_color = "#F3F3F3"
            self.text_color = "#000000"
            self.update_theme()
            self.configure_styles()
            self.save_settings_to_file()
        except Exception as e:
            logger.error(f"Unexpected error loading settings from {settings_file}: {e}")
            messagebox.showerror("Error", f"Failed to load settings. Using defaults. Details: {e}")
            self.unplug_threshold = UNPLUG_THRESHOLD
            self.refresh_interval = REFRESH_INTERVAL
            self.power_saving_mode = False
            self.custom_logo_path = ""
            self.background_color = "#F3F3F3"
            self.text_color = "#000000"
            self.update_theme()
            self.configure_styles()
            self.save_settings_to_file()
        if not is_auto_start_enabled():
            logger.info("Auto-start not enabled, enabling it now...")
            set_auto_start(True)

    def _build_main_screen(self):
        """Build the main screen UI using grid layout with Fluent Design."""
        logger.info("Building main screen...")
        for widget in self.main_frame.winfo_children():
            widget.destroy()
        self.main_frame.pack(fill="both", expand=True, padx=16, pady=16)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(0, weight=1)  # Battery percentage
        self.main_frame.rowconfigure(1, weight=0)  # Status
        self.main_frame.rowconfigure(2, weight=0)  # Time
        self.main_frame.rowconfigure(3, weight=0)  # Button frame spacer
        self.main_frame.rowconfigure(4, weight=0)  # Button frame

        battery = psutil.sensors_battery()
        initial_percent = f"{battery.percent}%" if battery else "N/A"
        self.battery_label = ttk.Label(
            self.main_frame,
            text=initial_percent,
            font=(self.font_type, 80, "bold"),
            foreground=self.text_color,
            background=self.background_color,
            anchor="center"
        )
        self.battery_label.grid(row=0, column=0, pady=(0, 8), sticky="nsew")

        status = "Charging" if (battery and battery.power_plugged) else "Discharging"
        self.battery_status = ttk.Label(
            self.main_frame,
            text=status,
            font=(self.font_type, 14),
            foreground="#666666" if not self.is_dark_mode else "#AAAAAA",
            background=self.background_color,
            anchor="center"
        )
        self.battery_status.grid(row=1, column=0, pady=(0, 8), sticky="ew")

        self.battery_time = ttk.Label(
            self.main_frame,
            text=calculate_battery_time(battery),
            font=(self.font_type, 14),
            foreground=self.text_color,
            background=self.background_color,
            anchor="center"
        )
        self.battery_time.grid(row=2, column=0, pady=(0, 16), sticky="ew")

        button_frame = ttk.Frame(self.main_frame, style="Main.TFrame")
        button_frame.grid(row=4, column=0, pady=(16, 0), sticky="nsew")
        button_frame.columnconfigure(0, weight=1)

        self.details_button = ttk.Button(button_frame, text="System Diagnostics", command=self.show_details, style="Custom.TButton")
        self.details_button.grid(row=0, column=0, pady=4, padx=10, sticky="ew")
        self.about_button = ttk.Button(button_frame, text="About Save My Cell", command=self.show_about, style="Custom.TButton")
        self.about_button.grid(row=1, column=0, pady=4, padx=10, sticky="ew")
        self.stop_button = ttk.Button(button_frame, text="Minimize", command=self.minimize_to_tray, style="Stop.TButton")
        self.stop_button.grid(row=2, column=0, pady=4, padx=10, sticky="ew")
        self.settings_button = ttk.Button(button_frame, text="Settings", command=self.show_settings, style="Custom.TButton")
        self.settings_button.grid(row=3, column=0, pady=4, padx=10, sticky="ew")
        logger.info("Main screen built successfully.")

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
        self.unplug_window.geometry("640x400")  # Increased height to 400
        self.unplug_window.resizable(False, False)
        self.unplug_window.overrideredirect(True)
        self.unplug_window.configure(bg=self.background_color)
        self.unplug_window.attributes('-topmost', True)
        self.unplug_window.attributes('-alpha', 0.95)  # Acrylic effect

        screen_width = self.unplug_window.winfo_screenwidth()
        screen_height = self.unplug_window.winfo_screenheight()
        x = (screen_width - 640) // 2
        y = (screen_height - 400) // 2
        self.unplug_window.geometry(f"+{x}+{y}")

        if not self.power_saving_mode:
            self.unplug_window.attributes('-alpha', 0)
            for alpha in range(0, 21):
                self.unplug_window.attributes('-alpha', alpha / 20)
                time.sleep(0.01)
            self.unplug_window.attributes('-alpha', 0.95)

        self.main_frame_prompt = ttk.Frame(self.unplug_window, style="Main.TFrame")
        self.main_frame_prompt.place(relx=0.5, rely=0.5, anchor="center")
        self.main_frame_prompt.columnconfigure(0, weight=1)
        for i in range(5):  # Configure rows 0 to 4
            self.main_frame_prompt.rowconfigure(i, weight=0)

        row = 0
        logo_image = None

        if hasattr(self, "custom_logo_path") and self.custom_logo_path and os.path.exists(self.custom_logo_path):
            try:
                logo_img = Image.open(self.custom_logo_path)
                # Preserve aspect ratio
                original_width, original_height = logo_img.size
                target_size = 100
                ratio = min(target_size / original_width, target_size / original_height)
                new_width = int(original_width * ratio)
                new_height = int(original_height * ratio)
                logo_img = logo_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logo_photo = ImageTk.PhotoImage(logo_img)
                logo_label = ttk.Label(self.main_frame_prompt, image=logo_photo, background=self.background_color)
                logo_label.image = logo_photo  # Keep a reference to avoid garbage collection
                logo_label.grid(row=row, column=0, pady=(16, 8), padx=20, sticky="n")
                row += 1
                logger.info(f"Custom logo loaded from {self.custom_logo_path}")
            except Exception as e:
                logger.error(f"Failed to load custom logo: {e}")

        prompt_label = ttk.Label(self.main_frame_prompt, text="Battery Full!\nPlease Unplug Charger", style="Prompt.TLabel", anchor="center", justify="center")
        prompt_label.grid(row=row, column=0, pady=(0 if row > 0 else 16, 8), padx=20, sticky="nsew")
        row += 1

        info_label = ttk.Label(self.main_frame_prompt, text="Unplugging your charger when the battery is fully charged:\n"
                                                            "- Extends battery lifespan by preventing overcharging.\n"
                                                            "- Reduces energy waste and lowers your carbon footprint.\n"
                                                            "- Protects your device from potential heat damage.",
                               style="Info.TLabel", anchor="center", justify="center")
        info_label.grid(row=row, column=0, pady=(0, 16), padx=20, sticky="nsew")
        row += 1

        countdown_label = ttk.Label(self.main_frame_prompt, text=f"Auto-close in {PROMPT_TIMEOUT}s", font=(self.font_type, 14, "bold"), foreground=self.accent_color, background=self.background_color, anchor="center")
        countdown_label.grid(row=row, column=0, pady=(0, 16), padx=20, sticky="nsew")
        row += 1

        def add_close_button():
            elapsed_time = time.time() - self.prompt_start_time
            if elapsed_time >= PROMPT_TIMEOUT and self.unplug_window.winfo_exists():
                close_button = ttk.Button(self.main_frame_prompt, text="Close", command=lambda: self.close_unplug_prompt(), style="Custom.TButton")
                close_button.grid(row=row, column=0, pady=(0, 16), padx=20, sticky="nsew")
                logger.info("Close button added after timeout.")
                self.unplug_window.bind("<Escape>", lambda event: self.close_unplug_prompt())
                self.main_frame_prompt.rowconfigure(row, weight=0)  # Ensure row is configured after adding

        self.prompt_start_time = time.time()
        self.unplug_window.after(int(PROMPT_TIMEOUT * 1000), add_close_button)
        self.monitor_unplug(countdown_label)
        logger.info("Unplug prompt displayed.")

    def close_unplug_prompt(self):
        """Close the unplug prompt manually with fade-out."""
        global UNPLUG_PROMPT_ACTIVE
        if self.unplug_window and self.unplug_window.winfo_exists():
            for alpha in range(20, -1, -1):
                self.unplug_window.attributes('-alpha', alpha / 20)
                time.sleep(0.01)
            self.unplug_window.destroy()
            UNPLUG_PROMPT_ACTIVE = False
            logger.info("Unplug prompt closed manually.")

    def monitor_unplug(self, countdown_label):
        """Monitor battery status to close the unplug prompt."""
        global UNPLUG_PROMPT_ACTIVE
        try:
            if not self.unplug_window.winfo_exists():
                logger.info("Unplug window closed.")
                UNPLUG_PROMPT_ACTIVE = False
                return
            battery = None
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    battery = psutil.sensors_battery()
                    if battery is not None:
                        break
                    logger.warning(f"Battery status None on attempt {attempt + 1}/{max_retries}")
                    time.sleep(0.1)
                except Exception as e:
                    logger.error(f"Battery status error on attempt {attempt + 1}/{max_retries}: {e}")
                    time.sleep(0.1)
            idle_time = get_idle_time()
            if battery and not battery.power_plugged:
                self.close_unplug_prompt()
                logger.info("Charger unplugged, closing prompt.")
                return
            elif idle_time >= IDLE_TIMEOUT:
                self.close_unplug_prompt()
                logger.info("System idle for 2 minutes, closing prompt.")
                return
            else:
                if not hasattr(self, "prompt_start_time"):
                    self.prompt_start_time = time.time()
                elapsed_time = time.time() - self.prompt_start_time
                if elapsed_time >= PROMPT_TIMEOUT:
                    countdown_label.config(text="Auto-close in 0s")
                    logger.info("Countdown reached 0, waiting for manual close.")
                    if elapsed_time >= PROMPT_TIMEOUT + 30:
                        self.close_unplug_prompt()
                        logger.warning("Prompt stuck after timeout, force closing.")
                        return
                else:
                    remaining = max(0, PROMPT_TIMEOUT - int(elapsed_time))
                    countdown_label.config(text=f"Auto-close in {remaining}s")
                    self.unplug_window.after(500, lambda: self.monitor_unplug(countdown_label))
        except Exception as e:
            logger.error(f"Error in monitor_unplug: {e}")
            if self.unplug_window.winfo_exists():
                self.unplug_window.after(500, lambda: self.monitor_unplug(countdown_label))

    def check_unplug_prompt_on_restore(self):
        """Check battery state and show unplug prompt when restoring."""
        logger.info("Checking for unplug prompt on restore...")
        battery = psutil.sensors_battery()
        if battery and battery.percent >= self.unplug_threshold and battery.power_plugged:
            self.show_unplug_prompt()
        else:
            logger.info("No unplug prompt needed on restore.")

    def check_prompt_queue(self):
        """Check the prompt queue and show unplug prompt if signaled."""
        try:
            if not PROMPT_QUEUE.empty():
                PROMPT_QUEUE.get_nowait()
                battery = psutil.sensors_battery()
                if battery and battery.percent >= self.unplug_threshold and battery.power_plugged and not UNPLUG_PROMPT_ACTIVE:
                    self.show_unplug_prompt()
        except queue.Empty:
            pass
        self.root.after(500, self.check_prompt_queue)

    def show_alt_screen(self, title: str, content: str):
        """Show an alternate screen with Fluent Design."""
        logger.info(f"Showing alternate screen: {title}")
        if self.main_frame:
            self.main_frame.pack_forget()
        self.alt_frame = ttk.Frame(self.root, style="Main.TFrame")
        self.alt_frame.pack(fill="both", expand=True, padx=16, pady=16)
        self.alt_frame.columnconfigure(0, weight=1)

        self.alt_title = ttk.Label(self.alt_frame, text=title, style="Title.TLabel")
        self.alt_title.grid(row=0, column=0, pady=(0, 8), sticky="ew")

        content_lines = content.count('\n') + 1
        text_height = min(max(content_lines, 5), 10)
        self.alt_text = tk.Text(self.alt_frame, wrap="word", font=(self.font_type, 10), bg=self.secondary_bg, fg=self.text_color, relief="flat", borderwidth=0, height=text_height, width=50)
        self.alt_text.grid(row=1, column=0, pady=(0, 8), sticky="nsew")
        self.alt_text.insert(tk.END, content)
        self.alt_text.config(state="disabled")

        self.back_button = ttk.Button(self.alt_frame, text="Back to Monitor", command=self.show_main_screen, style="Back.TButton")
        self.back_button.grid(row=2, column=0, pady=(8, 0), sticky="ew")
        self.alt_frame.rowconfigure(0, weight=0)
        self.alt_frame.rowconfigure(1, weight=1)
        self.alt_frame.rowconfigure(2, weight=0)
        logger.info(f"Alternate screen {title} displayed.")

    def show_main_screen(self):
        """Show the main screen, restoring from tray or alternate screen with smooth animation."""
        global MINIMIZED_TO_TRAY
        logger.info("Showing main screen...")
        was_minimized = MINIMIZED_TO_TRAY
        if was_minimized:
            logger.info("Restoring from tray...")
            self.root.deiconify()
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            x = (screen_width - WINDOW_WIDTH) // 2
            y = (screen_height - WINDOW_HEIGHT) // 2
            self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")
            for alpha in range(0, 21):
                self.root.attributes('-alpha', alpha / 20)
                time.sleep(0.01)
            self.root.attributes('-alpha', 0.95)
            self.root.lift()
            self.root.focus_force()
            self.root.attributes('-topmost', True)
            self.root.update_idletasks()
            self.root.attributes('-topmost', False)
            self.root.update()
            self.check_unplug_prompt_on_restore()
            MINIMIZED_TO_TRAY = False
        else:
            if self.alt_frame:
                self.alt_frame.pack_forget()
            self.main_frame.pack(fill="both", expand=True, padx=16, pady=16)
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.update_idletasks()
        self.root.update()
        self.update_ui(psutil.sensors_battery().percent if psutil.sensors_battery() else 0,
                       psutil.sensors_battery().power_plugged if psutil.sensors_battery() else False)
        self.update_system_stats()
        logger.info("Main screen displayed.")

    def update_ui(self, percent: float, plugged: bool):
        """Update UI elements."""
        if self.battery_label:
            self.battery_label.config(text=f"{percent:.0f}%")
            self.battery_status.config(text="Charging" if plugged else "Discharging")
            self.battery_time.config(text=calculate_battery_time(psutil.sensors_battery()))

    def update_system_stats(self):
        """Update system stats (placeholder)."""
        pass

    def show_details(self):
        """Show the System Diagnostics screen."""
        details = get_system_details()
        details_text = "\n".join(f"{key}: {value}" for key, value in details.items())
        self.show_alt_screen("System Diagnostics", details_text)

    def show_about(self):
        """Show the About screen."""
        version_text = "Pro Version" if VERSION == "PRO" else "Free Version"
        about_text = f"Save My Cell\nDeveloped by: Gideon Aniechi\nVersion: MVP ({version_text})\nPowered by ValionTech"
        self.show_alt_screen("About Save My Cell", about_text)

    def show_settings(self):
        """Show Settings screen with UI customization options in a scrollable frame."""
        logger.info("Showing settings screen.")
        if self.main_frame:
            self.main_frame.pack_forget()

        self.alt_frame = ttk.Frame(self.root, style="Main.TFrame")
        self.alt_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(self.alt_frame, bg=self.background_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.alt_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style="Main.TFrame")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def configure_canvas(event):
            canvas.itemconfig(canvas_frame, width=event.width)
        canvas.bind("<Configure>", configure_canvas)

        self.alt_title = ttk.Label(scrollable_frame, text="Settings", style="Title.TLabel")
        self.alt_title.pack(pady=(16, 8))

        threshold_frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
        threshold_frame.pack(fill="x", pady=4, padx=16)
        ttk.Label(threshold_frame, text="Unplug Threshold (%):", font=(self.font_type, 11), foreground=self.text_color, background=self.background_color).pack(side="left", padx=8)
        threshold_entry = ttk.Entry(threshold_frame, font=(self.font_type, 11))
        threshold_entry.insert(0, str(self.unplug_threshold))
        threshold_entry.pack(side="left", padx=8, fill="x", expand=True)

        refresh_frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
        refresh_frame.pack(fill="x", pady=4, padx=16)
        ttk.Label(refresh_frame, text="Refresh Interval (s):", font=(self.font_type, 11), foreground=self.text_color, background=self.background_color).pack(side="left", padx=8)
        refresh_entry = ttk.Entry(refresh_frame, font=(self.font_type, 11))
        refresh_entry.insert(0, str(self.refresh_interval))
        if VERSION == "FREE":
            refresh_entry.config(state="disabled")
        refresh_entry.pack(side="left", padx=8, fill="x", expand=True)

        power_saving_frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
        power_saving_frame.pack(fill="x", pady=4, padx=16)
        ttk.Label(power_saving_frame, text="Power Saving Mode:", font=(self.font_type, 11), foreground=self.text_color, background=self.background_color).pack(side="left", padx=8)
        self.power_saving_var = tk.BooleanVar(value=self.power_saving_mode)
        power_saving_check = ttk.Checkbutton(power_saving_frame, variable=self.power_saving_var, onvalue=True, offvalue=False)
        power_saving_check.pack(side="left", padx=8)

        ui_frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
        ui_frame.pack(fill="x", pady=(16, 8), padx=16)
        ttk.Label(ui_frame, text="UI Customization", font=(self.font_type, 12, "bold"), foreground=self.text_color, background=self.background_color).pack(pady=(0, 8))

        logo_frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
        logo_frame.pack(fill="x", pady=4, padx=16)
        ttk.Label(logo_frame, text="Custom Logo Path:", font=(self.font_type, 11), foreground=self.text_color, background=self.background_color).pack(side="left", padx=8)
        logo_entry = ttk.Entry(logo_frame, font=(self.font_type, 11))
        logo_entry.insert(0, getattr(self, "custom_logo_path", ""))
        logo_entry.pack(side="left", padx=8, fill="x", expand=True)
        ttk.Button(logo_frame, text="Browse", command=lambda: logo_entry.delete(0, tk.END) or logo_entry.insert(0, filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")])), style="Custom.TButton").pack(side="left", padx=8)

        bg_color_frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
        bg_color_frame.pack(fill="x", pady=4, padx=16)
        ttk.Label(bg_color_frame, text="Background Color (Hex):", font=(self.font_type, 11), foreground=self.text_color, background=self.background_color).pack(side="left", padx=8)
        bg_color_entry = ttk.Entry(bg_color_frame, font=(self.font_type, 11))
        bg_color_entry.insert(0, self.background_color if hasattr(self, "background_color") else "#F3F3F3")
        bg_color_entry.pack(side="left", padx=8, fill="x", expand=True)

        text_color_frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
        text_color_frame.pack(fill="x", pady=4, padx=16)
        ttk.Label(text_color_frame, text="Text Color (Hex):", font=(self.font_type, 11), foreground=self.text_color, background=self.background_color).pack(side="left", padx=8)
        text_color_entry = ttk.Entry(text_color_frame, font=(self.font_type, 11))
        text_color_entry.insert(0, self.text_color if hasattr(self, "text_color") else "#000000")
        text_color_entry.pack(side="left", padx=8, fill="x", expand=True)

        button_frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
        button_frame.pack(fill="x", pady=(16, 16), padx=16)
        ttk.Button(button_frame, text="Save", command=lambda: save_settings(bg_color_entry, text_color_entry, threshold_entry, refresh_entry, logo_entry), style="Custom.TButton").pack(side="left", padx=8, fill="x", expand=True)
        ttk.Button(button_frame, text="Back to Monitor", command=self.show_main_screen, style="Back.TButton").pack(side="left", padx=8, fill="x", expand=True)

        def save_settings(bg_color_entry, text_color_entry, threshold_entry, refresh_entry, logo_entry):
            try:
                new_threshold = int(threshold_entry.get())
                if not 0 <= new_threshold <= 100:
                    raise ValueError("Unplug threshold must be 0-100.")
                if VERSION == "PRO":
                    new_refresh = int(refresh_entry.get())
                    if new_refresh <= 0:
                        raise ValueError("Refresh interval must be greater than 0.")
                    self.refresh_interval = new_refresh
                self.unplug_threshold = new_threshold
                self.power_saving_mode = self.power_saving_var.get()
                self.custom_logo_path = logo_entry.get().strip()
                if self.custom_logo_path and not os.path.exists(self.custom_logo_path):
                    messagebox.showwarning("Warning", "Logo file not found. It won’t be displayed until a valid path is provided.")

                # Validate and set new colors
                new_bg_color = bg_color_entry.get().strip()
                new_text_color = text_color_entry.get().strip()
                if not (new_bg_color.startswith('#') and len(new_bg_color) == 7) or not (new_text_color.startswith('#') and len(new_text_color) == 7):
                    raise ValueError("Colors must be valid hex codes (e.g., #RRGGBB).")
                self.background_color = new_bg_color
                self.text_color = new_text_color

                # Apply colors immediately
                self.update_theme()
                self.configure_styles()
                self.show_main_screen()  # Refresh UI with new colors

                # Save to file
                settings = {
                    "unplug_threshold": self.unplug_threshold,
                    "refresh_interval": self.refresh_interval,
                    "power_saving_mode": self.power_saving_mode,
                    "ui_settings": {
                        "custom_logo_path": self.custom_logo_path,
                        "background_color": self.background_color,
                        "text_color": self.text_color
                    }
                }
                with open(os.path.join(log_dir, "settings.json"), "w") as f:
                    json.dump(settings, f)
                logger.info(f"Settings saved to settings.json: {settings}")
                messagebox.showinfo("Success", "Settings saved successfully!")
            except ValueError as ve:
                messagebox.showerror("Error", str(ve))
            except Exception as e:
                logger.error(f"Error saving settings: {e}")
                messagebox.showerror("Error", f"An unexpected error occurred: {e}")

    def minimize_to_tray(self):
        """Minimize the app to the system tray with fade-out."""
        global MINIMIZED_TO_TRAY
        logger.info("Minimizing to tray...")
        MINIMIZED_TO_TRAY = True
        for alpha in range(20, -1, -1):
            self.root.attributes('-alpha', alpha / 20)
            time.sleep(0.01)
        self.root.withdraw()
        if self.tray:
            self.tray.update_menu()
        logger.info("Minimized to tray successfully.")

if __name__ == "__main__":
    root = tk.Tk()
    app = BatteryMonitorApp(root)
    root.mainloop()