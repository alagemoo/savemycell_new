import customtkinter as ctk
from tkinter import ttk
import tkinter as tk
from PIL import Image, ImageTk
import os

# Set appearance mode and color theme
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class SaveMyCellApp:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Save My Cell")
        self.root.geometry("900x600")
        self.root.resizable(False, False)
        
        # Initialize variables
        self.current_page = "home"
        self.appearance_mode = "light"
        self.display_name = "John Doe"
        self.battery_percentage = 100
        
        # Create main container
        self.main_container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Setup the main layout
        self.setup_main_layout()
        
    def setup_main_layout(self):
        # Create two-column layout
        self.left_frame = ctk.CTkFrame(self.main_container, width=250, corner_radius=10)
        self.left_frame.pack(side="left", fill="y", padx=(0, 10))
        self.left_frame.pack_propagate(False)
        
        self.right_frame = ctk.CTkFrame(self.main_container, corner_radius=10)
        self.right_frame.pack(side="right", fill="both", expand=True)
        
        self.setup_left_panel()
        self.show_home_page()
        
    def setup_left_panel(self):
        # User info section
        user_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        user_frame.pack(fill="x", padx=15, pady=(15, 20))
        
        # User image placeholder (circular frame)
        self.user_image_frame = ctk.CTkFrame(user_frame, width=80, height=80, corner_radius=40)
        self.user_image_frame.pack(pady=(0, 10))
        
        # User icon (placeholder)
        user_icon_label = ctk.CTkLabel(self.user_image_frame, text="👤", font=("Arial", 60))
        user_icon_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Display name
        self.name_label = ctk.CTkLabel(user_frame, text=self.display_name, 
                                      font=ctk.CTkFont(size=16, weight="bold"))
        self.name_label.pack()
        
        # Navigation buttons
        nav_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        nav_frame.pack(fill="x", padx=15, pady=10)
        
        self.system_diag_btn = ctk.CTkButton(nav_frame, text="System Diagnostics",
                                           command=self.show_system_diagnostics,
                                           height=40, font=ctk.CTkFont(size=14))
        self.system_diag_btn.pack(fill="x", pady=(0, 10))
        
        self.about_btn = ctk.CTkButton(nav_frame, text="About Save My Cell",
                                     command=self.show_about_page,
                                     height=40, font=ctk.CTkFont(size=14))
        self.about_btn.pack(fill="x")
        
        # Settings button at bottom
        settings_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        settings_frame.pack(side="bottom", fill="x", padx=15, pady=15)
        
        self.settings_btn = ctk.CTkButton(
            settings_frame,
            text="⚙️",
            width=40,
            height=40,
            fg_color="transparent",
            hover_color="#e0e0e0",
            font=ctk.CTkFont(size=18),
            command=self.show_settings_page
        )
        self.settings_btn.pack(anchor="w", pady=5)
        
    def clear_right_frame(self):
        for widget in self.right_frame.winfo_children():
            widget.destroy()
            
    def show_home_page(self):
        self.current_page = "home"
        self.clear_right_frame()
        
        # Home page content
        home_content = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        home_content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Large battery percentage display
        battery_frame = ctk.CTkFrame(home_content, fg_color="transparent", height=180, width=350)
        battery_frame.pack(pady=(20, 20))
        battery_frame.pack_propagate(False)

        battery_label = ctk.CTkLabel(
            battery_frame,
            text=f"{self.battery_percentage}%",
            font=ctk.CTkFont(size=110, weight="bold"),
            text_color="#2CC985"
        )
        battery_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Battery info section
        info_frame = ctk.CTkFrame(home_content, corner_radius=10)
        info_frame.place(relx=0.5, rely=0.6, anchor="center", relwidth=0.8)
        
        info_title = ctk.CTkLabel(info_frame, text="Battery Information",
                                font=ctk.CTkFont(size=18, weight="bold"))
        info_title.pack(pady=(10, 10))
        
        # Battery details
        details = [
            "Status: Charging",
            "Health: Good",
            "Capacity: 4000 mAh",
            "Voltage: 3.8V",
            "Temperature: 32°C",
            "Time remaining: 2h 15m"
        ]
        
        for detail in details:
            detail_label = ctk.CTkLabel(info_frame, text=detail,
                                      font=ctk.CTkFont(size=14))
            detail_label.pack(pady=2)
            
        # Add some padding at bottom
        ctk.CTkLabel(info_frame, text="").pack(pady=10)
        
    def create_header_with_back_button(self, title):
        header_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        back_btn = ctk.CTkButton(header_frame, text="←",
                               command=self.show_home_page,
                               width=40, height=40,
                               fg_color="transparent",
                                text_color="gray",
                                hover_color="#e0e0e0",
                               font=ctk.CTkFont(size=20))
        back_btn.pack(side="left")
        
        title_label = ctk.CTkLabel(header_frame, text=title,
                                 font=ctk.CTkFont(size=24, weight="bold"))
        title_label.pack(side="left", padx=(20, 0))
        
        return header_frame
        
    def show_about_page(self):
        self.current_page = "about"
        self.clear_right_frame()
        
        self.create_header_with_back_button("About Save My Cell")
        
        # About content
        content_frame = ctk.CTkScrollableFrame(self.right_frame)
        content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        about_text = """
Save My Cell - Battery Management Application

Version: 2.1.0
Developer: Save My Cell Team
Released: 2025

About This Application:
Save My Cell is a comprehensive battery management application designed to help you monitor, maintain, and optimize your device's battery performance. Our application provides real-time battery statistics, health monitoring, and intelligent power management features.

Key Features:
• Real-time battery percentage and status monitoring
• Advanced battery health diagnostics
• Power consumption analysis
• Charging optimization recommendations
• Temperature monitoring and alerts
• Battery lifespan prediction
• Custom power profiles
• Detailed usage statistics

Mission Statement:
Our mission is to extend the lifespan of your device's battery through intelligent monitoring and optimization techniques. We believe that proper battery care can significantly improve device longevity and user experience.

Technical Specifications:
• Compatible with all major battery types
• Real-time monitoring with 1-second updates
• Advanced algorithms for health assessment
• Machine learning-based usage predictions
• Secure data handling and privacy protection

Support:
For technical support, feature requests, or general inquiries, please contact our support team at support@savemycell.com or visit our website at www.savemycell.com.

License:
This software is licensed under the MIT License. See LICENSE file for details.

Acknowledgments:
We would like to thank the open-source community and all beta testers who helped make this application possible.

Copyright © 2024 Save My Cell Team. All rights reserved.
        """
        
        text_label = ctk.CTkLabel(content_frame, text=about_text.strip(),
                                font=ctk.CTkFont(size=12),
                                justify="left", wraplength=500)
        text_label.pack(padx=20, pady=20, anchor="w")
        
    def show_system_diagnostics(self):
        self.current_page = "diagnostics"
        self.clear_right_frame()
        
        self.create_header_with_back_button("System Diagnostics")
        
        # Diagnostics content
        content_frame = ctk.CTkScrollableFrame(self.right_frame)
        content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Diagnostic sections
        sections = [
            ("Battery Health", [
                "Overall Health: Excellent (98%)",
                "Charge Cycles: 127 / 1000",
                "Maximum Capacity: 3920 mAh (98% of original)",
                "Internal Resistance: 0.12 Ω (Normal)",
                "Capacity Retention: 98.2%"
            ]),
            ("Charging System", [
                "Charger Status: Connected",
                "Charging Speed: Fast Charging (18W)",
                "Input Voltage: 5.2V",
                "Charging Efficiency: 92%",
                "Estimated Full Charge: 1h 45m"
            ]),
            ("Power Management", [
                "CPU Power Draw: 2.1W",
                "Display Power Draw: 1.8W",
                "Background Apps: 0.9W",
                "Network Activity: 0.3W",
                "Total System Draw: 5.1W"
            ]),
            ("Temperature Monitoring", [
                "Battery Temperature: 32°C (Normal)",
                "CPU Temperature: 45°C (Normal)",
                "Ambient Temperature: 24°C",
                "Thermal Throttling: Inactive",
                "Cooling Status: Adequate"
            ]),
            ("System Performance", [
                "Memory Usage: 3.2GB / 8GB (40%)",
                "Storage Usage: 45GB / 128GB (35%)",
                "CPU Usage: 15% (Average)",
                "Network Status: Connected (WiFi)",
                "Background Processes: 23 active"
            ])
        ]
        
        for section_title, items in sections:
            section_frame = ctk.CTkFrame(content_frame)
            section_frame.pack(fill="x", padx=20, pady=10)
            
            title_label = ctk.CTkLabel(section_frame, text=section_title,
                                     font=ctk.CTkFont(size=16, weight="bold"))
            title_label.pack(pady=(15, 10), anchor="w", padx=20)
            
            for item in items:
                item_label = ctk.CTkLabel(section_frame, text=f"• {item}",
                                        font=ctk.CTkFont(size=12),
                                        anchor="w")
                item_label.pack(pady=2, anchor="w", padx=40)
                
            # Add padding at bottom of section
            ctk.CTkLabel(section_frame, text="").pack(pady=5)
            
    def show_settings_page(self):
        self.current_page = "settings"
        self.clear_right_frame()
        
        self.create_header_with_back_button("Settings")
        
        # Settings content
        content_frame = ctk.CTkScrollableFrame(self.right_frame)
        content_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # General Section
        general_frame = ctk.CTkFrame(content_frame)
        general_frame.pack(fill="x", padx=20, pady=(10, 20))
        
        general_title = ctk.CTkLabel(general_frame, text="General",
                                   font=ctk.CTkFont(size=18, weight="bold"))
        general_title.pack(pady=(15, 15), anchor="w", padx=20)
        
        # Display name setting
        name_frame = ctk.CTkFrame(general_frame, fg_color="transparent")
        name_frame.pack(fill="x", padx=20, pady=5)
        
        name_label = ctk.CTkLabel(name_frame, text="Display name",
                                font=ctk.CTkFont(size=12))
        name_label.pack(anchor="w")
        
        self.name_entry = ctk.CTkEntry(name_frame, placeholder_text="Enter your name",
                                     width=300, height=30)
        self.name_entry.pack(anchor="w", pady=(5, 15))
        self.name_entry.insert(0, self.display_name)
        
        # Voltage threshold setting
        voltage_frame = ctk.CTkFrame(general_frame, fg_color="transparent")
        voltage_frame.pack(fill="x", padx=20, pady=5)
        
        voltage_label = ctk.CTkLabel(voltage_frame, text="Voltage Threshold",
                                   font=ctk.CTkFont(size=12))
        voltage_label.pack(anchor="w")
        
        voltage_slider_frame = ctk.CTkFrame(voltage_frame, fg_color="transparent")
        voltage_slider_frame.pack(fill="x", pady=(5, 15))
        
        self.voltage_slider = ctk.CTkSlider(voltage_slider_frame, from_=3.0, to=4.2,
                                          width=200, height=20, number_of_steps=12)
        self.voltage_slider.pack(side="left")
        self.voltage_slider.set(3.7)
        
        voltage_value_label = ctk.CTkLabel(voltage_slider_frame, text="3.7V",
                                         font=ctk.CTkFont(size=12))
        voltage_value_label.pack(side="left", padx=(20, 0))
        
        # Customization Section
        custom_frame = ctk.CTkFrame(content_frame)
        custom_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        custom_title = ctk.CTkLabel(custom_frame, text="Customization",
                                  font=ctk.CTkFont(size=18, weight="bold"))
        custom_title.pack(pady=(15, 15), anchor="w", padx=20)
        
        # Theme selection
        theme_frame = ctk.CTkFrame(custom_frame, fg_color="transparent")
        theme_frame.pack(fill="x", padx=20, pady=(0, 20))

        # Light and Dark mode previews
        mode_frame = ctk.CTkFrame(theme_frame, fg_color="transparent")
        mode_frame.pack(fill="x")

        # Shared variable for radio buttons
        self.theme_var = ctk.StringVar(value=self.appearance_mode)

        def select_light_mode(event=None):
            self.theme_var.set("light")
            self.change_appearance_mode("light")

        def select_dark_mode(event=None):
            self.theme_var.set("dark")
            self.change_appearance_mode("dark")

        # Light mode preview
        light_preview_frame = ctk.CTkFrame(mode_frame, width=220, height=220, corner_radius=10, fg_color="#f7f7f7", border_width=1, border_color="#bdbdbd", cursor="hand2")
        light_preview_frame.pack(side="left", padx=(0, 40))
        light_preview_frame.pack_propagate(False)
        light_preview_frame.bind("<Button-1>", select_light_mode)

        # Simulate UI elements for light mode
        ctk.CTkCanvas(light_preview_frame, width=200, height=200, bg="#f7f7f7", highlightthickness=0, cursor="hand2").pack()
        canvas_light = light_preview_frame.winfo_children()[0]
        # Draw circle (avatar)
        canvas_light.create_oval(30, 30, 70, 70, fill="#dddddd", outline="#dddddd")
        # Draw lines (text)
        canvas_light.create_rectangle(30, 80, 110, 95, fill="#dddddd", outline="#dddddd")
        canvas_light.create_rectangle(30, 100, 110, 115, fill="#dddddd", outline="#dddddd")
        canvas_light.create_rectangle(120, 30, 190, 40, fill="#dddddd", outline="#dddddd")
        canvas_light.create_rectangle(120, 45, 190, 55, fill="#dddddd", outline="#dddddd")
        canvas_light.create_rectangle(120, 60, 190, 70, fill="#dddddd", outline="#dddddd")
        # Draw rectangles (list items)
        canvas_light.create_rectangle(30, 130, 190, 145, fill="#e0e0e0", outline="#e0e0e0")
        canvas_light.create_rectangle(30, 150, 190, 165, fill="#e0e0e0", outline="#e0e0e0")
        canvas_light.create_rectangle(30, 170, 190, 185, fill="#e0e0e0", outline="#e0e0e0")
        canvas_light.bind("<Button-1>", select_light_mode)

        # Dark mode preview
        dark_preview_frame = ctk.CTkFrame(mode_frame, width=220, height=220, corner_radius=10, fg_color="#232323", border_width=1, border_color="#232323", cursor="hand2")
        dark_preview_frame.pack(side="left", padx=(0, 0))
        dark_preview_frame.pack_propagate(False)
        dark_preview_frame.bind("<Button-1>", select_dark_mode)

        # Simulate UI elements for dark mode
        ctk.CTkCanvas(dark_preview_frame, width=200, height=200, bg="#232323", highlightthickness=0, cursor="hand2").pack()
        canvas_dark = dark_preview_frame.winfo_children()[0]
        # Draw circle (avatar)
        canvas_dark.create_oval(30, 30, 70, 70, fill="#bdbdbd", outline="#bdbdbd")
        # Draw lines (text)
        canvas_dark.create_rectangle(30, 80, 110, 95, fill="#bdbdbd", outline="#bdbdbd")
        canvas_dark.create_rectangle(30, 100, 110, 115, fill="#bdbdbd", outline="#bdbdbd")
        canvas_dark.create_rectangle(120, 30, 190, 40, fill="#bdbdbd", outline="#bdbdbd")
        canvas_dark.create_rectangle(120, 45, 190, 55, fill="#bdbdbd", outline="#bdbdbd")
        canvas_dark.create_rectangle(120, 60, 190, 70, fill="#bdbdbd", outline="#bdbdbd")
        # Draw rectangles (list items)
        canvas_dark.create_rectangle(30, 130, 190, 145, fill="#444444", outline="#444444")
        canvas_dark.create_rectangle(30, 150, 190, 165, fill="#444444", outline="#444444")
        canvas_dark.create_rectangle(30, 170, 190, 185, fill="#444444", outline="#444444")
        canvas_dark.bind("<Button-1>", select_dark_mode)

        # Dark mode radio and label
        dark_radio = ctk.CTkRadioButton(
            mode_frame, text="Dark mode",
            variable=self.theme_var, value="dark",
            command=select_dark_mode,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#6c6c80"
        )
        dark_radio.pack(side="left", pady=(10, 0))
        dark_radio.place(in_=dark_preview_frame, relx=0.5, rely=1.08, anchor="center")

        # Apply button
        apply_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        apply_frame.pack(fill="x", padx=20, pady=20)
        
        apply_btn = ctk.CTkButton(apply_frame, text="Apply", width=100, height=35,
                                command=self.apply_settings,
                                font=ctk.CTkFont(size=14))
        apply_btn.pack(anchor="e")
        
    def change_appearance_mode(self, mode):
        self.appearance_mode = mode
        ctk.set_appearance_mode(mode)
        
    def apply_settings(self):
        # Apply display name change
        new_name = self.name_entry.get().strip()
        if new_name:
            self.display_name = new_name
            self.name_label.configure(text=self.display_name)
            
        # Show confirmation
        self.show_settings_confirmation()
        
    def show_settings_confirmation(self):
        # Simple confirmation message
        confirmation_window = ctk.CTkToplevel(self.root)
        confirmation_window.title("Settings Applied")
        confirmation_window.geometry("300x150")
        confirmation_window.resizable(False, False)
        
        # Center the window
        confirmation_window.transient(self.root)
        confirmation_window.grab_set()
        
        message_label = ctk.CTkLabel(confirmation_window, 
                                   text="Settings have been applied successfully!",
                                   font=ctk.CTkFont(size=14))
        message_label.pack(pady=40)
        
        ok_btn = ctk.CTkButton(confirmation_window, text="OK", width=80,
                             command=confirmation_window.destroy)
        ok_btn.pack(pady=10)
        
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = SaveMyCellApp()
    app.run()