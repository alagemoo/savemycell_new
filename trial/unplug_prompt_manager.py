# unplug_prompt_manager.py

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import os
import time
import logging
from typing import Optional # Add this import

from constants import (
    PROMPT_WINDOW_WIDTH, PROMPT_WINDOW_HEIGHT, PROMPT_TIMEOUT_SECONDS,
    IDLE_TIMEOUT_SECONDS
)
from system_info import get_idle_time

logger = logging.getLogger(__name__)

class UnplugPromptManager:
    def __init__(self, parent_root: tk.Tk, settings_manager, close_callback=None):
        self.parent_root = parent_root
        self.settings_manager = settings_manager
        self.unplug_window: Optional[tk.Toplevel] = None
        self.prompt_start_time: float = 0
        self.close_callback = close_callback
        self._prompt_active = False

    def is_prompt_active(self) -> bool:
        return self._prompt_active and self.unplug_window and self.unplug_window.winfo_exists()

    def show_prompt(self):
        if self.is_prompt_active():
            logger.info("Unplug prompt already active, skipping. Bringing to front.")
            self.unplug_window.lift()
            self.unplug_window.focus_force()
            return
            
        logger.info("Showing unplug prompt...")
        self._prompt_active = True
        
        self.unplug_window = tk.Toplevel(self.parent_root)
        self.unplug_window.title("Battery Full - Action Required")
        self.unplug_window.geometry(f"{PROMPT_WINDOW_WIDTH}x{PROMPT_WINDOW_HEIGHT}")
        self.unplug_window.resizable(False, False)
        self.unplug_window.overrideredirect(True)
        self.unplug_window.configure(bg=self.settings_manager.background_color)
        self.unplug_window.attributes('-topmost', True)

        try:
            self.unplug_window.attributes('-alpha', 0.95)
            self.unplug_window.wm_attributes('-transparentcolor', self.settings_manager.background_color)
            logger.info(f"Applied prompt transparency with transparentcolor: {self.settings_manager.background_color}")
        except tk.TclError as e:
            logger.warning(f"Prompt transparency attribute failed (might not be supported): {e}")

        self.unplug_window.update_idletasks()
        screen_width = self.unplug_window.winfo_screenwidth()
        screen_height = self.unplug_window.winfo_screenheight()
        x = (screen_width - PROMPT_WINDOW_WIDTH) // 2
        y = (screen_height - PROMPT_WINDOW_HEIGHT) // 2
        self.unplug_window.geometry(f"+{x}+{y}")

        if not self.settings_manager.power_saving_mode:
            self.unplug_window.attributes('-alpha', 0)
            for alpha in range(0, 21):
                if not self.unplug_window.winfo_exists(): return
                self.unplug_window.attributes('-alpha', alpha / 20)
                self.parent_root.update_idletasks()
                time.sleep(0.01)
            if self.unplug_window.winfo_exists():
                self.unplug_window.attributes('-alpha', 0.95)

        main_frame_prompt = ttk.Frame(self.unplug_window, style="Main.TFrame")
        main_frame_prompt.pack(fill="both", expand=True, padx=20, pady=20)
        main_frame_prompt.columnconfigure(0, weight=1)
        
        row_idx = 0
        self.logo_photo = None

        custom_logo_path = self.settings_manager.custom_logo_path
        if custom_logo_path and os.path.exists(custom_logo_path):
            try:
                logo_img = Image.open(custom_logo_path)
                original_width, original_height = logo_img.size
                target_size = 100
                ratio = min(target_size / original_width, target_size / original_height)
                new_width = int(original_width * ratio)
                new_height = int(original_height * ratio)
                logo_img = logo_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                self.logo_photo = ImageTk.PhotoImage(logo_img)
                logo_label = ttk.Label(main_frame_prompt, image=self.logo_photo, background=self.settings_manager.background_color)
                logo_label.grid(row=row_idx, column=0, pady=(0, 8), sticky="n")
                row_idx += 1
                logger.info(f"Custom logo loaded from {custom_logo_path}")
            except Exception as e:
                logger.error(f"Failed to load custom logo from {custom_logo_path}: {e}")

        prompt_label = ttk.Label(main_frame_prompt, text="Battery Full!\nPlease Unplug Charger", style="Prompt.TLabel", anchor="center", justify="center")
        prompt_label.grid(row=row_idx, column=0, pady=(0, 8), sticky="nsew")
        row_idx += 1

        info_label = ttk.Label(main_frame_prompt, text="Unplugging your charger when the battery is fully charged:\n"
                                                            "- Extends battery lifespan by preventing overcharging.\n"
                                                            "- Reduces energy waste and lowers your carbon footprint.\n"
                                                            "- Protects your device from potential heat damage.",
                               style="Info.TLabel", anchor="center", justify="center")
        info_label.grid(row=row_idx, column=0, pady=(0, 16), padx=10, sticky="nsew")
        row_idx += 1

        countdown_label = ttk.Label(main_frame_prompt, text=f"Auto-close in {PROMPT_TIMEOUT_SECONDS}s", font=(self.settings_manager.get_ui_setting("font_type", "Segoe UI"), 14, "bold"), foreground=self.settings_manager.accent_color, background=self.settings_manager.background_color, anchor="center")
        countdown_label.grid(row=row_idx, column=0, pady=(0, 16), sticky="nsew")
        row_idx += 1

        def add_close_button_after_timeout():
            if self.unplug_window and self.unplug_window.winfo_exists():
                close_button = ttk.Button(main_frame_prompt, text="Close", command=self.close_prompt, style="Custom.TButton")
                close_button.grid(row=row_idx, column=0, pady=(0, 16), sticky="nsew")
                self.unplug_window.bind("<Escape>", lambda event: self.close_prompt())
                logger.info("Close button added to unplug prompt.")

        self.prompt_start_time = time.time()
        self.unplug_window.after(int(PROMPT_TIMEOUT_SECONDS * 1000), add_close_button_after_timeout)
        
        self._monitor_unplug_status(countdown_label)
        logger.info("Unplug prompt displayed.")

    def close_prompt(self):
        if self.unplug_window and self.unplug_window.winfo_exists():
            for alpha in range(20, -1, -1):
                if not self.unplug_window.winfo_exists(): break
                self.unplug_window.attributes('-alpha', alpha / 20)
                self.parent_root.update_idletasks()
                time.sleep(0.01)
            if self.unplug_window.winfo_exists():
                self.unplug_window.destroy()
            self.unplug_window = None
            self._prompt_active = False
            self.logo_photo = None
            if self.close_callback:
                self.close_callback()
            logger.info("Unplug prompt closed.")

    def _monitor_unplug_status(self, countdown_label):
        if not self.is_prompt_active():
            return

        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery and not battery.power_plugged:
                logger.info("Charger unplugged, closing prompt automatically.")
                self.close_prompt()
                return

            idle_time = get_idle_time()
            if idle_time >= IDLE_TIMEOUT_SECONDS:
                logger.info(f"System idle for {IDLE_TIMEOUT_SECONDS} seconds, closing prompt automatically.")
                self.close_prompt()
                return
            
            elapsed_time = time.time() - self.prompt_start_time
            if elapsed_time >= PROMPT_TIMEOUT_SECONDS:
                countdown_label.config(text="Auto-close in 0s")
            else:
                remaining = max(0, PROMPT_TIMEOUT_SECONDS - int(elapsed_time))
                countdown_label.config(text=f"Auto-close in {remaining}s")

            self.unplug_window.after(500, lambda: self._monitor_unplug_status(countdown_label))

        except Exception as e:
            logger.error(f"Error in _monitor_unplug_status: {e}")
            if self.unplug_window and self.unplug_window.winfo_exists():
                self.unplug_window.after(500, lambda: self._monitor_unplug_status(countdown_label))