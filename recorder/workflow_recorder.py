import os
import json
import time
import threading
from pynput import mouse, keyboard
from core.user_settings import get_workflows_path

class WorkflowRecorder:
    def __init__(self, output_path=None):
        self.output_path = output_path or str(get_workflows_path())
        self.is_recording = False
        self.events = []
        
        self.mouse_listener = None
        self.keyboard_listener = None
        
        self.start_time = 0
        self.last_event_time = 0
        
        # Debouncing
        self.typed_buffer = ""
        self.last_typed_time = 0

    def start(self):
        if self.is_recording:
            return
            
        self.is_recording = True
        self.events = []
        self.typed_buffer = ""
        self.start_time = time.time()
        self.last_event_time = self.start_time
        
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press)
        
        self.mouse_listener.start()
        self.keyboard_listener.start()
        print("Recording started...")

    def stop(self, save_name=None):
        if not self.is_recording:
            return
            
        self.is_recording = False
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            
        # Flush typing buffer
        self._flush_typed_buffer()
        print("Recording stopped.")
        
        if save_name and self.events:
            self.save_to_file(save_name)
            
        return self.events

    def _add_delay_if_needed(self):
        now = time.time()
        delay = min(now - self.last_event_time, 5.0) # Cap at 5 seconds delay
        if delay > 0.5:
            self.events.append({
                "action": "delay",
                "params": {"seconds": round(delay, 1)}
            })
        self.last_event_time = now

    def _flush_typed_buffer(self):
        if self.typed_buffer:
            self.events.append({
                "action": "type_text",
                "params": {"text": self.typed_buffer}
            })
            self.typed_buffer = ""

    def on_click(self, x, y, button, pressed):
        if not self.is_recording or not pressed:
            return
            
        self._flush_typed_buffer()
        self._add_delay_if_needed()
        self.events.append({
            "action": "click_mouse",
            "params": {"x": int(x), "y": int(y), "button": button.name}
        })

    def on_press(self, key):
        if not self.is_recording:
            return
            
        now = time.time()
        
        # Handle regular characters for typing
        try:
            if hasattr(key, 'char') and key.char is not None:
                # If there's a huge delay between keys, flush first and add delay
                if now - self.last_typed_time > 1.0 and self.typed_buffer:
                    self._flush_typed_buffer()
                    self._add_delay_if_needed()
                    
                self.typed_buffer += key.char
                self.last_typed_time = now
                self.last_event_time = now
                return
        except Exception:
            pass
            
        # Handle special keys (enter, tab, backspace mapping etc.)
        self._flush_typed_buffer()
        self._add_delay_if_needed()
        
        key_name = ""
        if hasattr(key, 'name') and key.name is not None:
            key_name = key.name
            
        # PyAutoGUI friendly names mapping
        mapping = {
            'cmd': 'win',
            'cmd_l': 'win',
            'cmd_r': 'win',
            'shift': 'shift',
            'shift_r': 'shift',
            'ctrl': 'ctrl',
            'ctrl_l': 'ctrl',
            'alt': 'alt',
            'alt_l': 'alt',
            'alt_gr': 'alt',
            'enter': 'enter',
            'space': 'space',
            'tab': 'tab',
            'backspace': 'backspace',
            'esc': 'esc',
            'up': 'up',
            'down': 'down',
            'left': 'left',
            'right': 'right'
        }
        
        mapped_key = mapping.get(key_name, key_name)
        
        if mapped_key:
            self.events.append({
                "action": "press_key",
                "params": {"key": mapped_key}
            })

    def save_to_file(self, gesture_name):
        try:
            target_path = self.output_path
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            workflows = {}
            if os.path.exists(target_path):
                with open(target_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        workflows = json.loads(content)
                        
            workflows[gesture_name] = self.events
            
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(workflows, f, indent=4)
                
            print(f"Workflow saved for gesture: '{gesture_name}' with {len(self.events)} steps.")
            return True
        except Exception as e:
            print(f"Error saving workflow: {e}")
            return False
