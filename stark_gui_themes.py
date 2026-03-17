"""
Theme management for STARK GUI
Supports light and dark themes with customization
"""

class ThemeManager:
    THEMES = {
        "light": {
            "bot_bg": "#3498db",
            "bot_border": "#2980b9",
            "bot_eye": "white",
            "bot_mouth": "white",
            "status_ready": "#27ae60",
            "status_error": "#e74c3c",
            
            "chat_bg": "#ffffff",
            "chat_fg": "#2c3e50",
            "chat_input_bg": "#f8f9fa",
            "chat_user_color": "#8e44ad",
            "chat_stark_color": "#27ae60",
            "chat_system_color": "#3498db",
            
            "button_bg": "#ecf0f1",
            "button_fg": "#2c3e50",
            "button_hover": "#bdc3c7"
        },
        
        "dark": {
            "bot_bg": "#2c3e50",
            "bot_border": "#1a252f",
            "bot_eye": "#ecf0f1",
            "bot_mouth": "#ecf0f1",
            "status_ready": "#27ae60",
            "status_error": "#e74c3c",
            
            "chat_bg": "#2c3e50",
            "chat_fg": "#ecf0f1",
            "chat_input_bg": "#34495e",
            "chat_user_color": "#9b59b6",
            "chat_stark_color": "#2ecc71",
            "chat_system_color": "#3498db",
            
            "button_bg": "#34495e",
            "button_fg": "#ecf0f1",
            "button_hover": "#4a6741"
        }
    }
    
    def __init__(self, theme_name: str = "light"):
        self.current_theme = theme_name
    
    def get_color(self, element: str) -> str:
        """Get color for theme element"""
        return self.THEMES.get(self.current_theme, self.THEMES["light"]).get(element, "#000000")
    
    def set_theme(self, theme_name: str):
        """Set current theme"""
        if theme_name in self.THEMES:
            self.current_theme = theme_name
    
    def apply_to_widget(self, widget, element_type: str):
        """Apply theme colors to a widget"""
        colors = self.THEMES.get(self.current_theme, self.THEMES["light"])
        
        if element_type == "chat_display":
            widget.config(
                bg=colors["chat_bg"],
                fg=colors["chat_fg"],
                insertbackground=colors["chat_fg"]
            )
        elif element_type == "button":
            widget.config(
                bg=colors["button_bg"],
                fg=colors["button_fg"]
            )