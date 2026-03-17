"""
Main launcher script for STARK GUI
This is the entry point that users will run
"""

import sys
import os
import argparse
import platform
from pathlib import Path

# Windows registry import (only on Windows)
if platform.system() == "Windows":
    try:
        import winreg
    except ImportError:
        winreg = None

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from core.user_settings import clear_api_key, ensure_api_key, get_saved_api_key, get_settings_path, load_api_key_into_env


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
        if not winreg:
            return False
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
        if not winreg:
            return False
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                               winreg.KEY_SET_VALUE)
            
            # Get current script path
            script_path = os.path.abspath(sys.argv[0])
            python_path = sys.executable
            command = f'"{python_path}" "{script_path}" --gui --minimized'
            
            winreg.SetValueEx(key, "STARK", 0, winreg.REG_SZ, command)
            winreg.CloseKey(key)
            return True
        except Exception as e:
            print(f"Failed to enable Windows auto-start: {e}")
            return False
    
    @staticmethod
    def _windows_disable():
        if not winreg:
            return False
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                               r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                               winreg.KEY_SET_VALUE)
            winreg.DeleteValue(key, "STARK")
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return True  # Already disabled
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
            import subprocess
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
        <string>--gui</string>
        <string>--minimized</string>
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
            import subprocess
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
Exec={python_path} {script_path} --gui --minimized
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Comment=AI Desktop Assistant
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


def main():
    """Main entry point for STARK launcher"""
    parser = argparse.ArgumentParser(description="STARK Desktop Assistant")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode only")
    parser.add_argument("--gui", action="store_true", help="Run in GUI mode")
    parser.add_argument("--minimized", action="store_true", help="Start minimized to tray")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--config", type=str, help="Configuration file path")
    parser.add_argument("--autostart-enable", action="store_true", help="Enable auto-start")
    parser.add_argument("--autostart-disable", action="store_true", help="Disable auto-start")
    parser.add_argument("--autostart-status", action="store_true", help="Check auto-start status")
    parser.add_argument("--set-api-key", action="store_true", help="Prompt to save/update the Groq API key")
    parser.add_argument("--clear-api-key", action="store_true", help="Remove the saved Groq API key from user settings")
    
    args = parser.parse_args()
    
    # Handle auto-start commands
    if args.autostart_enable:
        if AutoStartManager.enable():
            print("Auto-start enabled successfully")
        else:
            print("Failed to enable auto-start")
        return
    
    if args.autostart_disable:
        if AutoStartManager.disable():
            print("Auto-start disabled successfully")
        else:
            print("Failed to disable auto-start")
        return
    
    if args.autostart_status:
        status = "enabled" if AutoStartManager.is_enabled() else "disabled"
        print(f"Auto-start is {status}")
        return

    if args.clear_api_key:
        cleared_path = clear_api_key()
        if "GROQ_API_KEY" in os.environ:
            os.environ.pop("GROQ_API_KEY", None)
        if cleared_path:
            print(f"Saved API key removed from {cleared_path}")
        else:
            print(f"No saved API key found in {get_settings_path()}")
        return
    
    # Set up environment
    if args.debug:
        os.environ["STARK_DEBUG"] = "1"
    
    if args.config:
        os.environ["STARK_CONFIG_PATH"] = args.config

    api_key = ensure_api_key(
        gui=not args.cli,
        force_prompt=args.set_api_key,
        allow_skip=True,
    )
    saved_api_key_after = get_saved_api_key()
    if api_key and saved_api_key_after and api_key == saved_api_key_after:
        print(f"Using saved API key from {get_settings_path()}")
    elif api_key:
        print("Using GROQ_API_KEY from the current environment.")
    else:
        load_api_key_into_env(prefer_saved=True)
        print("No saved API key found. STARK will continue in limited Tier 1 mode.")
    
    # Choose interface mode
    if args.cli:
        # Run CLI mode
        try:
            from stark import main as stark_main
            # Prevent launcher flags (e.g. --cli) from leaking into stark.py argparse
            sys.argv = [sys.argv[0]]
            stark_main()
        except ImportError:
            print("Error: STARK core module not found")
            print("Make sure stark.py is in the same directory")
            sys.exit(1)
        except Exception as e:
            print(f"Error running STARK CLI: {e}")
            sys.exit(1)
    else:
        # Run GUI mode (default)
        try:
            from stark_gui import STARKGUIApp
            app = STARKGUIApp()
            if args.minimized:
                app.start_minimized = True
            app.run()
        except ImportError:
            print("Error: STARK GUI module not found")
            print("Make sure stark_gui.py is in the same directory")
            print("Falling back to CLI mode...")
            try:
                from stark import main as stark_main
                stark_main()
            except ImportError:
                print("Error: No STARK modules found")
                print("Make sure stark.py is in the same directory")
                sys.exit(1)
        except Exception as e:
            print(f"GUI Error: {e}")
            print("Falling back to CLI mode...")
            try:
                from stark import main as stark_main
                sys.argv = [sys.argv[0]]
                stark_main()
            except ImportError:
                print("Error: STARK core module not found")
                sys.exit(1)


if __name__ == "__main__":
    main()
