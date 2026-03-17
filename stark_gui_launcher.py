# stark_gui_launcher.py - Auto-start launcher
"""
STARK GUI Launcher
Handles auto-start functionality and system integration
"""

import os
import sys
import subprocess
import platform
import winreg
from pathlib import Path

class AutoStartManager:
    """Manages auto-start functionality across different OS"""
    
    @staticmethod
    def is_enabled():
        """Check if auto-start is enabled"""
        system = platform.system()
        
        if system == "Windows":
            return AutoStartManager._windows_check()
        elif system == "Darwin":  # macOS
            return AutoStartManager._macos_check()
        elif system == "Linux":
            return AutoStartManager._linux_check()
        
        return False
    
    @staticmethod
    def enable():
        """Enable auto-start"""
        system = platform.system()
        
        if system == "Windows":
            return AutoStartManager._windows_enable()
        elif system == "Darwin":  # macOS
            return AutoStartManager._macos_enable()
        elif system == "Linux":
            return AutoStartManager._linux_enable()
        
        return False
    
    @staticmethod
    def disable():
        """Disable auto-start"""
        system = platform.system()
        
        if system == "Windows":
            return AutoStartManager._windows_disable()
        elif system == "Darwin":  # macOS
            return AutoStartManager._macos_disable()
        elif system == "Linux":
            return AutoStartManager._linux_disable()
        
        return False
    
    # Windows implementations
    @staticmethod
    def _windows_check():
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                               r"Software\Microsoft\Windows\CurrentVersion\Run")
            winreg.QueryValueEx(key, "STARK")
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False
    
    @staticmethod
    def _windows_enable():
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                               winreg.KEY_SET_VALUE)
            script_path = os.path.abspath(sys.argv[0])
            python_path = sys.executable
            command = f'"{python_path}" "{script_path}"'
            winreg.SetValueEx(key, "STARK", 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"Failed to enable Windows auto-start: {e}")
            return False

    @staticmethod
    def _windows_disable():
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                               winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, "STARK")
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return True
        except Exception as e:
            print(f"Failed to disable Windows auto-start: {e}")
            return False
    
    # macOS implementations
    @staticmethod
    def _macos_check():
        plist_path = Path.home() / "Library/LaunchAgents/com.stark.assistant.plist"
        return plist_path.exists()
    
    @staticmethod
    def _macos_enable():
        try:
            script_path = os.path.abspath(sys.argv[0])
            python_path = sys.executable
            
            plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.stark.assistant</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>'''
            
            plist_path = Path.home() / "Library/LaunchAgents/com.stark.assistant.plist"
            plist_path.parent.mkdir(exist_ok=True)
            
            with open(plist_path, 'w') as f:
                f.write(plist_content)
            
            # Load the launch agent
            subprocess.run(["launchctl", "load", str(plist_path)], check=True)
            return True
            
        except Exception as e:
            print(f"Failed to enable macOS auto-start: {e}")
            return False
    
    @staticmethod
    def _macos_disable():
        try:
            plist_path = Path.home() / "Library/LaunchAgents/com.stark.assistant.plist"
            
            if plist_path.exists():
                # Unload the launch agent
                subprocess.run(["launchctl", "unload", str(plist_path)], check=False)
                # Remove the plist file
                plist_path.unlink()
            
            return True
        except Exception as e:
            print(f"Failed to disable macOS auto-start: {e}")
            return False
    
    # Linux implementations
    @staticmethod
    def _linux_check():
        desktop_path = Path.home() / ".config/autostart/stark-assistant.desktop"
        return desktop_path.exists()
    
    @staticmethod
    def _linux_enable():
        try:
            script_path = os.path.abspath(sys.argv[0])
            python_path = sys.executable
            
            desktop_content = f'''[Desktop Entry]
Type=Application
Name=STARK Assistant
Exec={python_path} {script_path}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
'''
            
            desktop_path = Path.home() / ".config/autostart/stark-assistant.desktop"
            desktop_path.parent.mkdir(exist_ok=True)
            
            with open(desktop_path, 'w') as f:
                f.write(desktop_content)
            
            return True
        except Exception as e:
            print(f"Failed to enable Linux auto-start: {e}")
            return False
    
    @staticmethod
    def _linux_disable():
        try:
            desktop_path = Path.home() / ".config/autostart/stark-assistant.desktop"
            if desktop_path.exists():
                desktop_path.unlink()
            return True
        except Exception as e:
            print(f"Failed to disable Linux auto-start: {e}")
            return False


