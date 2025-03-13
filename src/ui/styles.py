import darkdetect

def update_theme(app):
    if app.is_dark_mode:
        app.background_color = "#2D2D2D"
        app.text_color = "#FFFFFF"
        app.secondary_bg = "#3B3B3B"
    else:
        app.background_color = "#F3F3F3"
        app.text_color = "#000000"
        app.secondary_bg = "#E6E6E6"
    app.root.configure(bg=app.background_color)
    configure_styles(app)

def check_theme_change(app):
    new_theme = darkdetect.isDark()
    if new_theme != app.is_dark_mode:
        app.is_dark_mode = new_theme
        update_theme(app)
        app.show_main_screen()
    app.root.after(1000, lambda: check_theme_change(app))

def configure_styles(app):
    app.style.configure("Main.TFrame", background=app.background_color)
    app.style.configure("Custom.TButton",
                        font=(app.font_type, 11),
                        padding=10,
                        background=app.accent_color,
                        foreground="#FFFFFF",
                        borderwidth=0,
                        relief="flat",
                        bordercolor=app.accent_color)
    app.style.map("Custom.TButton",
                  background=[("active", "#005BA1")],
                  foreground=[("active", "#FFFFFF")])
    app.style.configure("Stop.TButton",
                        font=(app.font_type, 11),
                        padding=10,
                        background="#D83B01",
                        foreground="#FFFFFF",
                        borderwidth=0,
                        relief="flat")
    app.style.map("Stop.TButton",
                  background=[("active", "#A12D00")],
                  foreground=[("active", "#FFFFFF")])
    app.style.configure("Back.TButton",
                        font=(app.font_type, 10),
                        padding=10,
                        background=app.secondary_bg,
                        foreground=app.text_color,
                        borderwidth=0,
                        relief="flat")
    app.style.map("Back.TButton",
                  background=[("active", "#D0D0D0" if not app.is_dark_mode else "#404040")],
                  foreground=[("active", app.text_color)])
    app.style.configure("Title.TLabel",
                        font=(app.font_type, 14, "bold"),
                        foreground=app.text_color,
                        background=app.background_color)
    app.style.configure("Prompt.TLabel",
                        font=(app.font_type, 20, "bold"),
                        foreground="#D83B01",
                        background=app.background_color)
    app.style.configure("Info.TLabel",
                        font=(app.font_type, 11),
                        foreground="#666666" if not app.is_dark_mode else "#AAAAAA",
                        background=app.background_color,
                        wraplength=600)