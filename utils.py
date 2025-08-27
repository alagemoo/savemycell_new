import getpass
import os
import json
import logging
import platform
import socket
import sys
from tkinter import messagebox
from typing import Dict, Optional
import winreg

import psutil
try:
    import win32api
    import win32con
except ImportError:
    win32api = None
    win32con = None

logger = logging.getLogger(__name__)

def save_settings_to_file(settings, log_dir):
    """Save settings, including UI customizations, to a JSON file."""
    try:
        with open(os.path.join(log_dir, "settings.json"), "w") as f:
            json.dump(settings, f)
        logger.info(f"Settings saved to settings.json: {settings}")
        return True
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        messagebox.showerror("Error", "Failed to save settings. Check logs for details.")
        return False

def load_settings_from_file(log_dir, defaults, update_theme=None, configure_styles=None, is_auto_start_enabled=None, set_auto_start=None):
    """Load settings, including UI customizations, from a JSON file."""
    settings_file = os.path.join(log_dir, "settings.json")
    settings = defaults.copy()
    try:
        if not os.path.exists(settings_file):
            logger.warning(f"Settings file not found at {settings_file}. Using defaults.")
            raise FileNotFoundError(f"Settings file not found at {settings_file}")

        with open(settings_file, "r") as f:
            loaded = json.load(f)
            settings["unplug_threshold"] = loaded.get("unplug_threshold", defaults["unplug_threshold"])
            settings["refresh_interval"] = loaded.get("refresh_interval", defaults["refresh_interval"])
            settings["power_saving_mode"] = loaded.get("power_saving_mode", defaults["power_saving_mode"])
            ui_settings = loaded.get("ui_settings", {})
            settings["custom_logo_path"] = ui_settings.get("custom_logo_path", defaults["custom_logo_path"])
            settings["background_color"] = ui_settings.get("background_color", defaults["background_color"])
            settings["text_color"] = ui_settings.get("text_color", defaults["text_color"])
            if update_theme:
                update_theme(settings)
            if configure_styles:
                configure_styles(settings)
            logger.info(f"Settings loaded from {settings_file}: {loaded}")
    except FileNotFoundError as e:
        logger.error(f"Failed to load settings due to file not found: {e}")
        messagebox.showerror("Error", f"Failed to load settings. Using defaults. Details: {e}")
        if update_theme:
            update_theme(settings)
        if configure_styles:
            configure_styles(settings)
        save_settings_to_file(settings, log_dir)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse settings file {settings_file}: {e}")
        messagebox.showerror("Error", f"Failed to load settings due to invalid JSON. Using defaults. Details: {e}")
        if update_theme:
            update_theme(settings)
        if configure_styles:
            configure_styles(settings)
        save_settings_to_file(settings, log_dir)
    except Exception as e:
        logger.error(f"Unexpected error loading settings from {settings_file}: {e}")
        messagebox.showerror("Error", f"Failed to load settings. Using defaults. Details: {e}")
        if update_theme:
            update_theme(settings)
        if configure_styles:
            configure_styles(settings)
        save_settings_to_file(settings, log_dir)
    if is_auto_start_enabled and set_auto_start and not is_auto_start_enabled():
        logger.info("Auto-start not enabled, enabling it now...")
        set_auto_start(True)
    return settings

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
                python_exe = sys.executable.replace("python.exe", "pythonw.exe")  # Use pythonw.exe for windowless execution
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