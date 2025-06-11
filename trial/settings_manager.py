# settings_manager.py

import json
import os
import logging
import darkdetect # Ensure darkdetect is imported here

# --- Constants for SettingsManager (These should ideally be in constants.py) ---
# For now, defined here for clarity in settings_manager.py
# Assuming these are NOT in constants.py yet, or need to be moved there later.

# Application Data Path
APP_DATA_PATH = os.path.join(os.path.expanduser("~"), "AppData", "Local", "SaveMyCell")
SETTINGS_FILE_PATH = os.path.join(APP_DATA_PATH, "settings.json")

# Default UI Colors (Dark Mode)
DEFAULT_DARK_MODE_BG = "#1e1e1e" # Dark grey
DEFAULT_DARK_MODE_TEXT = "#ffffff" # White
DEFAULT_DARK_MODE_SECONDARY_BG = "#2d2d30" # Slightly lighter dark grey
DEFAULT_DARK_MODE_ACCENT = "#0078d4" # Microsoft Fluent Blue

# Default UI Colors (Light Mode)
DEFAULT_LIGHT_MODE_BG = "#f2f2f2" # Light grey
DEFAULT_LIGHT_MODE_TEXT = "#000000" # Black
DEFAULT_LIGHT_MODE_SECONDARY_BG = "#e0e0e0" # Slightly darker light grey
DEFAULT_LIGHT_MODE_ACCENT = "#0078d4" # Microsoft Fluent Blue

# Default Font
DEFAULT_FONT_TYPE = "Segoe UI" if "Segoe UI" in logging.getLogger(__name__).handlers else "Arial" # Fallback if font isn't found
# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class SettingsManager:
    def __init__(self):
        self.unplug_threshold = 90
        self.refresh_interval = 120 # Default for free version
        self.power_saving_mode = False
        self.custom_logo_path = ""
        self.is_dark_mode = False # Current detected system theme state

        # UI color settings - initialized to system defaults
        self.background_color = ""
        self.text_color = ""
        self.secondary_bg_color = ""
        self.accent_color = ""
        self.font_type = DEFAULT_FONT_TYPE

        # Load settings first, then apply theme defaults if custom colors are not set
        self._load_settings()
        self._apply_initial_theme_defaults() # Apply defaults based on detected theme

    def _get_default_colors_for_theme(self, is_dark: bool):
        """Returns the default color set for a given theme."""
        if is_dark:
            return {
                "background_color": DEFAULT_DARK_MODE_BG,
                "text_color": DEFAULT_DARK_MODE_TEXT,
                "secondary_bg_color": DEFAULT_DARK_MODE_SECONDARY_BG,
                "accent_color": DEFAULT_DARK_MODE_ACCENT,
            }
        else:
            return {
                "background_color": DEFAULT_LIGHT_MODE_BG,
                "text_color": DEFAULT_LIGHT_MODE_TEXT,
                "secondary_bg_color": DEFAULT_LIGHT_MODE_SECONDARY_BG,
                "accent_color": DEFAULT_LIGHT_MODE_ACCENT,
            }

    def _apply_initial_theme_defaults(self):
        """
        Applies default theme colors if custom colors are not explicitly set
        or if it's the very first run.
        """
        current_system_is_dark = darkdetect.isDark()
        self.is_dark_mode = current_system_is_dark # Always store current system theme

        default_colors = self._get_default_colors_for_theme(current_system_is_dark)

        # Apply defaults only if the custom setting is empty or not a valid hex (indicates first run or reset)
        if not self._is_valid_hex_color(self.background_color):
            self.background_color = default_colors["background_color"]
        if not self._is_valid_hex_color(self.text_color):
            self.text_color = default_colors["text_color"]
        if not self._is_valid_hex_color(self.secondary_bg_color):
            self.secondary_bg_color = default_colors["secondary_bg_color"]
        if not self._is_valid_hex_color(self.accent_color):
            self.accent_color = default_colors["accent_color"]
        
        # Ensure font is always set
        if not self.font_type:
            self.font_type = DEFAULT_FONT_TYPE


    def update_theme_if_changed(self) -> bool:
        """
        Checks if the system theme has changed and updates internal settings.
        Returns True if theme changed and settings were updated, False otherwise.
        """
        current_system_is_dark = darkdetect.isDark()
        if current_system_is_dark != self.is_dark_mode:
            logger.info(f"System theme changed from {'Dark' if self.is_dark_mode else 'Light'} to {'Dark' if current_system_is_dark else 'Light'}")
            self.is_dark_mode = current_system_is_dark
            
            # When system theme changes, reset custom colors to the *new* theme's defaults
            # This prioritizes system theme over old custom settings if theme changes
            default_colors = self._get_default_colors_for_theme(current_system_is_dark)
            self.background_color = default_colors["background_color"]
            self.text_color = default_colors["text_color"]
            self.secondary_bg_color = default_colors["secondary_bg_color"]
            self.accent_color = default_colors["accent_color"]
            
            self.save_settings() # Save the updated theme settings
            return True
        return False

    def _is_valid_hex_color(self, hex_code: str) -> bool:
        """Helper to validate if a string is a valid hex color code."""
        if not isinstance(hex_code, str):
            return False
        if not (hex_code.startswith('#') and len(hex_code) == 7):
            return False
        try:
            int(hex_code[1:], 16)
            return True
        except ValueError:
            return False

    def _load_settings(self):
        """Loads settings from settings.json."""
        if not os.path.exists(APP_DATA_PATH):
            os.makedirs(APP_DATA_PATH, exist_ok=True)

        if os.path.exists(SETTINGS_FILE_PATH):
            try:
                with open(SETTINGS_FILE_PATH, "r") as f:
                    settings = json.load(f)
                    self.unplug_threshold = settings.get("unplug_threshold", self.unplug_threshold)
                    self.refresh_interval = settings.get("refresh_interval", self.refresh_interval)
                    self.power_saving_mode = settings.get("power_saving_mode", self.power_saving_mode)
                    
                    ui_settings = settings.get("ui_settings", {})
                    self.custom_logo_path = ui_settings.get("custom_logo_path", self.custom_logo_path)
                    
                    # Only load if valid hex, otherwise keep as "" to trigger default application
                    if self._is_valid_hex_color(ui_settings.get("background_color", "")):
                        self.background_color = ui_settings["background_color"]
                    if self._is_valid_hex_color(ui_settings.get("text_color", "")):
                        self.text_color = ui_settings["text_color"]
                    if self._is_valid_hex_color(ui_settings.get("secondary_bg_color", "")):
                        self.secondary_bg_color = ui_settings["secondary_bg_color"]
                    if self._is_valid_hex_color(ui_settings.get("accent_color", "")):
                        self.accent_color = ui_settings["accent_color"]
                    
                    self.font_type = ui_settings.get("font_type", self.font_type)

                logger.info("Settings loaded successfully.")
            except Exception as e:
                logger.error(f"Error loading settings: {e}. Using default settings.")
                self.save_settings() # Save defaults if loading fails
        else:
            logger.info("settings.json not found. Using default settings and saving them.")
            self.save_settings() # Save defaults if file doesn't exist

    def save_settings(self):
        """Saves current settings to settings.json."""
        if not os.path.exists(APP_DATA_PATH):
            os.makedirs(APP_DATA_PATH, exist_ok=True)
            
        settings = {
            "unplug_threshold": self.unplug_threshold,
            "refresh_interval": self.refresh_interval,
            "power_saving_mode": self.power_saving_mode,
            "ui_settings": {
                "custom_logo_path": self.custom_logo_path,
                "background_color": self.background_color,
                "text_color": self.text_color,
                "secondary_bg_color": self.secondary_bg_color,
                "accent_color": self.accent_color,
                "font_type": self.font_type,
            }
        }
        try:
            with open(SETTINGS_FILE_PATH, "w") as f:
                json.dump(settings, f, indent=4)
            logger.info("Settings saved successfully.")
        except Exception as e:
            logger.error(f"Error saving settings: {e}")

    def get_ui_setting(self, key: str, default: any):
        """Retrieves a specific UI setting."""
        # This method is primarily for retrieving font_type and other fixed UI settings
        # that are not directly mapped to dynamic color attributes.
        if key == "font_type":
            return self.font_type
        # Add other specific UI settings here if needed
        return default