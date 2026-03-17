"""
GUI Configuration Manager for STARK
Handles GUI-specific settings and preferences
"""

import json
import tkinter as tk
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Tuple, Dict, Any

@dataclass
class GUIConfig:
    # Window positions
    bot_x: int = -1  # -1 means auto-position
    bot_y: int = -1
    chat_width: int = 400
    chat_height: int = 300
    
    # Appearance
    bot_size: int = 60
    bot_alpha: float = 0.8
    chat_alpha: float = 0.95
    theme: str = "light"  # light, dark
    
    # Behavior
    auto_hide_chat: bool = True
    auto_hide_delay: int = 3000  # milliseconds
    minimize_to_tray: bool = True
    start_minimized: bool = True
    
    # Quick actions
    quick_actions: list = None
    
    def __post_init__(self):
        if self.quick_actions is None:
            self.quick_actions = [
                ("Time", "what time is it?"),
                ("Files", "list files"),
                ("System", "system status"),
                ("Help", "help")
            ]

class GUIConfigManager:
    def __init__(self, config_path: str = "stark_gui_config.json"):
        self.config_path = Path(config_path)
        self.config = self.load_config()
    
    def load_config(self) -> GUIConfig:
        """Load GUI configuration from file"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                return GUIConfig(**data)
            except Exception as e:
                print(f"Error loading GUI config: {e}")
        
        return GUIConfig()
    
    def save_config(self):
        """Save GUI configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(asdict(self.config), f, indent=2)
        except Exception as e:
            print(f"Error saving GUI config: {e}")
    
    def update_bot_position(self, x: int, y: int):
        """Update bot position"""
        self.config.bot_x = x
        self.config.bot_y = y
        self.save_config()
    
    def get_bot_position(self, screen_width: int, screen_height: int) -> Tuple[int, int]:
        """Get bot position, with auto-positioning if needed"""
        if self.config.bot_x == -1 or self.config.bot_y == -1:
            # Auto-position in bottom-right
            x = screen_width - self.config.bot_size - 20
            y = screen_height - self.config.bot_size - 100
            return x, y
        
        return self.config.bot_x, self.config.bot_y