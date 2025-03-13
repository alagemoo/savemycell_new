import psutil
import platform
import getpass
import socket
import logging
import os
from typing import Optional, Dict
import queue
import logging.handlers

# Configure logging
log_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "SaveMyCell")
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file = os.path.join(log_dir, "SaveMyCell.log")
handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=1024*1024, backupCount=5)  # 1MB per file, keep 5 backups
logging.basicConfig(handlers=[handler], level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global flags and constants
RUNNING = True
UNPLUG_PROMPT_ACTIVE = False
PROMPT_QUEUE = queue.Queue()

try:
    import win32api
    import win32con
except ImportError:
    win32api = None
    win32con = None

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