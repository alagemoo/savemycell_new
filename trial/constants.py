# constants.py

import os

# --- Versioning ---
VERSION = "FREE"    # Can be "FREE" or "PRO"

# --- Paths ---
APP_NAME = "SaveMyCellbyValionTech"
LOG_DIR_NAME = "SaveMyCell"
APP_DATA_PATH = os.path.join(os.path.expanduser("~"), "AppData", "Local", LOG_DIR_NAME)
LOG_FILE_PATH = os.path.join(APP_DATA_PATH, "SaveMyCell.log")
SETTINGS_FILE_PATH = os.path.join(APP_DATA_PATH, "settings.json")
ICON_FILE_NAME = "icon.png" # Assuming icon.png is in the same directory as the executable/script

# --- Battery Monitoring Thresholds and Intervals ---
DEFAULT_UNPLUG_THRESHOLD = 90    # Percentage at which to prompt to unplug
DEFAULT_REFRESH_INTERVAL_SECONDS = 120 # Main UI refresh interval
POWER_SAVING_REFRESH_INTERVAL_SECONDS = 600 # Longer interval for power saving mode
TRAY_MINIMIZED_REFRESH_INTERVAL_SECONDS = 300 # Even longer when minimized to tray

# --- UI Dimensions and Timings ---
WINDOW_WIDTH = 400
WINDOW_HEIGHT = 500
PROMPT_WINDOW_WIDTH = 640
PROMPT_WINDOW_HEIGHT = 400
IDLE_TIMEOUT_SECONDS = 120 # Time in seconds before considering system idle
PROMPT_TIMEOUT_SECONDS = 30 # Time in seconds before "Close" button appears on prompt

# --- Default UI Settings (if not loaded from file) ---
DEFAULT_LIGHT_MODE_BG = "#F3F3F3"   # Windows 11 light mode Mica-like color
DEFAULT_LIGHT_MODE_TEXT = "#000000"
DEFAULT_LIGHT_MODE_SECONDARY_BG = "#E6E6E6"

DEFAULT_DARK_MODE_BG = "#2D2D2D"    # Windows 11 dark mode Mica-like color
DEFAULT_DARK_MODE_TEXT = "#FFFFFF"
DEFAULT_DARK_MODE_SECONDARY_BG = "#3B3B3B"

DEFAULT_ACCENT_COLOR = "#0078D4" # Windows 11 default accent color

DEFAULT_FONT_TYPE = "Segoe UI" # Default font for the application UI

# --- Registry for Auto-Start ---
AUTO_START_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTO_START_APP_NAME = "SaveMyCellbyValionTech"