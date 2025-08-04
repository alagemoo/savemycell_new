import psutil
import platform
import getpass
import socket
import customtkinter as ctk
from tkinter import messagebox, filedialog
import tkinter as tk
from PIL import Image, ImageTk
import threading
import time
import queue
import logging
import os
import winreg
import pystray
import darkdetect
import json
import sys
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
WINDOW_WIDTH, WINDOW_HEIGHT = 900, 600
UNPLUG_THRESHOLD = 90
REFRESH_INTERVAL = 120
POWER_SAVING_REFRESH_INTERVAL = 600
IDLE_TIMEOUT = 120
PROMPT_TIMEOUT = 30

# Set appearance mode and color theme
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# Utility Functions (from savemycell.py)
def calculate_battery_time(battery):
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

def get_system_details():
    details = {
        "System Name": socket.gethostname(),
        "Laptop Model Number": platform.machine(),
        "System Username": getpass.getuser(),
        "Operating System": f"{platform.system()} {platform.release()}",
        "Processor": platform.processor()
    }
    battery = psutil.sensors_battery()
    if battery:
        details.update({
            "Battery Percentage": f"{battery.percent}%",
            "Battery Status": "Charging" if battery.power_plugged else "Discharging",
            "Power Plugged": str(battery.power_plugged),
            "Battery Cell Type": "Unknown",
            "Time to Full Charge": calculate_battery_time(battery) if battery.power_plugged else "",
            "Time to Complete Discharge": calculate_battery_time(battery) if not battery.power_plugged else ""
        })
    else:
        details.update({
            "Battery Percentage": "N/A",
            "Battery Status": "N/A",
            "Power Plugged": "N/A",
            "Battery Cell Type": "N/A",
            "Time to Full Charge": "N/A",
            "Time to Complete Discharge": "N/A"
        })
    return details

def get_diagnostic_sections():
    mem = psutil.virtual_memory()
    memory_usage = f"{mem.used / 1e9:.1f} GB / {mem.total / 1e9:.1f} GB"
    disk = psutil.disk_usage('/')
    storage_usage = f"Storage Usage: {disk.used / 1e9:.1f} GB / {disk.total / 1e9:.1f} GB"
    network_status = "Connected" if socket.gethostbyname(socket.gethostname()) else "Disconnected"
    battery = psutil.sensors_battery()
    battery_summary = [
        str(battery.percent) if battery else "N/A",
        "Status: Charging" if battery and battery.power_plugged else "Status: Discharging",
        f"Power Plugged: {battery.power_plugged}" if battery else "Power Plugged: N/A",
        f"Time to Full Charge: {calculate_battery_time(battery)}" if battery and battery.power_plugged else "",
        f"Time to Complete Discharge: {calculate_battery_time(battery)}" if battery and not battery.power_plugged else ""
    ]
    percent = battery_summary.pop(0)
    sections = [
        ("Battery Health", [
            f"Current Capacity: {percent}%",
            "Design Capacity: WMI or battery_report.html",
            "Full Charge Capacity: WMI or battery_report.html",
            "Maximum Capacity: WMI or battery_report.html",
            "Capacity Retention: calculated from FullCharge / DesignCapacity"
        ]),
        ("Charging System", battery_summary),
        ("System Performance", [
            f"Memory Usage: {memory_usage}",
            f"Storage Usage: {storage_usage}",
            f"CPU Usage: {psutil.cpu_percent()}%"
        ])
    ]
    return sections

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
                            self.app.root.after(0, lambda: self.app.update_battery_ui(battery.percent, battery.power_plugged))
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
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Save My Cell")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        # Initialize settings
        self.unplug_threshold = UNPLUG_THRESHOLD
        self.refresh_interval = REFRESH_INTERVAL
        self.power_saving_mode = False
        self.background_color = "#F3F3F3"
        self.text_color = "#000000"
        self.custom_logo_path = ""
        self.is_dark_mode = darkdetect.isDark()
        self.appearance_mode = "light" if not self.is_dark_mode else "dark"
        self.current_page = "home"
        self.battery_percentage = 100

        # System tray
        self.tray, self.tray_thread = create_tray_icon(self)
        self.tray_thread.start()

        # Load settings
        self.load_settings_from_file()

        # Create main container
        self.main_container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # Setup UI
        self.setup_main_layout()

        # Start monitoring
        self.monitor = BatteryMonitor(self)
        self.monitor_thread = threading.Thread(target=self.monitor.run, daemon=True)
        self.monitor_thread.start()
        self.root.after(1000, self.check_theme_change)
        self.root.after(500, self.check_prompt_queue)

    def setup_main_layout(self):
        self.left_frame = ctk.CTkFrame(self.main_container, width=250, corner_radius=10)
        self.left_frame.pack(side="left", fill="y", padx=(0, 10))
        self.left_frame.pack_propagate(False)

        self.right_frame = ctk.CTkFrame(self.main_container, corner_radius=10)
        self.right_frame.pack(side="right", fill="both", expand=True)

        self.setup_left_panel()
        self.show_home_page()

    def setup_left_panel(self):
        user_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        user_frame.pack(fill="x", padx=15, pady=(15, 20))

        self.user_image_frame = ctk.CTkFrame(user_frame, width=80, height=80, corner_radius=40)
        self.user_image_frame.pack(pady=(0, 10))
        user_icon_label = ctk.CTkLabel(self.user_image_frame, text="👤", font=("Arial", 60))
        user_icon_label.place(relx=0.5, rely=0.5, anchor="center")

        if self.custom_logo_path and os.path.exists(self.custom_logo_path):
            try:
                logo_img = Image.open(self.custom_logo_path)
                logo_img = logo_img.resize((80, 80), Image.Resampling.LANCZOS)
                logo_photo = ImageTk.PhotoImage(logo_img)
                user_icon_label.configure(image=logo_photo, text="")
                user_icon_label.image = logo_photo
                logger.info(f"Custom logo loaded in left panel from {self.custom_logo_path}")
            except Exception as e:
                logger.error(f"Failed to load custom logo in left panel: {e}")

        self.name_label = ctk.CTkLabel(user_frame, text=getpass.getuser(), font=ctk.CTkFont(size=16, weight="bold"))
        self.name_label.pack()

        nav_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        nav_frame.pack(fill="x", padx=15, pady=10)

        self.system_diag_btn = ctk.CTkButton(nav_frame, text="System Diagnostics",
                                             command=self.show_system_diagnostics,
                                             height=40, font=ctk.CTkFont(size=14))
        self.system_diag_btn.pack(fill="x", pady=(0, 10))

        self.about_btn = ctk.CTkButton(nav_frame, text="About Save My Cell",
                                       command=self.show_about_page,
                                       height=40, font=ctk.CTkFont(size=14))
        self.about_btn.pack(fill="x")

        settings_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        settings_frame.pack(side="bottom", fill="x", padx=15, pady=15)

        self.settings_btn = ctk.CTkButton(settings_frame, text="⚙️", width=40, height=40,
                                          fg_color="transparent", hover_color="#e0e0e0",
                                          font=ctk.CTkFont(size=18), text_color="#979090",
                                          command=self.show_settings_page)
        self.settings_btn.pack(anchor="w", pady=5)

        self.stop_button = ctk.CTkButton(nav_frame, text="Minimize to Tray",
                                         command=self.minimize_to_tray,
                                         height=40, font=ctk.CTkFont(size=14),
                                         fg_color="#D83B01", hover_color="#A12D00")
        self.stop_button.pack(fill="x", pady=(10, 0))

    def clear_right_frame(self):
        for widget in self.right_frame.winfo_children():
            widget.destroy()

    def show_home_page(self):
        self.current_page = "home"
        self.clear_right_frame()

        home_content = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        home_content.pack(fill="both", expand=True, padx=20, pady=20)

        battery_frame = ctk.CTkFrame(home_content, fg_color="transparent", height=180, width=350)
        battery_frame.pack(pady=(20, 20))
        battery_frame.pack_propagate(False)

        battery_label = ctk.CTkLabel(battery_frame, text=f"{self.battery_percentage}%",
                                     font=ctk.CTkFont(size=110, weight="bold"),
                                     text_color="#2CC985")
        battery_label.place(relx=0.5, rely=0.5, anchor="center")
        self.battery_label = battery_label

        info_frame = ctk.CTkFrame(home_content, corner_radius=10)
        info_frame.place(relx=0.5, rely=0.6, anchor="center", relwidth=0.8)

        info_title = ctk.CTkLabel(info_frame, text="System Information",
                                  font=ctk.CTkFont(size=18, weight="bold"))
        info_title.pack(pady=(10, 10))

        battery = psutil.sensors_battery()
        battery_summary = [
            "Status: Charging" if battery and battery.power_plugged else "Status: Discharging",
            f"Power Plugged: {battery.power_plugged}" if battery else "Power Plugged: N/A",
            f"Time to Full Charge: {calculate_battery_time(battery)}" if battery and battery.power_plugged else "",
            f"Time to Complete Discharge: {calculate_battery_time(battery)}" if battery and not battery.power_plugged else ""
        ]
        self.battery_status_labels = []
        for item in battery_summary:
            if item:
                detail_label = ctk.CTkLabel(info_frame, text=item, font=ctk.CTkFont(size=14))
                detail_label.pack(pady=2)
                self.battery_status_labels.append(detail_label)

        ctk.CTkLabel(info_frame, text="").pack(pady=10)

    def create_header_with_back_button(self, title):
        header_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))

        back_btn = ctk.CTkButton(header_frame, text="←", command=self.show_home_page,
                                 width=40, height=40, fg_color="transparent",
                                 text_color="gray", hover_color="#e0e0e0",
                                 font=ctk.CTkFont(size=20))
        back_btn.pack(side="left")

        title_label = ctk.CTkLabel(header_frame, text=title,
                                   font=ctk.CTkFont(size=24, weight="bold"))
        title_label.pack(side="left", padx=(20, 0))

        return header_frame

    def show_system_diagnostics(self):
        self.current_page = "diagnostics"
        self.clear_right_frame()

        self.create_header_with_back_button("System Diagnostics")

        content_frame = ctk.CTkScrollableFrame(self.right_frame)
        content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        sections = get_diagnostic_sections()
        for section_title, items in sections:
            section_frame = ctk.CTkFrame(content_frame)
            section_frame.pack(fill="x", padx=20, pady=10)

            title_label = ctk.CTkLabel(section_frame, text=section_title,
                                       font=ctk.CTkFont(size=16, weight="bold"))
            title_label.pack(pady=(15, 10), anchor="w", padx=20)

            for item in items:
                item_label = ctk.CTkLabel(section_frame, text=f"• {item}",
                                          font=ctk.CTkFont(size=12), anchor="w")
                item_label.pack(pady=2, anchor="w", padx=40)

            ctk.CTkLabel(section_frame, text="").pack(pady=5)

    def show_about_page(self):
        self.current_page = "about"
        self.clear_right_frame()

        self.create_header_with_back_button("About Save My Cell")

        content_frame = ctk.CTkScrollableFrame(self.right_frame)
        content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        version_text = "Pro Version" if VERSION == "PRO" else "Free Version"
        about_text = f"""
Save My Cell - Battery Management Application

Version: MVP ({version_text})
Developer: Gideon Aniechi
Powered by: ValionTech

About This Application:
Save My Cell is a comprehensive battery management application designed to help you monitor, maintain, and optimize your device's battery performance. Our application provides real-time battery statistics, health monitoring, and intelligent power management features.

Key Features:
• Real-time battery percentage and status monitoring
• Advanced battery health diagnostics
• Power consumption analysis
• Charging optimization recommendations
• Custom power profiles
• Detailed usage statistics

Support:
For technical support, feature requests, or general inquiries, please contact our support team at support@savemycell.com or visit our website at www.savemycell.com.

Copyright © {time.strftime("%Y")} Save My Cell Team. All rights reserved.
        """
        text_label = ctk.CTkLabel(content_frame, text=about_text.strip(),
                                  font=ctk.CTkFont(size=12), justify="left", wraplength=500)
        text_label.pack(padx=20, pady=20, anchor="w")

    def show_settings_page(self):
        self.current_page = "settings"
        self.clear_right_frame()

        self.create_header_with_back_button("Settings")

        content_frame = ctk.CTkScrollableFrame(self.right_frame)
        content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        general_frame = ctk.CTkFrame(content_frame)
        general_frame.pack(fill="x", padx=20, pady=(10, 20))

        general_title = ctk.CTkLabel(general_frame, text="General",
                                     font=ctk.CTkFont(size=18, weight="bold"))
        general_title.pack(pady=(15, 15), anchor="w", padx=20)

        threshold_label = ctk.CTkLabel(general_frame, text="Unplug Threshold (%)",
                                       font=ctk.CTkFont(size=14))
        threshold_label.pack(anchor="w", padx=20, pady=(0, 5))
        self.threshold_var = tk.IntVar(value=self.unplug_threshold)

        def validate_threshold(value):
            try:
                val = int(value)
                return 1 <= val <= 100
            except ValueError:
                return False

        def on_threshold_change(*args):
            value = self.threshold_var.get()
            if validate_threshold(value):
                self.unplug_threshold = value
            else:
                self.threshold_var.set(self.unplug_threshold)

        self.threshold_entry = ctk.CTkEntry(general_frame, textvariable=self.threshold_var, width=80)
        self.threshold_entry.pack(anchor="w", padx=20, pady=(0, 10))
        self.threshold_var.trace_add("write", on_threshold_change)

        refresh_label = ctk.CTkLabel(general_frame, text="Refresh Interval (s)",
                                     font=ctk.CTkFont(size=14))
        refresh_label.pack(anchor="w", padx=20, pady=(0, 5))
        self.refresh_var = tk.IntVar(value=self.refresh_interval)
        self.refresh_entry = ctk.CTkEntry(general_frame, textvariable=self.refresh_var, width=80)
        self.refresh_entry.pack(anchor="w", padx=20, pady=(0, 10))
        if VERSION == "FREE":
            self.refresh_entry.configure(state="disabled")

        power_saving_label = ctk.CTkLabel(general_frame, text="Power Saving Mode",
                                          font=ctk.CTkFont(size=14))
        power_saving_label.pack(anchor="w", padx=20, pady=(0, 5))
        self.power_saving_var = tk.BooleanVar(value=self.power_saving_mode)
        power_saving_check = ctk.CTkCheckBox(general_frame, text="", variable=self.power_saving_var)
        power_saving_check.pack(anchor="w", padx=20, pady=(0, 10))

        custom_frame = ctk.CTkFrame(content_frame)
        custom_frame.pack(fill="x", padx=20, pady=(0, 20))

        custom_title = ctk.CTkLabel(custom_frame, text="Customization",
                                    font=ctk.CTkFont(size=18, weight="bold"))
        custom_title.pack(pady=(15, 15), anchor="w", padx=20)

        logo_label = ctk.CTkLabel(custom_frame, text="Custom Logo Path",
                                  font=ctk.CTkFont(size=14))
        logo_label.pack(anchor="w", padx=20, pady=(0, 5))
        self.logo_var = tk.StringVar(value=self.custom_logo_path)
        logo_entry = ctk.CTkEntry(custom_frame, textvariable=self.logo_var, width=200)
        logo_entry.pack(anchor="w", padx=20, pady=(0, 5))
        ctk.CTkButton(custom_frame, text="Browse",
                      command=lambda: self.logo_var.set(filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")])),
                      width=80).pack(anchor="w", padx=20, pady=(0, 10))

        theme_frame = ctk.CTkFrame(custom_frame, fg_color="transparent")
        theme_frame.pack(fill="x", padx=20, pady=(0, 20))

        mode_frame = ctk.CTkFrame(theme_frame, fg_color="transparent")
        mode_frame.pack(fill="x")

        self.theme_var = ctk.StringVar(value=self.appearance_mode)

        def select_light_mode(event=None):
            self.theme_var.set("light")
            self.change_appearance_mode("light")

        def select_dark_mode(event=None):
            self.theme_var.set("dark")
            self.change_appearance_mode("dark")

        light_preview_frame = ctk.CTkFrame(mode_frame, width=220, height=220, corner_radius=10,
                                           fg_color="#f7f7f7", border_width=1, border_color="#bdbdbd", cursor="hand2")
        light_preview_frame.pack(side="left", padx=(0, 40))
        light_preview_frame.pack_propagate(False)
        light_preview_frame.bind("<Button-1>", select_light_mode)

        ctk.CTkCanvas(light_preview_frame, width=200, height=200,
                      bg="#f7f7f7", highlightthickness=0, cursor="hand2").pack()
        canvas_light = light_preview_frame.winfo_children()[0]
        canvas_light.create_oval(30, 30, 70, 70, fill="#dddddd", outline="#dddddd")
        canvas_light.create_rectangle(30, 80, 110, 95, fill="#dddddd", outline="#dddddd")
        canvas_light.create_rectangle(30, 100, 110, 115, fill="#dddddd", outline="#dddddd")
        canvas_light.create_rectangle(120, 30, 190, 40, fill="#dddddd", outline="#dddddd")
        canvas_light.create_rectangle(120, 45, 190, 55, fill="#dddddd", outline="#dddddd")
        canvas_light.create_rectangle(120, 60, 190, 70, fill="#dddddd", outline="#dddddd")
        canvas_light.create_rectangle(30, 130, 190, 145, fill="#e0e0e0", outline="#e0e0e0")
        canvas_light.create_rectangle(30, 150, 190, 165, fill="#e0e0e0", outline="#e0e0e0")
        canvas_light.create_rectangle(30, 170, 190, 185, fill="#e0e0e0", outline="#e0e0e0")
        canvas_light.bind("<Button-1>", select_light_mode)

        dark_preview_frame = ctk.CTkFrame(mode_frame, width=220, height=220, corner_radius=10,
                                          fg_color="#232323", border_width=1, border_color="#232323", cursor="hand2")
        dark_preview_frame.pack(side="left", padx=(0, 0))
        dark_preview_frame.pack_propagate(False)
        dark_preview_frame.bind("<Button-1>", select_dark_mode)

        ctk.CTkCanvas(dark_preview_frame, width=200, height=200,
                      bg="#232323", highlightthickness=0, cursor="hand2").pack()
        canvas_dark = dark_preview_frame.winfo_children()[0]
        canvas_dark.create_oval(30, 30, 70, 70, fill="#bdbdbd", outline="#bdbdbd")
        canvas_dark.create_rectangle(30, 80, 110, 95, fill="#bdbdbd", outline="#bdbdbd")
        canvas_dark.create_rectangle(30, 100, 110, 115, fill="#bdbdbd", outline="#bdbdbd")
        canvas_dark.create_rectangle(120, 30, 190, 40, fill="#bdbdbd", outline="#bdbdbd")
        canvas_dark.create_rectangle(120, 45, 190, 55, fill="#bdbdbd", outline="#bdbdbd")
        canvas_dark.create_rectangle(120, 60, 190, 70, fill="#bdbdbd", outline="#bdbdbd")
        canvas_dark.create_rectangle(30, 130, 190, 145, fill="#444444", outline="#444444")
        canvas_dark.create_rectangle(30, 150, 190, 165, fill="#444444", outline="#444444")
        canvas_dark.create_rectangle(30, 170, 190, 185, fill="#444444", outline="#444444")
        canvas_dark.bind("<Button-1>", select_dark_mode)

        dark_radio = ctk.CTkRadioButton(mode_frame, text="Dark mode",
                                        variable=self.theme_var, value="dark",
                                        command=select_dark_mode,
                                        font=ctk.CTkFont(size=18, weight="bold"),
                                        text_color="#6c6c80")
        dark_radio.pack(side="left", pady=(10, 0))
        dark_radio.place(in_=dark_preview_frame, relx=0.5, rely=1.08, anchor="center")

        apply_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        apply_frame.pack(fill="x", padx=20, pady=20)

        apply_btn = ctk.CTkButton(apply_frame, text="Apply", width=100, height=35,
                                  command=self.apply_settings,
                                  font=ctk.CTkFont(size=14))
        apply_btn.pack(anchor="e")

    def change_appearance_mode(self, mode):
        self.appearance_mode = mode
        ctk.set_appearance_mode(mode)
        self.update_theme()

    def update_theme(self):
        if self.appearance_mode == "dark":
            self.background_color = "#2D2D2D"
            self.text_color = "#FFFFFF"
        else:
            self.background_color = "#F3F3F3"
            self.text_color = "#000000"
        self.root.configure(fg_color=self.background_color)

    def load_settings_from_file(self):
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
                self.background_color = ui_settings.get("background_color", "#F3F3F3")
                self.text_color = ui_settings.get("text_color", "#000000")
                self.appearance_mode = settings.get("appearance_mode", "light")
                self.change_appearance_mode(self.appearance_mode)
                logger.info(f"Settings loaded from {settings_file}: {settings}")
        except FileNotFoundError as e:
            logger.error(f"Failed to load settings due to file not found: {e}")
            messagebox.showerror("Error", f"Failed to load settings. Using defaults. Details: {e}")
            self.save_settings_to_file()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse settings file {settings_file}: {e}")
            messagebox.showerror("Error", f"Failed to load settings due to invalid JSON. Using defaults. Details: {e}")
            self.save_settings_to_file()
        except Exception as e:
            logger.error(f"Unexpected error loading settings from {settings_file}: {e}")
            messagebox.showerror("Error", f"Failed to load settings. Using defaults. Details: {e}")
            self.save_settings_to_file()
        if not is_auto_start_enabled():
            logger.info("Auto-start not enabled, enabling it now...")
            set_auto_start(True)

    def save_settings_to_file(self):
        try:
            settings = {
                "unplug_threshold": self.unplug_threshold,
                "refresh_interval": self.refresh_interval,
                "power_saving_mode": self.power_saving_mode,
                "appearance_mode": self.appearance_mode,
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

    def apply_settings(self):
        try:
            unplug_threshold = self.threshold_var.get()
            if not 1 <= unplug_threshold <= 100:
                messagebox.showerror("Error", "Unplug threshold must be between 1 and 100.")
                return
            if VERSION == "PRO":
                refresh_interval = self.refresh_var.get()
                if refresh_interval <= 0:
                    messagebox.showerror("Error", "Refresh interval must be greater than 0.")
                    return
                self.refresh_interval = refresh_interval
            self.unplug_threshold = unplug_threshold
            self.power_saving_mode = self.power_saving_var.get()
            self.custom_logo_path = self.logo_var.get().strip()
            if self.custom_logo_path and not os.path.exists(self.custom_logo_path):
                messagebox.showwarning("Warning", "Logo file not found. It won’t be displayed until a valid path is provided.")
            self.is_dark_mode = self.theme_var.get() == "dark"
            self.appearance_mode = "dark" if self.is_dark_mode else "light"
            self.save_settings_to_file()
            self.setup_left_panel()  # Refresh left panel for logo
            self.show_settings_confirmation()
        except ValueError as ve:
            messagebox.showerror("Error", str(ve))
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")

    def show_settings_confirmation(self):
        confirmation_window = ctk.CTkToplevel(self.root)
        confirmation_window.title("Settings Applied")
        confirmation_window.geometry("300x150")
        confirmation_window.resizable(False, False)

        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 150
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 75
        confirmation_window.geometry(f"+{x}+{y}")
        confirmation_window.transient(self.root)
        confirmation_window.grab_set()

        message_label = ctk.CTkLabel(confirmation_window,
                                     text="Settings have been applied successfully!",
                                     font=ctk.CTkFont(size=14))
        message_label.pack(expand=True, pady=(30, 10))

        ok_btn = ctk.CTkButton(confirmation_window, text="OK", width=80,
                               command=confirmation_window.destroy)
        ok_btn.pack(pady=(0, 20))

    def update_battery_ui(self, percent, plugged):
        self.battery_percentage = percent
        if self.current_page == "home" and hasattr(self, 'battery_label'):
            self.battery_label.configure(text=f"{percent:.0f}%")
            battery = psutil.sensors_battery()
            battery_summary = [
                "Status: Charging" if battery and battery.power_plugged else "Status: Discharging",
                f"Power Plugged: {battery.power_plugged}" if battery else "Power Plugged: N/A",
                f"Time to Full Charge: {calculate_battery_time(battery)}" if battery and battery.power_plugged else "",
                f"Time to Complete Discharge: {calculate_battery_time(battery)}" if battery and not battery.power_plugged else ""
            ]
            for i, label in enumerate(self.battery_status_labels):
                if i < len(battery_summary) and battery_summary[i]:
                    label.configure(text=battery_summary[i])

    def update_system_stats(self):
        pass

    def show_unplug_prompt(self):
        global UNPLUG_PROMPT_ACTIVE
        if UNPLUG_PROMPT_ACTIVE:
            logger.info("Unplug prompt already active, skipping.")
            return
        logger.info("Showing unplug prompt...")
        UNPLUG_PROMPT_ACTIVE = True
        self.unplug_window = ctk.CTkToplevel(self.root)
        self.unplug_window.title("Battery Full - Action Required")
        self.unplug_window.geometry("640x400")
        self.unplug_window.resizable(False, False)
        self.unplug_window.attributes('-topmost', True)
        self.unplug_window.configure(fg_color=self.background_color)

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

        main_frame = ctk.CTkFrame(self.unplug_window, fg_color="transparent")
        main_frame.place(relx=0.5, rely=0.5, anchor="center")

        row = 0
        if self.custom_logo_path and os.path.exists(self.custom_logo_path):
            try:
                logo_img = Image.open(self.custom_logo_path)
                target_size = 100
                ratio = min(target_size / logo_img.size[0], target_size / logo_img.size[1])
                new_width = int(logo_img.size[0] * ratio)
                new_height = int(logo_img.size[1] * ratio)
                logo_img = logo_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logo_photo = ImageTk.PhotoImage(logo_img)
                logo_label = ctk.CTkLabel(main_frame, image=logo_photo, text="")
                logo_label.image = logo_photo
                logo_label.pack(pady=(16, 8))
                row += 1
                logger.info(f"Custom logo loaded in unplug prompt from {self.custom_logo_path}")
            except Exception as e:
                logger.error(f"Failed to load custom logo in unplug prompt: {e}")

        prompt_label = ctk.CTkLabel(main_frame, text="Battery Full!\nPlease Unplug Charger",
                                    font=ctk.CTkFont(size=20, weight="bold"),
                                    text_color="#D83B01")
        prompt_label.pack(pady=(0 if row > 0 else 16, 8))

        info_label = ctk.CTkLabel(main_frame,
                                  text="Unplugging your charger when the battery is fully charged:\n"
                                       "- Extends battery lifespan by preventing overcharging.\n"
                                       "- Reduces energy waste and lowers your carbon footprint.\n"
                                       "- Protects your device from potential heat damage.",
                                  font=ctk.CTkFont(size=12), justify="center")
        info_label.pack(pady=(0, 16))

        self.countdown_label = ctk.CTkLabel(main_frame, text=f"Auto-close in {PROMPT_TIMEOUT}s",
                                            font=ctk.CTkFont(size=14, weight="bold"),
                                            text_color="#0078D4")
        self.countdown_label.pack(pady=(0, 16))

        def add_close_button():
            elapsed_time = time.time() - self.prompt_start_time
            if elapsed_time >= PROMPT_TIMEOUT and self.unplug_window.winfo_exists():
                close_button = ctk.CTkButton(main_frame, text="Close",
                                             command=self.close_unplug_prompt,
                                             width=100, height=35,
                                             font=ctk.CTkFont(size=14))
                close_button.pack(pady=(0, 16))
                logger.info("Close button added after timeout.")
                self.unplug_window.bind("<Escape>", lambda event: self.close_unplug_prompt())

        self.prompt_start_time = time.time()
        self.unplug_window.after(int(PROMPT_TIMEOUT * 1000), add_close_button)
        self.monitor_unplug()

    def close_unplug_prompt(self):
        global UNPLUG_PROMPT_ACTIVE
        if self.unplug_window and self.unplug_window.winfo_exists():
            if not self.power_saving_mode:
                for alpha in range(20, -1, -1):
                    self.unplug_window.attributes('-alpha', alpha / 20)
                    time.sleep(0.01)
            self.unplug_window.destroy()
            UNPLUG_PROMPT_ACTIVE = False
            logger.info("Unplug prompt closed manually.")

    def monitor_unplug(self):
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
                elapsed_time = time.time() - self.prompt_start_time
                if elapsed_time >= PROMPT_TIMEOUT:
                    self.countdown_label.configure(text="Auto-close in 0s")
                    logger.info("Countdown reached 0, waiting for manual close.")
                    if elapsed_time >= PROMPT_TIMEOUT + 30:
                        self.close_unplug_prompt()
                        logger.warning("Prompt stuck after timeout, force closing.")
                        return
                else:
                    remaining = max(0, PROMPT_TIMEOUT - int(elapsed_time))
                    self.countdown_label.configure(text=f"Auto-close in {remaining}s")
                    self.unplug_window.after(500, self.monitor_unplug)
        except Exception as e:
            logger.error(f"Error in monitor_unplug: {e}")
            if self.unplug_window.winfo_exists():
                self.unplug_window.after(500, self.monitor_unplug)

    def check_prompt_queue(self):
        try:
            if not PROMPT_QUEUE.empty():
                PROMPT_QUEUE.get_nowait()
                battery = psutil.sensors_battery()
                if battery and battery.percent >= self.unplug_threshold and battery.power_plugged and not UNPLUG_PROMPT_ACTIVE:
                    self.show_unplug_prompt()
        except queue.Empty:
            pass
        self.root.after(500, self.check_prompt_queue)

    def minimize_to_tray(self):
        global MINIMIZED_TO_TRAY
        logger.info("Minimizing to tray...")
        MINIMIZED_TO_TRAY = True
        if not self.power_saving_mode:
            for alpha in range(20, -1, -1):
                self.root.attributes('-alpha', alpha / 20)
                time.sleep(0.01)
        self.root.withdraw()
        if self.tray:
            self.tray.update_menu()
        logger.info("Minimized to tray successfully.")

    def show_main_screen(self):
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
            if not self.power_saving_mode:
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
        self.show_home_page()
        battery = psutil.sensors_battery()
        self.update_battery_ui(battery.percent if battery else 0,
                               battery.power_plugged if battery else False)
        self.update_system_stats()
        logger.info("Main screen displayed.")

    def check_unplug_prompt_on_restore(self):
        logger.info("Checking for unplug prompt on restore...")
        battery = psutil.sensors_battery()
        if battery and battery.percent >= self.unplug_threshold and battery.power_plugged:
            self.show_unplug_prompt()
        else:
            logger.info("No unplug prompt needed on restore.")

    def check_theme_change(self):
        new_theme = darkdetect.isDark()
        if new_theme != self.is_dark_mode:
            self.is_dark_mode = new_theme
            self.appearance_mode = "dark" if new_theme else "light"
            self.change_appearance_mode(self.appearance_mode)
            self.show_main_screen()
        self.root.after(1000, self.check_theme_change)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = BatteryMonitorApp()
    app.run()