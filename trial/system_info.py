# system_info.py

import psutil
import platform
import getpass
import socket
import logging
import os
import sys
import winreg
from typing import Optional, Dict

from constants import AUTO_START_REG_KEY, AUTO_START_APP_NAME

logger = logging.getLogger(__name__)

# Detect idle time on Windows
try:
    import win32api
    import win32con
except ImportError:
    win32api = None
    win32con = None
    logger.warning("pywin32 not installed. Idle time detection disabled.")

def calculate_battery_time(battery: Optional[psutil.sensors_battery]) -> str:
    """Calculates and returns estimated time to discharge or full charge."""
    if not battery:
        return "Time: N/A"
    if not battery.power_plugged:
        if battery.secsleft == psutil.POWER_TIME_UNKNOWN:
            return "Time to Discharge: Estimating..."
        hours = battery.secsleft // 3600
        minutes = (battery.secsleft % 3600) // 60
        return f"Time to Discharge: {hours}h {minutes}m"
    if battery.power_plugged:
        current_percent = battery.percent
        remaining_percent = 100 - current_percent
        # This charging rate estimation is approximate and depends on typical battery charging curves.
        # For a more accurate estimation, historical data or battery specific APIs would be needed.
        # Simple linear approximation for charging time:
        # Assume it takes roughly 2 hours to charge from 0 to 100 on average for a laptop (7200 seconds)
        # Calculate seconds remaining based on remaining percentage.
        # A more advanced model would consider charging rate decreases as battery gets fuller.
        
        # If battery is already 100%, it's fully charged.
        if current_percent >= 99.9: # Use 99.9 to account for floating point inaccuracies
            return "Time to Full Charge: Fully Charged"
        
        # A simple linear model for estimation:
        # Suppose charging from 0 to 100% takes 'X' seconds.
        # Then, time remaining is (100 - current_percent) / 100 * X
        # Let's use a rough average of 2.5 hours (9000 seconds) for 0-100% charge for typical laptops.
        total_charge_time_seconds = 9000 # 2.5 hours
        estimated_secs_to_full = (remaining_percent / 100) * total_charge_time_seconds

        if estimated_secs_to_full <= 0: # Should not happen if current_percent < 100
             return "Time to Full Charge: Fully Charged"

        hours = int(estimated_secs_to_full // 3600)
        minutes = int((estimated_secs_to_full % 3600) // 60)
        return f"Time to Full Charge: {hours}h {minutes}m"

def get_system_details() -> Dict[str, str]:
    """Retrieves and returns system and battery details."""
    # Use caching for details that don't change frequently
    if not hasattr(get_system_details, "cached_details"):
        get_system_details.cached_details = {
            "System Name": socket.gethostname(),
            "Laptop Model Number": platform.machine(), # This is actually architecture, not model number
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
            "Battery Cell Type": "Unknown", # psutil does not provide this directly
            "Time to Full Charge": "N/A",
            "Time to Complete Discharge": "N/A"
        })
        time_text = calculate_battery_time(battery)
        if "Full Charge" in time_text:
            get_system_details.cached_details["Time to Full Charge"] = time_text.replace("Time to Full Charge: ", "")
            get_system_details.cached_details["Time to Complete Discharge"] = "N/A" # Ensure only one is set
        elif "Discharge" in time_text:
            get_system_details.cached_details["Time to Complete Discharge"] = time_text.replace("Time to Discharge: ", "")
            get_system_details.cached_details["Time to Full Charge"] = "N/A" # Ensure only one is set
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
    """Enables or disables the application's auto-start on Windows."""
    if platform.system() != "Windows":
        logger.warning("Auto-start feature is only available on Windows.")
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTO_START_REG_KEY, 0, winreg.KEY_ALL_ACCESS)
        if enabled:
            if getattr(sys, 'frozen', False): # Running as a bundled executable
                executable_path = sys.executable
            else: # Running as a Python script
                python_exe = sys.executable
                script_path = os.path.abspath(sys.argv[0]) # Use sys.argv[0] for current script path
                executable_path = f'"{python_exe}" "{script_path}"'
            logger.info(f"Setting auto-start for '{AUTO_START_APP_NAME}' with value: {executable_path}")
            winreg.SetValueEx(key, AUTO_START_APP_NAME, 0, winreg.REG_SZ, executable_path)
        else:
            try:
                winreg.DeleteValue(key, AUTO_START_APP_NAME)
                logger.info(f"Removed auto-start for '{AUTO_START_APP_NAME}'")
            except FileNotFoundError:
                logger.info(f"Auto-start for '{AUTO_START_APP_NAME}' was not found, no action needed.")
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.error(f"Failed to set auto-start for '{AUTO_START_APP_NAME}': {str(e)}")
        return False

def is_auto_start_enabled() -> bool:
    """Checks if the application's auto-start is enabled on Windows."""
    if platform.system() != "Windows":
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTO_START_REG_KEY, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, AUTO_START_APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception as e:
        logger.error(f"Failed to check auto-start for '{AUTO_START_APP_NAME}': {e}")
        return False

def get_idle_time() -> float:
    """Returns the system idle time in seconds on Windows, 0 otherwise."""
    if win32api is None or win32con is None:
        return 0
    try:
        last_input = win32api.GetLastInputInfo()
        current_time = win32api.GetTickCount()
        idle_time_ms = current_time - last_input
        return idle_time_ms / 1000.0
    except Exception as e:
        logger.error(f"Failed to get idle time: {e}")
        return 0