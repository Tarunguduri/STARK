"""
Cross-platform notification system for STARK
"""

import platform
import subprocess
from typing import Optional

class NotificationManager:
    @staticmethod
    def show_notification(title: str, message: str, icon: str = None):
        """Show system notification"""
        system = platform.system()
        
        if system == "Windows":
            NotificationManager._windows_notify(title, message, icon)
        elif system == "Darwin":  # macOS
            NotificationManager._macos_notify(title, message, icon)
        elif system == "Linux":
            NotificationManager._linux_notify(title, message, icon)
    
    @staticmethod
    def _windows_notify(title: str, message: str, icon: str = None):
        """Show Windows notification"""
        try:
            import win10toast
            toaster = win10toast.ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)
        except ImportError:
            # Fallback using PowerShell
            try:
                ps_script = f'''
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.MessageBox]::Show("{message}", "{title}")
'''
                subprocess.run(["powershell", "-Command", ps_script], 
                             creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception as e:
                print(f"Notification failed: {e}")
    
    @staticmethod
    def _macos_notify(title: str, message: str, icon: str = None):
        """Show macOS notification"""
        try:
            script = f'display notification "{message}" with title "{title}"'
            subprocess.run(["osascript", "-e", script])
        except Exception as e:
            print(f"Notification failed: {e}")
    
    @staticmethod
    def _linux_notify(title: str, message: str, icon: str = None):
        """Show Linux notification"""
        try:
            cmd = ["notify-send", title, message]
            if icon:
                cmd.extend(["-i", icon])
            subprocess.run(cmd)
        except Exception as e:
            print(f"Notification failed: {e}")
