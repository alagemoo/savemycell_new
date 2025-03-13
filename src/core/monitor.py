import psutil
import threading
import time
from src.core.utils import RUNNING, UNPLUG_PROMPT_ACTIVE, PROMPT_QUEUE, logger

class BatteryMonitor:
    def __init__(self, app):
        self.app = app
        self.last_battery = None
        self.last_unplug_prompt_time = 0
        self.last_update = 0
        self.lock = threading.Lock()
        self.last_percent = None
        self.last_plugged = None

    def run(self):
        while RUNNING:
            try:
                battery = psutil.sensors_battery()
                if not battery:
                    logger.warning("Battery status unavailable.")
                    time.sleep(10)
                    continue
                with self.lock:
                    current_time = time.time()
                    if self.app.minimized_to_tray and (not battery.power_plugged or battery.percent < self.app.unplug_threshold):
                        sleep_interval = 300
                    elif self.app.power_saving_mode:
                        sleep_interval = 600
                    elif battery.power_plugged and battery.percent >= self.app.unplug_threshold:
                        sleep_interval = 5
                    else:
                        sleep_interval = self.app.refresh_interval
                    if battery.percent >= self.app.unplug_threshold and battery.power_plugged:
                        if not UNPLUG_PROMPT_ACTIVE:
                            if self.last_battery and not self.last_battery.power_plugged and battery.power_plugged:
                                logger.info("Charger replugged above threshold, triggering prompt...")
                                PROMPT_QUEUE.put(True)
                            elif current_time - self.last_unplug_prompt_time >= 300 or not self.last_unplug_prompt_time:
                                logger.info("Triggering unplug prompt...")
                                PROMPT_QUEUE.put(True)
                                self.last_unplug_prompt_time = current_time
                    elif self.last_battery and not battery.power_plugged and self.last_battery.power_plugged:
                        if battery.percent < self.app.unplug_threshold:
                            self.last_unplug_prompt_time = 0
                            logger.info("Charger unplugged and below threshold, resetting cooldown.")
                    self.last_battery = battery
                    if self.app.root.winfo_exists() and not self.app.minimized_to_tray:
                        if self.last_percent is None or self.last_plugged is None or \
                           abs(battery.percent - self.last_percent) >= 1 or battery.power_plugged != self.last_plugged:
                            self.app.root.after(0, lambda: self.app.update_ui(battery.percent, battery.power_plugged))
                            self.last_percent = battery.percent
                            self.last_plugged = battery.power_plugged
                    if current_time - self.last_update >= 300:
                        self.app.update_system_stats()
                        self.last_update = current_time
                time.sleep(sleep_interval)
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(10)