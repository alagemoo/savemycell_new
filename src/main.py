import sys
import os

# Add the parent directory (SaveMyCell) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import tkinter as tk
from src.ui.app import BatteryMonitorApp

if __name__ == "__main__":
    root = tk.Tk()
    app = BatteryMonitorApp(root)
    root.mainloop()