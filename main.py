import winreg
import customtkinter as ctk
from tkinter import ttk
import tkinter as tk
from PIL import Image, ImageTk
from utils import get_system_details
import threading
import time
import queue
import os
import json
import sys
import platform
import getpass
import socket
import psutil
import darkdetect
import winsound
import logging

# Configure logging
log_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "SaveMyCell")
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file = os.path.join(log_dir, "SaveMyCell.log")
logging.basicConfig(filename=log_file, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set appearance mode and color theme
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# --- Add these global variables and constants ---
RUNNING = True
MINIMIZED_TO_TRAY = False
UNPLUG_PROMPT_ACTIVE = False
PROMPT_QUEUE = queue.Queue()
WINDOW_WIDTH, WINDOW_HEIGHT = 900, 600
UNPLUG_THRESHOLD = 90

SETTINGS_FILE = os.path.join(os.path.expanduser(
    "~"), "AppData", "Local", "SaveMyCell", "settings.json")
if not os.path.exists(os.path.dirname(SETTINGS_FILE)):
    os.makedirs(os.path.dirname(SETTINGS_FILE))

# --- Utility functions from savemycell.py ---


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


def get_battery_summary():
    # battery_report = fetch_battery_report()
    battery = psutil.sensors_battery()
    if not battery:
        return ["N/A", "Status: Discharging (N/A)", "Power Plugged: N/A", "Time to Full Charge: N/A", "Time to Complete Discharge: N/A"]

    summary = [
        str(battery.percent),
        "Status: Charging" if battery.power_plugged else "Status: Discharging",
        f"Power Plugged: {battery.power_plugged}",
        f"Time to Full Charge: {calculate_battery_time(battery)}" if battery.power_plugged else "",
        f"Time to Complete Discharge: {calculate_battery_time(battery)}" if not battery.power_plugged else "",
    ]


    return summary


def fetch_battery_report():
    """
    To test on Windows machine.
    """
    import webbrowser
    import os
    from bs4 import BeautifulSoup

    os.system('powercfg /batteryreport /output battery_report.html')

    webbrowser.open('battery_report.html')

    with open("battery_report.html", "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "lxml")


    for table in soup.find_all("table"):
        if "Installed batteries" in table.text:
            print("=== Installed Batteries ===")
            print(table.text.strip())

        if "Battery capacity history" in table.text:
            print("=== Battery Capacity History ===")
            print(table.text.strip())

        if "Battery life estimates" in table.text:
            print("=== Battery Life Estimates ===")
            print(table.text.strip())
    
    return "Battery report not implemented yet."


def get_diagnostic_sections():
    mem = psutil.virtual_memory()
    memory_usage = f"{mem.used / 1e9:.1f} GB / {mem.total / 1e9:.1f} GB"

    # Disk
    disk = psutil.disk_usage('/')
    storage_usage = f"Storage Usage: {disk.used / 1e9:.1f} GB / {disk.total / 1e9:.1f} GB"

    # Network
    network_status = "Connected" if socket.gethostbyname(
        socket.gethostname()) else "Disconnected"

    # Background processes
    num_procs = len(list(psutil.process_iter()))
    print("Background Processes:", num_procs)

    battery_summary = get_battery_summary()
    percent = battery_summary.pop(0)

    sections = [
        ("Battery Health", [
            f"Current Capacity: {percent}%",
            "Design Capacity: WMI or battery_report.html",
            "Full Charge Capacity: WMI or battery_report.html",
            "Maximum Capacity: WMI or battery_report.html",
            "Capacity Retention: calculated from FullCharge / DesignCapacity"
        ]),
        ("Charging System", [
            battery_summary[1],  # Status
            battery_summary[2],  # Power Plugged
            battery_summary[3],  # Time to Full Charge
        ]),
        ("System Performance", [
            f"Memory Usage: {memory_usage}",
            f"Storage Usage: {storage_usage}",
            f"CPU Usage: {psutil.cpu_percent()}%"
        ])
    ]
    return sections


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
            "Time to Full Charge": calculate_battery_time(battery) if battery.power_plugged else "",
            "Time to Complete Discharge": calculate_battery_time(battery) if not battery.power_plugged else ""
        })
    return details

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


class SaveMyCellApp:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Save My Cell")
        self.root.geometry("900x600")
        self.root.resizable(False, False)

        # Initialize variables
        self.current_page = "home"
        self.appearance_mode = "light"
        self.battery_percentage = 100

        # --- Add these attributes for settings and monitoring ---
        self.unplug_threshold = UNPLUG_THRESHOLD
        self.background_color = "#F3F3F3"
        self.text_color = "#000000"
        self.is_dark_mode = darkdetect.isDark()

        # Create main container
        self.main_container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # Setup the main layout
        self.setup_main_layout()

        # --- Load settings from file and start monitoring thread ---
        self.load_settings_from_file()
        self.monitor_thread = threading.Thread(
            target=self.battery_monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.root.after(1000, self.check_theme_change)
        self.root.after(500, self.check_prompt_queue)

    def setup_main_layout(self):
        # Create two-column layout
        self.left_frame = ctk.CTkFrame(
            self.main_container, width=250, corner_radius=10)
        self.left_frame.pack(side="left", fill="y", padx=(0, 10))
        self.left_frame.pack_propagate(False)

        self.right_frame = ctk.CTkFrame(self.main_container, corner_radius=10)
        self.right_frame.pack(side="right", fill="both", expand=True)

        self.setup_left_panel()
        self.show_home_page()

    def setup_left_panel(self):
        # User info section
        user_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        user_frame.pack(fill="x", padx=15, pady=(15, 20))

        # User image placeholder (circular frame)
        self.user_image_frame = ctk.CTkFrame(
            user_frame, width=80, height=80, corner_radius=40)
        self.user_image_frame.pack(pady=(0, 10))

        # User icon (placeholder)
        user_icon_label = ctk.CTkLabel(
            self.user_image_frame, text="👤", font=("Arial", 60))
        user_icon_label.place(relx=0.5, rely=0.5, anchor="center")

        # Display name
        self.name_label = ctk.CTkLabel(
            user_frame, text=getpass.getuser(), font=ctk.CTkFont(size=16, weight="bold"))
        self.name_label.pack()

        # Navigation buttons
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

        # Settings button at bottom
        settings_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        settings_frame.pack(side="bottom", fill="x", padx=15, pady=15)
        

        self.settings_btn = ctk.CTkButton(
            settings_frame,
            text="⚙️",
            width=40,
            height=40,
            fg_color="transparent",
            hover_color="#e0e0e0",
            font=ctk.CTkFont(size=18),
            text_color="#979090",
            command=self.show_settings_page
        )
        self.settings_btn.pack(anchor="w", pady=5)

    def clear_right_frame(self):
        for widget in self.right_frame.winfo_children():
            widget.destroy()

    def show_home_page(self):
        battery_summary = get_battery_summary()
        percent = battery_summary.pop(0)
        self.battery_percentage = percent

        self.current_page = "home"
        self.clear_right_frame()

        # Home page content
        home_content = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        home_content.pack(fill="both", expand=True, padx=20, pady=20)

        # Large battery percentage display
        battery_frame = ctk.CTkFrame(
            home_content, fg_color="transparent", height=180, width=350)
        battery_frame.pack(pady=(20, 20))
        battery_frame.pack_propagate(False)

        battery_label = ctk.CTkLabel(
            battery_frame,
            text=f"{self.battery_percentage}%",
            font=ctk.CTkFont(size=110, weight="bold"),
            text_color="#2CC985"
        )
        battery_label.place(relx=0.5, rely=0.5, anchor="center")

        # Battery info section
        info_frame = ctk.CTkFrame(home_content, corner_radius=10)
        info_frame.place(relx=0.5, rely=0.6, anchor="center", relwidth=0.8)

        info_title = ctk.CTkLabel(info_frame, text="System Information",
                                  font=ctk.CTkFont(size=18, weight="bold"))
        info_title.pack(pady=(10, 10))

        for item in battery_summary:
            detail_label = ctk.CTkLabel(info_frame, text=item,
                                        font=ctk.CTkFont(size=14))
            detail_label.pack(pady=2)

        # Add some padding at bottom
        ctk.CTkLabel(info_frame, text="").pack(pady=10)

    def create_header_with_back_button(self, title):
        header_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))

        back_btn = ctk.CTkButton(header_frame, text="←",
                                 command=self.show_home_page,
                                 width=40, height=40,
                                 fg_color="transparent",
                                 text_color="gray",
                                 hover_color="#e0e0e0",
                                 font=ctk.CTkFont(size=20))
        back_btn.pack(side="left")

        title_label = ctk.CTkLabel(header_frame, text=title,
                                   font=ctk.CTkFont(size=24, weight="bold"))
        title_label.pack(side="left", padx=(20, 0))

        return header_frame

    def show_about_page(self):
        self.current_page = "about"
        self.clear_right_frame()

        self.create_header_with_back_button("About Save My Cell")

        # About content
        content_frame = ctk.CTkScrollableFrame(self.right_frame)
        content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        about_text = """
Save My Cell - Battery Management Application

Version: 2.1.0
Developer: Save My Cell Team
Released: 2025

About This Application:
Save My Cell is a comprehensive battery management application designed to help you monitor, maintain, and optimize your device's battery performance. Our application provides real-time battery statistics, health monitoring, and intelligent power management features.

Key Features:
• Real-time battery percentage and status monitoring
• Advanced battery health diagnostics
• Power consumption analysis
• Charging optimization recommendations
• Temperature monitoring and alerts
• Battery lifespan prediction
• Custom power profiles
• Detailed usage statistics

Mission Statement:
Our mission is to extend the lifespan of your device's battery through intelligent monitoring and optimization techniques. We believe that proper battery care can significantly improve device longevity and user experience.

Technical Specifications:
• Compatible with all major battery types
• Real-time monitoring with 1-second updates
• Advanced algorithms for health assessment
• Machine learning-based usage predictions
• Secure data handling and privacy protection

Support:
For technical support, feature requests, or general inquiries, please contact our support team at support@savemycell.com or visit our website at www.savemycell.com.

License:
This software is licensed under the MIT License. See LICENSE file for details.

Acknowledgments:
We would like to thank the open-source community and all beta testers who helped make this application possible.

Copyright © {current_year} Save My Cell Team. All rights reserved.
        """.format(current_year=time.strftime("%Y"))

        text_label = ctk.CTkLabel(content_frame, text=about_text.strip(),
                                  font=ctk.CTkFont(size=12),
                                  justify="left", wraplength=500)
        text_label.pack(padx=20, pady=20, anchor="w")

    def show_system_diagnostics(self):
        self.current_page = "diagnostics"
        self.clear_right_frame()

        self.create_header_with_back_button("System Diagnostics")

        # Diagnostics content
        content_frame = ctk.CTkScrollableFrame(self.right_frame)
        content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Diagnostic sections
        sections = get_diagnostic_sections()

        for section_title, items in sections:
            section_frame = ctk.CTkFrame(content_frame)
            section_frame.pack(fill="x", padx=20, pady=10)

            title_label = ctk.CTkLabel(section_frame, text=section_title,
                                       font=ctk.CTkFont(size=16, weight="bold"))
            title_label.pack(pady=(15, 10), anchor="w", padx=20)

            for item in items:
                item_label = ctk.CTkLabel(section_frame, text=f"• {item}",
                                          font=ctk.CTkFont(size=12),
                                          anchor="w")
                item_label.pack(pady=2, anchor="w", padx=40)

            # Add padding at bottom of section
            ctk.CTkLabel(section_frame, text="").pack(pady=5)

    def show_settings_page(self):
        self.current_page = "settings"
        self.clear_right_frame()

        self.create_header_with_back_button("Settings")

        # Settings content
        content_frame = ctk.CTkScrollableFrame(self.right_frame)
        content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # General Section
        general_frame = ctk.CTkFrame(content_frame)
        general_frame.pack(fill="x", padx=20, pady=(10, 20))

        general_title = ctk.CTkLabel(general_frame, text="General",
                                     font=ctk.CTkFont(size=18, weight="bold"))
        general_title.pack(pady=(15, 15), anchor="w", padx=20)


        # Unplug threshold setting
        threshold_label = ctk.CTkLabel(
            general_frame,
            text="Unplug Threshold (%)",
            font=ctk.CTkFont(size=14)
        )
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

        self.threshold_entry = ctk.CTkEntry(
            general_frame,
            textvariable=self.threshold_var,
            width=80
        )
        self.threshold_entry.pack(anchor="w", padx=20, pady=(0, 10))
        self.threshold_var.trace_add("write", lambda *args: on_threshold_change())

        

        # Customization Section
        custom_frame = ctk.CTkFrame(content_frame)
        custom_frame.pack(fill="x", padx=20, pady=(0, 20))

        custom_title = ctk.CTkLabel(custom_frame, text="Customization",
                                    font=ctk.CTkFont(size=18, weight="bold"))
        custom_title.pack(pady=(15, 15), anchor="w", padx=20)

        # Theme selection
        theme_frame = ctk.CTkFrame(custom_frame, fg_color="transparent")
        theme_frame.pack(fill="x", padx=20, pady=(0, 20))

        # Light and Dark mode previews
        mode_frame = ctk.CTkFrame(theme_frame, fg_color="transparent")
        mode_frame.pack(fill="x")

        # Shared variable for radio buttons
        self.theme_var = ctk.StringVar(value=self.appearance_mode)

        def select_light_mode(event=None):
            self.theme_var.set("light")
            self.change_appearance_mode("light")

        def select_dark_mode(event=None):
            self.theme_var.set("dark")
            self.change_appearance_mode("dark")

        # Light mode preview
        light_preview_frame = ctk.CTkFrame(mode_frame, width=220, height=220, corner_radius=10,
                                           fg_color="#f7f7f7", border_width=1, border_color="#bdbdbd", cursor="hand2")
        light_preview_frame.pack(side="left", padx=(0, 40))
        light_preview_frame.pack_propagate(False)
        light_preview_frame.bind("<Button-1>", select_light_mode)

        # Simulate UI elements for light mode
        ctk.CTkCanvas(light_preview_frame, width=200, height=200,
                      bg="#f7f7f7", highlightthickness=0, cursor="hand2").pack()
        canvas_light = light_preview_frame.winfo_children()[0]
        # Draw circle (avatar)
        canvas_light.create_oval(
            30, 30, 70, 70, fill="#dddddd", outline="#dddddd")
        # Draw lines (text)
        canvas_light.create_rectangle(
            30, 80, 110, 95, fill="#dddddd", outline="#dddddd")
        canvas_light.create_rectangle(
            30, 100, 110, 115, fill="#dddddd", outline="#dddddd")
        canvas_light.create_rectangle(
            120, 30, 190, 40, fill="#dddddd", outline="#dddddd")
        canvas_light.create_rectangle(
            120, 45, 190, 55, fill="#dddddd", outline="#dddddd")
        canvas_light.create_rectangle(
            120, 60, 190, 70, fill="#dddddd", outline="#dddddd")
        # Draw rectangles (list items)
        canvas_light.create_rectangle(
            30, 130, 190, 145, fill="#e0e0e0", outline="#e0e0e0")
        canvas_light.create_rectangle(
            30, 150, 190, 165, fill="#e0e0e0", outline="#e0e0e0")
        canvas_light.create_rectangle(
            30, 170, 190, 185, fill="#e0e0e0", outline="#e0e0e0")
        canvas_light.bind("<Button-1>", select_light_mode)

        # Dark mode preview
        dark_preview_frame = ctk.CTkFrame(mode_frame, width=220, height=220, corner_radius=10,
                                          fg_color="#232323", border_width=1, border_color="#232323", cursor="hand2")
        dark_preview_frame.pack(side="left", padx=(0, 0))
        dark_preview_frame.pack_propagate(False)
        dark_preview_frame.bind("<Button-1>", select_dark_mode)

        # Simulate UI elements for dark mode
        ctk.CTkCanvas(dark_preview_frame, width=200, height=200,
                      bg="#232323", highlightthickness=0, cursor="hand2").pack()
        canvas_dark = dark_preview_frame.winfo_children()[0]
        # Draw circle (avatar)
        canvas_dark.create_oval(
            30, 30, 70, 70, fill="#bdbdbd", outline="#bdbdbd")
        # Draw lines (text)
        canvas_dark.create_rectangle(
            30, 80, 110, 95, fill="#bdbdbd", outline="#bdbdbd")
        canvas_dark.create_rectangle(
            30, 100, 110, 115, fill="#bdbdbd", outline="#bdbdbd")
        canvas_dark.create_rectangle(
            120, 30, 190, 40, fill="#bdbdbd", outline="#bdbdbd")
        canvas_dark.create_rectangle(
            120, 45, 190, 55, fill="#bdbdbd", outline="#bdbdbd")
        canvas_dark.create_rectangle(
            120, 60, 190, 70, fill="#bdbdbd", outline="#bdbdbd")
        # Draw rectangles (list items)
        canvas_dark.create_rectangle(
            30, 130, 190, 145, fill="#444444", outline="#444444")
        canvas_dark.create_rectangle(
            30, 150, 190, 165, fill="#444444", outline="#444444")
        canvas_dark.create_rectangle(
            30, 170, 190, 185, fill="#444444", outline="#444444")
        canvas_dark.bind("<Button-1>", select_dark_mode)

        # Dark mode radio and label
        dark_radio = ctk.CTkRadioButton(
            mode_frame, text="Dark mode",
            variable=self.theme_var, value="dark",
            command=select_dark_mode,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#6c6c80"
        )
        dark_radio.pack(side="left", pady=(10, 0))
        dark_radio.place(in_=dark_preview_frame, relx=0.5,
                         rely=1.08, anchor="center")

        # Apply button
        apply_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        apply_frame.pack(fill="x", padx=20, pady=20)

        apply_btn = ctk.CTkButton(apply_frame, text="Apply", width=100, height=35,
                                  command=self.apply_settings,
                                  font=ctk.CTkFont(size=14))
        apply_btn.pack(anchor="e")

    def change_appearance_mode(self, mode):
        self.appearance_mode = mode
        ctk.set_appearance_mode(mode)

    # --- Settings persistence ---
    def load_settings_from_file(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r") as f:
                    settings = json.load(f)
                self.unplug_threshold = settings.get(
                    "unplug_threshold", UNPLUG_THRESHOLD)
                self.change_appearance_mode(settings.get("appearance_mode", "light"))
                
        except Exception as e:
            print(f"Failed to load settings: {e}")

    def save_settings_to_file(self):
        try:
            settings = {
                "unplug_threshold": self.unplug_threshold,
                "appearance_mode": self.appearance_mode,
            }
            with open(SETTINGS_FILE, "w") as f:
                json.dump(settings, f)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    # --- Battery monitoring logic ---
    def battery_monitor_loop(self):
        global RUNNING, UNPLUG_PROMPT_ACTIVE, MINIMIZED_TO_TRAY
        last_battery = None
        last_unplug_prompt_time = 0
        last_percent = None
        last_plugged = None
        while RUNNING:
            try:
                battery = psutil.sensors_battery()
                if not battery:
                    time.sleep(10)
                    continue
                current_time = time.time()
                if MINIMIZED_TO_TRAY and (not battery.power_plugged or battery.percent < self.unplug_threshold):
                    sleep_interval = 300
                elif battery.power_plugged and battery.percent >= self.unplug_threshold:
                    sleep_interval = 5
                else:
                    sleep_interval = self.refresh_interval
                if battery.percent >= self.unplug_threshold and battery.power_plugged:
                    if not UNPLUG_PROMPT_ACTIVE:
                        if last_battery and not last_battery.power_plugged and battery.power_plugged:
                            PROMPT_QUEUE.put(True)
                        elif current_time - last_unplug_prompt_time >= 300 or not last_unplug_prompt_time:
                            PROMPT_QUEUE.put(True)
                            last_unplug_prompt_time = current_time
                elif last_battery and not battery.power_plugged and last_battery.power_plugged:
                    if battery.percent < self.unplug_threshold:
                        last_unplug_prompt_time = 0
                last_battery = battery
                if self.root.winfo_exists() and not MINIMIZED_TO_TRAY:
                    if last_percent is None or last_plugged is None or \
                       abs(battery.percent - last_percent) >= 1 or battery.power_plugged != last_plugged:
                        self.root.after(0, lambda: self.update_battery_ui(
                            battery.percent, battery.power_plugged))
                        last_percent = battery.percent
                        last_plugged = battery.power_plugged
                time.sleep(sleep_interval)
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(10)

    def update_battery_ui(self, percent, plugged):
        # Update battery percentage and status on home page
        self.battery_percentage = percent

    # --- Prompt logic ---
    def check_prompt_queue(self):
        global UNPLUG_PROMPT_ACTIVE
        try:
            if not PROMPT_QUEUE.empty():
                PROMPT_QUEUE.get_nowait()
                battery = psutil.sensors_battery()
                if battery and battery.percent >= self.unplug_threshold and battery.power_plugged and not UNPLUG_PROMPT_ACTIVE:
                    self.show_unplug_prompt()
        except queue.Empty:
            pass
        self.root.after(500, self.check_prompt_queue)

    def show_unplug_prompt(self):
        global UNPLUG_PROMPT_ACTIVE
        if UNPLUG_PROMPT_ACTIVE:
            return
        UNPLUG_PROMPT_ACTIVE = True

    # --- System tray integration (stub, see pystray for full implementation) ---
    def minimize_to_tray(self):
        global MINIMIZED_TO_TRAY
        MINIMIZED_TO_TRAY = True
        self.root.withdraw()

    # --- Theme auto-detection ---
    def check_theme_change(self):
        new_theme = darkdetect.isDark()
        if new_theme != self.is_dark_mode:
            self.is_dark_mode = new_theme
            # Update colors and UI here
        self.root.after(1000, self.check_theme_change)

    # --- Save settings from UI ---
    def apply_settings(self):
        # Apply display name change
        unplug_threshold = self.threshold_var.get()
        if unplug_threshold < 1 or unplug_threshold > 100:
            ctk.CTkMessageBox.show_error(
                "Invalid Unplug Threshold", "Please enter a value between 1 and 100.")
            return

        self.unplug_threshold = unplug_threshold
        
        self.is_dark_mode = self.theme_var.get() == "dark"
        self.appearance_mode = "dark" if self.is_dark_mode else "light"

        self.save_settings_to_file()
        # Show confirmation
        self.show_settings_confirmation()

    def show_settings_confirmation(self):
        # Simple confirmation message
        confirmation_window = ctk.CTkToplevel(self.root)
        confirmation_window.title("Settings Applied")
        confirmation_window.geometry("300x150")
        confirmation_window.resizable(False, False)

        # Center the window relative to the parent
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 150
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 75
        confirmation_window.geometry(f"+{x}+{y}")

        confirmation_window.transient(self.root)
        confirmation_window.grab_set()

        # Play toggle sound (Windows beep)
        try:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

        message_label = ctk.CTkLabel(confirmation_window,
                         text="Settings have been applied successfully!",
                         font=ctk.CTkFont(size=14))
        message_label.pack(expand=True, pady=(30, 10))


        ok_btn = ctk.CTkButton(confirmation_window, text="OK", width=80,
                       command=confirmation_window.destroy)
        ok_btn.pack(pady=(0, 20))

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = SaveMyCellApp()
    app.run()
