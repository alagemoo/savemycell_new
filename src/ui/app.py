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

import tkinter as tk
from tkinter import ttk
import psutil
from src.ui.screens import build_main_screen, show_unplug_prompt, show_alt_screen, show_settings
from src.ui.styles import update_theme, check_theme_change, configure_styles
from src.core.monitor import BatteryMonitor
from src.core.tray import create_tray_icon
from src.config.settings import load_settings_from_file

class BatteryMonitorApp:
    def __init__(self, root, unplug_threshold=90, refresh_interval=120):
        self.root = root
        self.root.title("Save My Cell")
        self.root.geometry(f"400x500")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Initialize settings and theme
        self.unplug_threshold = unplug_threshold
        self.refresh_interval = refresh_interval
        self.power_saving_mode = False
        self.background_color = "#F3F3F3"
        self.font_type = "Segoe UI Variable" if "Segoe UI Variable" in tkfont.families() else "Segoe UI"
        self.text_color = "#000000"
        self.custom_logo_path = ""
        self.accent_color = "#0078D4"
        self.is_dark_mode = darkdetect.isDark()
        self.secondary_bg = "#E6E6E6"
        self.minimized_to_tray = False  # Moved MINIMIZED_TO_TRAY to instance variable
        update_theme(self)
        load_settings_from_file(self)

        # Apply acrylic effect
        self.root.attributes('-alpha', 0.95)
        self.root.wm_attributes('-transparentcolor', 'gray')

        # Main UI setup
        self.main_frame = ttk.Frame(self.root, style="Main.TFrame")
        self.alt_frame = None
        self.battery_label = None
        self.battery_status = None
        self.battery_time = None
        self.details_button = None
        self.about_button = None
        self.stop_button = None
        self.settings_button = None
        self.unplug_window = None
        self.main_frame_prompt = None
        self.alt_title = None
        self.alt_text = None
        self.back_button = None
        self.prompt_start_time = 0

        # System tray and monitoring
        self.tray, self.tray_thread = create_tray_icon(self)
        self.tray_thread.start()
        self.monitor = BatteryMonitor(self)
        self.monitor_thread = threading.Thread(target=self.monitor.run, daemon=True)
        self.monitor_thread.start()

        # Build UI
        build_main_screen(self)
        self.check_prompt_queue()

        # Monitor theme changes
        self.root.after(1000, lambda: check_theme_change(self))

    def check_prompt_queue(self):
        from src.core.utils import PROMPT_QUEUE, UNPLUG_PROMPT_ACTIVE, logger
        try:
            if not PROMPT_QUEUE.empty():
                PROMPT_QUEUE.get_nowait()
                battery = psutil.sensors_battery()
                if battery and battery.percent >= self.unplug_threshold and battery.power_plugged and not UNPLUG_PROMPT_ACTIVE:
                    show_unplug_prompt(self)
        except queue.Empty:
            pass
        self.root.after(500, self.check_prompt_queue)

    def show_main_screen(self):
        from src.core.utils import logger
        logger.info("Showing main screen...")
        if self.alt_frame:
            self.alt_frame.pack_forget()
        self.main_frame.pack(fill="both", expand=True, padx=16, pady=16)
        self.root.deiconify()
        self.update_ui(psutil.sensors_battery().percent if psutil.sensors_battery() else 0,
                       psutil.sensors_battery().power_plugged if psutil.sensors_battery() else False)
        self.update_system_stats()
        logger.info("Main screen displayed.")

    def check_unplug_prompt_on_restore(self):
        from src.core.utils import logger
        logger.info("Checking for unplug prompt on restore...")
        battery = psutil.sensors_battery()
        if battery and battery.percent >= self.unplug_threshold and battery.power_plugged:
            show_unplug_prompt(self)
        else:
            logger.info("No unplug prompt needed on restore.")

    def update_ui(self, percent: float, plugged: bool):
        from src.core.utils import calculate_battery_time
        if self.battery_label:
            self.battery_label.config(text=f"{percent:.0f}%")
            self.battery_status.config(text="Charging" if plugged else "Discharging")
            self.battery_time.config(text=calculate_battery_time(psutil.sensors_battery()))

    def update_system_stats(self):
        pass

    def show_details(self):
        from src.core.utils import get_system_details
        details = get_system_details()
        details_text = "\n".join(f"{key}: {value}" for key, value in details.items())
        show_alt_screen(self, "System Diagnostics", details_text)

    def show_about(self):
        version_text = "Pro Version" if "PRO" == "PRO" else "Free Version"
        about_text = f"Save My Cell\nDeveloped by: Gideon Aniechi\nVersion: MVP ({version_text})\nPowered by ValionTech"
        show_alt_screen(self, "About Save My Cell", about_text)

    def show_settings(self):
        show_settings(self)

    def minimize_to_tray(self):
        from src.core.utils import logger
        logger.info("Minimizing to tray...")
        self.minimized_to_tray = True  # Updated to use instance variable
        logger.info(f"self.minimized_to_tray set to: {self.minimized_to_tray}")
        for alpha in range(20, -1, -1):
            self.root.attributes('-alpha', alpha / 20)
            self.root.update()
            time.sleep(0.01)
        self.root.withdraw()
        if self.tray:
            self.tray.update_menu()
        logger.info("Minimized to tray successfully.")