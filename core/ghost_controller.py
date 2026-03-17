import pyautogui
import keyboard
import time
import subprocess
import os

class GhostController:
    """Wrapper for OS automation and computer control."""
    
    def __init__(self):
        # Set a pause after every pyautogui command for stability
        pyautogui.PAUSE = 0.5
        # Fail-safe feature: moving mouse to 0,0 cancels
        pyautogui.FAILSAFE = True
        
    def open_application(self, app_name: str) -> bool:
        """Opens an application using multiple methods."""
        try:
            app_name_lower = app_name.lower()
            print(f"Attempting to launch: {app_name}")
            
            # Method 1: Direct OS Start (for common names)
            try:
                # Common Windows App IDs or executable names
                direct_map = {
                    "whatsapp": "WhatsApp",
                    "brave": "brave",
                    "chrome": "chrome",
                    "notepad": "notepad",
                    "calc": "calc"
                }
                cmd_name = direct_map.get(app_name_lower, app_name_lower)
                subprocess.Popen(f"start {cmd_name}", shell=True)
                time.sleep(2)
                return True
            except:
                pass

            # Method 2: Windows Key Search (Fallback)
            print(f"Fallback: Using Windows Search for {app_name}")
            pyautogui.press('win')
            time.sleep(1.2)
            pyautogui.write(app_name, interval=0.1)
            time.sleep(1.2)
            pyautogui.press('enter')
            time.sleep(3)
            return True
        except Exception as e:
            print(f"Error launching {app_name}: {e}")
            return False
            
    def type_text(self, text: str) -> bool:
        """Types out the given text."""
        try:
            pyautogui.write(text, interval=0.05)
            return True
        except Exception as e:
            print(f"Error typing text: {e}")
            return False
            
    def press_key(self, key: str) -> bool:
        """Presses a specific key or hotkey combination (e.g. 'ctrl+r', 'win+l')."""
        try:
            if '+' in key:
                # Compound hotkey like ctrl+r, ctrl+shift+p, win+l
                parts = [k.strip() for k in key.split('+')]
                import pyautogui
                pyautogui.hotkey(*parts)
            else:
                import pyautogui
                pyautogui.press(key)
            return True
        except Exception as e:
            print(f"Error pressing key {key}: {e}")
            return False

    def run_command(self, cmd: str) -> bool:
        """Runs a direct subprocess command."""
        try:
            subprocess.Popen(cmd, shell=True)
            return True
        except Exception as e:
            print(f"Error running command {cmd}: {e}")
            return False

    def click_mouse(self, x: int, y: int, button: str = 'left') -> bool:
        """Clicks the mouse at specific coordinates."""
        try:
            btn = 'left' if 'left' in button.lower() else 'right'
            pyautogui.click(x=x, y=y, button=btn)
            return True
        except Exception as e:
            print(f"Error clicking mouse: {e}")
            return False
