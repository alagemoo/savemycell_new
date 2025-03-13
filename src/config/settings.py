import os
import json
import winreg
import sys
from tkinter import messagebox
from src.core.utils import logger, log_dir
from src.ui.styles import update_theme, configure_styles

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

def save_settings_to_file(app):
    try:
        settings = {
            "unplug_threshold": app.unplug_threshold,
            "refresh_interval": app.refresh_interval,
            "power_saving_mode": app.power_saving_mode,
            "ui_settings": {
                "custom_logo_path": app.custom_logo_path,
                "background_color": app.background_color,
                "text_color": app.text_color
            }
        }
        with open(os.path.join(log_dir, "settings.json"), "w") as f:
            json.dump(settings, f)
        logger.info(f"Settings saved to settings.json: {settings}")
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        messagebox.showerror("Error", "Failed to save settings. Check logs for details.")

def load_settings_from_file(app):
    settings_file = os.path.join(log_dir, "settings.json")
    try:
        if not os.path.exists(settings_file):
            logger.warning(f"Settings file not found at {settings_file}. Using defaults.")
            raise FileNotFoundError(f"Settings file not found at {settings_file}")

        with open(settings_file, "r") as f:
            settings = json.load(f)
            app.unplug_threshold = settings.get("unplug_threshold", 90)
            app.refresh_interval = settings.get("refresh_interval", 120)
            app.power_saving_mode = settings.get("power_saving_mode", False)
            ui_settings = settings.get("ui_settings", {})
            app.custom_logo_path = ui_settings.get("custom_logo_path", "")
            app.background_color = ui_settings.get("background_color", "#F3F3F3")
            app.text_color = ui_settings.get("text_color", "#000000")
            update_theme(app)
            configure_styles(app)
            logger.info(f"Settings loaded from {settings_file}: {settings}")
    except FileNotFoundError as e:
        logger.error(f"Failed to load settings due to file not found: {e}")
        messagebox.showerror("Error", f"Failed to load settings. Using defaults. Details: {e}")
        app.unplug_threshold = 90
        app.refresh_interval = 120
        app.power_saving_mode = False
        app.custom_logo_path = ""
        app.background_color = "#F3F3F3"
        app.text_color = "#000000"
        update_theme(app)
        configure_styles(app)
        save_settings_to_file(app)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse settings file {settings_file}: {e}")
        messagebox.showerror("Error", f"Failed to load settings due to invalid JSON. Using defaults. Details: {e}")
        app.unplug_threshold = 90
        app.refresh_interval = 120
        app.power_saving_mode = False
        app.custom_logo_path = ""
        app.background_color = "#F3F3F3"
        app.text_color = "#000000"
        update_theme(app)
        configure_styles(app)
        save_settings_to_file(app)
    except Exception as e:
        logger.error(f"Unexpected error loading settings from {settings_file}: {e}")
        messagebox.showerror("Error", f"Failed to load settings. Using defaults. Details: {e}")
        app.unplug_threshold = 90
        app.refresh_interval = 120
        app.power_saving_mode = False
        app.custom_logo_path = ""
        app.background_color = "#F3F3F3"
        app.text_color = "#000000"
        update_theme(app)
        configure_styles(app)
        save_settings_to_file(app)
    if not is_auto_start_enabled():
        logger.info("Auto-start not enabled, enabling it now...")
        set_auto_start(True)