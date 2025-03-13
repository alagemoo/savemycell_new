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
from tkinter import ttk, messagebox, filedialog
import time
import psutil
from PIL import Image, ImageTk
from src.core.utils import calculate_battery_time, get_idle_time, logger, PROMPT_QUEUE, UNPLUG_PROMPT_ACTIVE

def build_main_screen(app):
    logger.info("Building main screen...")
    for widget in app.main_frame.winfo_children():
        widget.destroy()
    app.main_frame.pack(fill="both", expand=True, padx=16, pady=16)
    app.main_frame.columnconfigure(0, weight=1)
    app.main_frame.rowconfigure(0, weight=1)
    app.main_frame.rowconfigure(1, weight=0)
    app.main_frame.rowconfigure(2, weight=0)
    app.main_frame.rowconfigure(3, weight=0)
    app.main_frame.rowconfigure(4, weight=0)

    battery = psutil.sensors_battery()
    initial_percent = f"{battery.percent}%" if battery else "N/A"
    app.battery_label = ttk.Label(
        app.main_frame,
        text=initial_percent,
        font=(app.font_type, 80, "bold"),
        foreground=app.text_color,
        background=app.background_color,
        anchor="center"
    )
    app.battery_label.grid(row=0, column=0, pady=(0, 8), sticky="nsew")

    status = "Charging" if (battery and battery.power_plugged) else "Discharging"
    app.battery_status = ttk.Label(
        app.main_frame,
        text=status,
        font=(app.font_type, 14),
        foreground="#666666" if not app.is_dark_mode else "#AAAAAA",
        background=app.background_color,
        anchor="center"
    )
    app.battery_status.grid(row=1, column=0, pady=(0, 8), sticky="ew")

    app.battery_time = ttk.Label(
        app.main_frame,
        text=calculate_battery_time(battery),
        font=(app.font_type, 14),
        foreground=app.text_color,
        background=app.background_color,
        anchor="center"
    )
    app.battery_time.grid(row=2, column=0, pady=(0, 16), sticky="ew")

    button_frame = ttk.Frame(app.main_frame, style="Main.TFrame")
    button_frame.grid(row=4, column=0, pady=(16, 0), sticky="nsew")
    button_frame.columnconfigure(0, weight=1)

    app.details_button = ttk.Button(button_frame, text="System Diagnostics", command=app.show_details, style="Custom.TButton")
    app.details_button.grid(row=0, column=0, pady=4, padx=10, sticky="ew")
    app.about_button = ttk.Button(button_frame, text="About Save My Cell", command=app.show_about, style="Custom.TButton")
    app.about_button.grid(row=1, column=0, pady=4, padx=10, sticky="ew")
    app.stop_button = ttk.Button(button_frame, text="Minimize", command=app.minimize_to_tray, style="Stop.TButton")
    app.stop_button.grid(row=2, column=0, pady=4, padx=10, sticky="ew")
    app.settings_button = ttk.Button(button_frame, text="Settings", command=app.show_settings, style="Custom.TButton")
    app.settings_button.grid(row=3, column=0, pady=4, padx=10, sticky="ew")
    logger.info("Main screen built successfully.")

def show_unplug_prompt(app):
    global UNPLUG_PROMPT_ACTIVE
    if UNPLUG_PROMPT_ACTIVE:
        logger.info("Unplug prompt already active, skipping.")
        return
    logger.info("Showing unplug prompt...")
    UNPLUG_PROMPT_ACTIVE = True
    app.unplug_window = tk.Toplevel(app.root)
    app.unplug_window.title("Battery Full - Action Required")
    app.unplug_window.geometry("640x400")
    app.unplug_window.resizable(False, False)
    app.unplug_window.overrideredirect(True)
    app.unplug_window.configure(bg=app.background_color)
    app.unplug_window.attributes('-topmost', True)
    app.unplug_window.attributes('-alpha', 0.95)

    screen_width = app.unplug_window.winfo_screenwidth()
    screen_height = app.unplug_window.winfo_screenheight()
    x = (screen_width - 640) // 2
    y = (screen_height - 400) // 2
    app.unplug_window.geometry(f"+{x}+{y}")

    if not app.power_saving_mode:
        app.unplug_window.attributes('-alpha', 0)
        for alpha in range(0, 21):
            app.unplug_window.attributes('-alpha', alpha / 20)
            time.sleep(0.01)
        app.unplug_window.attributes('-alpha', 0.95)

    app.main_frame_prompt = ttk.Frame(app.unplug_window, style="Main.TFrame")
    app.main_frame_prompt.place(relx=0.5, rely=0.5, anchor="center")
    app.main_frame_prompt.columnconfigure(0, weight=1)
    for i in range(5):
        app.main_frame_prompt.rowconfigure(i, weight=0)

    row = 0
    if hasattr(app, "custom_logo_path") and app.custom_logo_path and os.path.exists(app.custom_logo_path):
        try:
            logo_img = Image.open(app.custom_logo_path)
            original_width, original_height = logo_img.size
            target_size = 100
            ratio = min(target_size / original_width, target_size / original_height)
            new_width = int(original_width * ratio)
            new_height = int(original_height * ratio)
            logo_img = logo_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logo_photo = ImageTk.PhotoImage(logo_img)
            logo_label = ttk.Label(app.main_frame_prompt, image=logo_photo, background=app.background_color)
            logo_label.image = logo_photo
            logo_label.grid(row=row, column=0, pady=(16, 8), padx=20, sticky="n")
            row += 1
            logger.info(f"Custom logo loaded from {app.custom_logo_path}")
        except Exception as e:
            logger.error(f"Failed to load custom logo: {e}")

    prompt_label = ttk.Label(app.main_frame_prompt, text="Battery Full!\nPlease Unplug Charger", style="Prompt.TLabel", anchor="center", justify="center")
    prompt_label.grid(row=row, column=0, pady=(0 if row > 0 else 16, 8), padx=20, sticky="nsew")
    row += 1

    info_label = ttk.Label(app.main_frame_prompt, text="Unplugging your charger when the battery is fully charged:\n"
                                                       "- Extends battery lifespan by preventing overcharging.\n"
                                                       "- Reduces energy waste and lowers your carbon footprint.\n"
                                                       "- Protects your device from potential heat damage.",
                           style="Info.TLabel", anchor="center", justify="center")
    info_label.grid(row=row, column=0, pady=(0, 16), padx=20, sticky="nsew")
    row += 1

    countdown_label = ttk.Label(app.main_frame_prompt, text=f"Auto-close in {30}s", font=(app.font_type, 14, "bold"), foreground=app.accent_color, background=app.background_color, anchor="center")
    countdown_label.grid(row=row, column=0, pady=(0, 16), padx=20, sticky="nsew")
    row += 1

    def add_close_button():
        elapsed_time = time.time() - app.prompt_start_time
        if elapsed_time >= 30 and app.unplug_window.winfo_exists():
            close_button = ttk.Button(app.main_frame_prompt, text="Close", command=lambda: close_unplug_prompt(app), style="Custom.TButton")
            close_button.grid(row=row, column=0, pady=(0, 16), padx=20, sticky="nsew")
            logger.info("Close button added after timeout.")
            app.unplug_window.bind("<Escape>", lambda event: close_unplug_prompt(app))
            app.main_frame_prompt.rowconfigure(row, weight=0)

    app.prompt_start_time = time.time()
    app.unplug_window.after(int(30 * 1000), add_close_button)
    monitor_unplug(app, countdown_label)
    logger.info("Unplug prompt displayed.")

def close_unplug_prompt(app):
    global UNPLUG_PROMPT_ACTIVE
    if app.unplug_window and app.unplug_window.winfo_exists():
        for alpha in range(20, -1, -1):
            app.unplug_window.attributes('-alpha', alpha / 20)
            time.sleep(0.01)
        app.unplug_window.destroy()
        UNPLUG_PROMPT_ACTIVE = False
        logger.info("Unplug prompt closed manually.")

def monitor_unplug(app, countdown_label):
    global UNPLUG_PROMPT_ACTIVE
    try:
        if not app.unplug_window.winfo_exists():
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
            close_unplug_prompt(app)
            logger.info("Charger unplugged, closing prompt.")
            return
        elif idle_time >= 120:
            close_unplug_prompt(app)
            logger.info("System idle for 2 minutes, closing prompt.")
            return
        else:
            if not hasattr(app, "prompt_start_time"):
                app.prompt_start_time = time.time()
            elapsed_time = time.time() - app.prompt_start_time
            if elapsed_time >= 30:
                countdown_label.config(text="Auto-close in 0s")
                logger.info("Countdown reached 0, waiting for manual close.")
                if elapsed_time >= 30 + 30:
                    close_unplug_prompt(app)
                    logger.warning("Prompt stuck after timeout, force closing.")
                    return
            else:
                remaining = max(0, 30 - int(elapsed_time))
                countdown_label.config(text=f"Auto-close in {remaining}s")
                app.unplug_window.after(500, lambda: monitor_unplug(app, countdown_label))
    except Exception as e:
        logger.error(f"Error in monitor_unplug: {e}")
        if app.unplug_window.winfo_exists():
            app.unplug_window.after(500, lambda: monitor_unplug(app, countdown_label))

def show_alt_screen(app, title: str, content: str):
    logger.info(f"Showing alternate screen: {title}")
    if app.main_frame:
        app.main_frame.pack_forget()
    app.alt_frame = ttk.Frame(app.root, style="Main.TFrame")
    app.alt_frame.pack(fill="both", expand=True, padx=16, pady=16)
    app.alt_frame.columnconfigure(0, weight=1)

    app.alt_title = ttk.Label(app.alt_frame, text=title, style="Title.TLabel")
    app.alt_title.grid(row=0, column=0, pady=(0, 8), sticky="ew")

    content_lines = content.count('\n') + 1
    text_height = min(max(content_lines, 5), 10)
    app.alt_text = tk.Text(app.alt_frame, wrap="word", font=(app.font_type, 10), bg=app.secondary_bg, fg=app.text_color, relief="flat", borderwidth=0, height=text_height, width=50)
    app.alt_text.grid(row=1, column=0, pady=(0, 8), sticky="nsew")
    app.alt_text.insert(tk.END, content)
    app.alt_text.config(state="disabled")

    app.back_button = ttk.Button(app.alt_frame, text="Back to Monitor", command=app.show_main_screen, style="Back.TButton")
    app.back_button.grid(row=2, column=0, pady=(8, 0), sticky="ew")
    app.alt_frame.rowconfigure(0, weight=0)
    app.alt_frame.rowconfigure(1, weight=1)
    app.alt_frame.rowconfigure(2, weight=0)
    logger.info(f"Alternate screen {title} displayed.")

def show_settings(app):
    logger.info("Showing settings screen.")
    if app.main_frame:
        app.main_frame.pack_forget()

    app.alt_frame = ttk.Frame(app.root, style="Main.TFrame")
    app.alt_frame.pack(fill="both", expand=True)

    canvas = tk.Canvas(app.alt_frame, bg=app.background_color, highlightthickness=0)
    scrollbar = ttk.Scrollbar(app.alt_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas, style="Main.TFrame")

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    canvas_frame = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

    def configure_canvas(event):
        canvas.itemconfig(canvas_frame, width=event.width)
    canvas.bind("<Configure>", configure_canvas)

    app.alt_title = ttk.Label(scrollable_frame, text="Settings", style="Title.TLabel")
    app.alt_title.pack(pady=(16, 8))

    threshold_frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
    threshold_frame.pack(fill="x", pady=4, padx=16)
    ttk.Label(threshold_frame, text="Unplug Threshold (%):", font=(app.font_type, 11), foreground=app.text_color, background=app.background_color).pack(side="left", padx=8)
    threshold_entry = ttk.Entry(threshold_frame, font=(app.font_type, 11))
    threshold_entry.insert(0, str(app.unplug_threshold))
    threshold_entry.pack(side="left", padx=8, fill="x", expand=True)

    refresh_frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
    refresh_frame.pack(fill="x", pady=4, padx=16)
    ttk.Label(refresh_frame, text="Refresh Interval (s):", font=(app.font_type, 11), foreground=app.text_color, background=app.background_color).pack(side="left", padx=8)
    refresh_entry = ttk.Entry(refresh_frame, font=(app.font_type, 11))
    refresh_entry.insert(0, str(app.refresh_interval))
    if "FREE" == "FREE":
        refresh_entry.config(state="disabled")
    refresh_entry.pack(side="left", padx=8, fill="x", expand=True)

    power_saving_frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
    power_saving_frame.pack(fill="x", pady=4, padx=16)
    ttk.Label(power_saving_frame, text="Power Saving Mode:", font=(app.font_type, 11), foreground=app.text_color, background=app.background_color).pack(side="left", padx=8)
    app.power_saving_var = tk.BooleanVar(value=app.power_saving_mode)
    power_saving_check = ttk.Checkbutton(power_saving_frame, variable=app.power_saving_var, onvalue=True, offvalue=False)
    power_saving_check.pack(side="left", padx=8)

    ui_frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
    ui_frame.pack(fill="x", pady=(16, 8), padx=16)
    ttk.Label(ui_frame, text="UI Customization", font=(app.font_type, 12, "bold"), foreground=app.text_color, background=app.background_color).pack(pady=(0, 8))

    logo_frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
    logo_frame.pack(fill="x", pady=4, padx=16)
    ttk.Label(logo_frame, text="Custom Logo Path:", font=(app.font_type, 11), foreground=app.text_color, background=app.background_color).pack(side="left", padx=8)
    logo_entry = ttk.Entry(logo_frame, font=(app.font_type, 11))
    logo_entry.insert(0, getattr(app, "custom_logo_path", ""))
    logo_entry.pack(side="left", padx=8, fill="x", expand=True)
    ttk.Button(logo_frame, text="Browse", command=lambda: logo_entry.delete(0, tk.END) or logo_entry.insert(0, filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp")])), style="Custom.TButton").pack(side="left", padx=8)

    bg_color_frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
    bg_color_frame.pack(fill="x", pady=4, padx=16)
    ttk.Label(bg_color_frame, text="Background Color (Hex):", font=(app.font_type, 11), foreground=app.text_color, background=app.background_color).pack(side="left", padx=8)
    bg_color_entry = ttk.Entry(bg_color_frame, font=(app.font_type, 11))
    bg_color_entry.insert(0, app.background_color if hasattr(app, "background_color") else "#F3F3F3")
    bg_color_entry.pack(side="left", padx=8, fill="x", expand=True)

    text_color_frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
    text_color_frame.pack(fill="x", pady=4, padx=16)
    ttk.Label(text_color_frame, text="Text Color (Hex):", font=(app.font_type, 11), foreground=app.text_color, background=app.background_color).pack(side="left", padx=8)
    text_color_entry = ttk.Entry(text_color_frame, font=(app.font_type, 11))
    text_color_entry.insert(0, app.text_color if hasattr(app, "text_color") else "#000000")
    text_color_entry.pack(side="left", padx=8, fill="x", expand=True)

    button_frame = ttk.Frame(scrollable_frame, style="Main.TFrame")
    button_frame.pack(fill="x", pady=(16, 16), padx=16)
    ttk.Button(button_frame, text="Save", command=lambda: save_settings(app, bg_color_entry, text_color_entry, threshold_entry, refresh_entry, logo_entry), style="Custom.TButton").pack(side="left", padx=8, fill="x", expand=True)
    ttk.Button(button_frame, text="Back to Monitor", command=app.show_main_screen, style="Back.TButton").pack(side="left", padx=8, fill="x", expand=True)

def save_settings(app, bg_color_entry, text_color_entry, threshold_entry, refresh_entry, logo_entry):
    from src.core.utils import logger, log_dir
    from src.ui.styles import update_theme, configure_styles
    try:
        new_threshold = int(threshold_entry.get())
        if not 0 <= new_threshold <= 100:
            raise ValueError("Unplug threshold must be 0-100.")
        if "PRO" == "PRO":
            new_refresh = int(refresh_entry.get())
            if new_refresh <= 0:
                raise ValueError("Refresh interval must be greater than 0.")
            app.refresh_interval = new_refresh
        app.unplug_threshold = new_threshold
        app.power_saving_mode = app.power_saving_var.get()
        app.custom_logo_path = logo_entry.get().strip()
        if app.custom_logo_path and not os.path.exists(app.custom_logo_path):
            messagebox.showwarning("Warning", "Logo file not found. It won’t be displayed until a valid path is provided.")

        new_bg_color = bg_color_entry.get().strip()
        new_text_color = text_color_entry.get().strip()
        if not (new_bg_color.startswith('#') and len(new_bg_color) == 7) or not (new_text_color.startswith('#') and len(new_text_color) == 7):
            raise ValueError("Colors must be valid hex codes (e.g., #RRGGBB).")
        app.background_color = new_bg_color
        app.text_color = new_text_color

        update_theme(app)
        configure_styles(app)
        app.show_main_screen()

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
        messagebox.showinfo("Success", "Settings saved successfully!")
    except ValueError as ve:
        messagebox.showerror("Error", str(ve))
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        messagebox.showerror("Error", f"An unexpected error occurred: {e}")