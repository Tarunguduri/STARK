"""
STARK GUI System - Complete Floating Bot Interface
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import threading
import time
import json
import os
import sys
from pathlib import Path
from typing import Optional, Callable
import logging
from datetime import datetime

# System tray imports
try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    print("Warning: pystray/PIL not available. Install with: pip install pillow pystray")

# Import STARK core
try:
    from stark import STARK, STARKConfig
    STARK_AVAILABLE = True
except ImportError:
    STARK_AVAILABLE = False
    print("Warning: STARK core not found. Using mock implementation.")

try:
    import cv2
    from PIL import Image, ImageTk
    from vision.camera import CameraComponent
    from vision.gesture_detector import GestureDetector
    VISION_AVAILABLE = True
except ImportError:
    cv2 = None
    Image = None
    ImageTk = None
    CameraComponent = None
    GestureDetector = None
    VISION_AVAILABLE = False
    print("Warning: Vision dependencies not available. Camera/gestures disabled.")

try:
    from recorder.workflow_recorder import WorkflowRecorder
    RECORDER_AVAILABLE = True
except ImportError:
    WorkflowRecorder = None
    RECORDER_AVAILABLE = False
    print("Warning: Workflow recorder not available. Install pynput.")

logger = logging.getLogger(__name__)

# Voice imports (optional)
try:
    from core.voice_engine import VoiceEngine, SpeechListener
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False
    print("Warning: Voice engine not available")

from core.reasoning import load_workflows, normalize_gesture_name
from core.user_settings import clear_api_key, ensure_api_key, get_settings_path, load_api_key_into_env

# Constants
CHAT_WIDTH = 550
CHAT_HEIGHT = 700
VISION_HEIGHT = 200


class MockSTARK:
    """Mock STARK implementation for testing"""
    def __init__(self, config=None):
        self.running = True

    def process_request(self, user_input: str) -> str:
        time.sleep(0.5)
        return f"Mock response to: {user_input}"

    def startup_check(self) -> bool:
        return True

    def shutdown(self):
        self.running = False


class FloatingBotWidget:
    """Small floating bot icon"""

    def __init__(self, main_app, size=60):
        self.main_app = main_app
        self.size = size
        self.is_dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0

        self.root = tk.Toplevel()
        self.root.title("STARK Bot")
        self.root.geometry(f"{size}x{size}")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.8)

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = screen_width - size - 20
        y = screen_height - size - 100
        self.root.geometry(f"{size}x{size}+{x}+{y}")

        self.canvas = tk.Canvas(self.root, width=size, height=size, bg="#2c3e50", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.draw_bot_icon()

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Enter>", self.on_hover_enter)
        self.canvas.bind("<Leave>", self.on_hover_leave)
        self.root.bind("<Button-1>", self.on_click)
        self.root.bind("<B1-Motion>", self.on_drag)
        self.root.bind("<ButtonRelease-1>", self.on_release)

    def draw_bot_icon(self):
        self.canvas.delete("all")
        margin = 8
        self.canvas.create_oval(margin, margin, self.size - margin, self.size - margin,
                                fill="#3498db", outline="#2980b9", width=2)
        eye_size = 6
        eye_y = self.size // 3
        left_eye_x = self.size // 3
        right_eye_x = 2 * self.size // 3
        self.canvas.create_oval(left_eye_x - eye_size//2, eye_y - eye_size//2,
                                left_eye_x + eye_size//2, eye_y + eye_size//2, fill="white", outline="white")
        self.canvas.create_oval(right_eye_x - eye_size//2, eye_y - eye_size//2,
                                right_eye_x + eye_size//2, eye_y + eye_size//2, fill="white", outline="white")
        mouth_y = 2 * self.size // 3
        self.canvas.create_arc(self.size // 4, mouth_y - 5, 3 * self.size // 4, mouth_y + 10,
                               start=0, extent=180, fill="white", outline="white", width=2)
        status_color = "#27ae60" if self.main_app.stark_ready else "#e74c3c"
        self.canvas.create_oval(self.size - 15, 5, self.size - 5, 15, fill=status_color, outline=status_color)

    def on_hover_enter(self, event): self.root.attributes("-alpha", 1.0)
    def on_hover_leave(self, event): self.root.attributes("-alpha", 0.8)

    def on_click(self, event):
        self.drag_start_x = event.x_root
        self.drag_start_y = event.y_root
        self.is_dragging = False

    def on_drag(self, event):
        dx = event.x_root - self.drag_start_x
        dy = event.y_root - self.drag_start_y
        if abs(dx) > 5 or abs(dy) > 5:
            self.is_dragging = True
            x = self.root.winfo_x() + dx
            y = self.root.winfo_y() + dy
            self.root.geometry(f"{self.size}x{self.size}+{x}+{y}")
            self.drag_start_x = event.x_root
            self.drag_start_y = event.y_root

    def on_release(self, event):
        if not self.is_dragging:
            self.main_app.toggle_chat_interface()
        self.is_dragging = False

    def update_status(self, ready: bool): self.draw_bot_icon()
    def hide(self): self.root.withdraw()
    def show(self): self.root.deiconify()


class ChatInterface:
    """Expandable chat interface window"""

    def __init__(self, main_app):
        self.main_app = main_app
        self.is_visible = False
        self.command_history = []
        self.history_index = -1

        self.root = tk.Toplevel()
        self.root.title("STARK Assistant")
        self.root.geometry(f"{CHAT_WIDTH}x{CHAT_HEIGHT}")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.97)
        self.root.withdraw()

        self.create_interface()
        self.root.bind("<FocusOut>", self.on_focus_out)

    def create_interface(self):
        main_frame = tk.Frame(self.root, bg="#2c3e50", padx=2, pady=2)
        main_frame.pack(fill="both", expand=True)

        content_frame = tk.Frame(main_frame, bg="#ecf0f1", padx=10, pady=10)
        content_frame.pack(fill="both", expand=True)

        # --- Header ---
        header_frame = tk.Frame(content_frame, bg="#ecf0f1")
        header_frame.pack(fill="x", pady=(0, 8))

        tk.Label(header_frame, text="STARK Assistant", font=("Arial", 12, "bold"),
                 bg="#ecf0f1", fg="#2c3e50").pack(side="left")

        self.status_label = tk.Label(header_frame, text="●", font=("Arial", 12),
                                     bg="#ecf0f1", fg="#27ae60" if self.main_app.stark_ready else "#e74c3c")
        self.status_label.pack(side="right")

        tk.Button(header_frame, text="×", font=("Arial", 12, "bold"), width=3,
                  command=self.hide, bg="#e74c3c", fg="white", relief="flat").pack(side="right", padx=(5, 0))

        # --- Vision / Camera Area ---
        self.vision_frame = tk.Frame(content_frame, bg="#000000", height=VISION_HEIGHT)
        self.vision_frame.pack(fill="x", pady=(0, 8))
        self.vision_frame.pack_propagate(False)

        self.camera_label = tk.Label(self.vision_frame, bg="#000000")
        self.camera_label.pack(fill="both", expand=True)

        self.vision_status = tk.Label(self.camera_label, text="Vision: Active",
                                      bg="#27ae60", fg="white", font=("Arial", 8, "bold"))
        self.vision_status.place(x=5, y=5)

        # --- Record Buttons ---
        rec_frame = tk.Frame(content_frame, bg="#ecf0f1")
        rec_frame.pack(fill="x", pady=(0, 5))

        self.start_rec_btn = tk.Button(rec_frame, text="▶ Start Recording",
                                       command=self.main_app.start_recording,
                                       bg="#e67e22", fg="white", font=("Arial", 8, "bold"),
                                       relief="flat", padx=8, pady=4)
        self.start_rec_btn.pack(side="left", padx=(0, 5))

        self.stop_rec_btn = tk.Button(rec_frame, text="■ Stop Recording",
                                      command=self.main_app.stop_recording,
                                      bg="#c0392b", fg="white", font=("Arial", 8, "bold"),
                                      state="disabled", relief="flat", padx=8, pady=4)
        self.stop_rec_btn.pack(side="left")

        # --- Quick Action Buttons (PINNED BOTTOM) ---
        self.actions_frame = tk.Frame(content_frame, bg="#dfe6e9")
        self.actions_frame.pack(side="bottom", fill="x", pady=(5, 0))

        for label, cmd in [("⏰ Time", "what time is it?"), ("📁 Files", "list files"),
                            ("💻 System", "system status"), ("❓ Help", "help")]:
            tk.Button(self.actions_frame, text=label, width=10,
                      command=lambda c=cmd: self.quick_action(c),
                      bg="#636e72", fg="white", relief="flat",
                      font=("Arial", 8), pady=4).pack(side="left", padx=2, pady=4)

        # --- Input Frame (PINNED BOTTOM ABOVE ACTIONS) ---
        self.input_frame = tk.Frame(content_frame, bg="#ecf0f1")
        self.input_frame.pack(side="bottom", fill="x", pady=(5, 3))

        self.input_field = tk.Entry(self.input_frame, font=("Arial", 11), relief="flat",
                                    bg="#ffffff", fg="#2c3e50", insertbackground="#2c3e50")
        self.input_field.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=6)
        self.input_field.bind("<Return>", self.send_message)
        self.input_field.bind("<Up>", self.previous_command)
        self.input_field.bind("<Down>", self.next_command)

        self.send_btn = tk.Button(self.input_frame, text="Send", command=self.send_message,
                                  bg="#2980b9", fg="white", relief="flat",
                                  font=("Arial", 10, "bold"), padx=16, pady=4)
        self.send_btn.pack(side="right")

        # Mic button
        self.mic_active = False
        self.mic_btn = tk.Button(self.input_frame, text="🎤", command=self.toggle_mic,
                                  bg="#636e72", fg="white", relief="flat",
                                  font=("Arial", 10), padx=8, pady=4)
        self.mic_btn.pack(side="right", padx=(0, 4))

        # Voice toggle in header (will be wired after main_app has voice)
        self.voice_indicator = tk.Label(header_frame, text="🔊", font=("Arial", 10),
                                        bg="#ecf0f1", fg="#27ae60", cursor="hand2")
        self.voice_indicator.pack(side="right", padx=(0, 8))
        self.voice_indicator.bind("<Button-1>", lambda e: self.toggle_voice())

        # --- Chat Display (EXPANDS IN THE MIDDLE) ---
        chat_frame = tk.Frame(content_frame, bg="#ecf0f1")
        chat_frame.pack(side="top", fill="both", expand=True, pady=(0, 5))

        self.chat_display = tk.Text(chat_frame, state="disabled",
                                    font=("Consolas", 10), bg="#ffffff", fg="#2c3e50",
                                    wrap="word", relief="flat", padx=8, pady=8)

        chat_scroll = tk.Scrollbar(chat_frame, command=self.chat_display.yview)
        self.chat_display.config(yscrollcommand=chat_scroll.set)
        self.chat_display.pack(side="left", fill="both", expand=True)
        chat_scroll.pack(side="right", fill="y")

        # Welcome message
        self.add_message("STARK", "Hello! I'm ready to assist you. What can I do for you?", "#2980b9")

    def add_message(self, sender: str, message: str, color: str = "#2c3e50"):
        self.chat_display.config(state="normal")
        timestamp = datetime.now().strftime("%H:%M")
        self.chat_display.insert("end", f"[{timestamp}] {sender}: ", ("sender",))
        self.chat_display.insert("end", f"{message}\n\n", ("message",))
        self.chat_display.tag_config("sender", foreground=color, font=("Arial", 9, "bold"))
        self.chat_display.tag_config("message", foreground="#2c3e50")
        self.chat_display.see("end")
        self.chat_display.config(state="disabled")

    def send_message(self, event=None):
        message = self.input_field.get().strip()
        if not message:
            return
        if message not in self.command_history:
            self.command_history.append(message)
        self.history_index = len(self.command_history)
        self.input_field.delete(0, "end")
        self.add_message("You", message, "#8e44ad")
        self.send_btn.config(state="disabled", text="...")
        self.input_field.config(state="disabled")
        threading.Thread(target=self.process_message, args=(message,), daemon=True).start()

    def process_message(self, message: str):
        try:
            response = self.main_app.process_stark_request(message)
            self.root.after(0, self.handle_response, response)
        except Exception as e:
            self.root.after(0, self.handle_response, f"Error: {str(e)}")

    def handle_response(self, response: str):
        self.add_message("STARK", response, "#27ae60")
        self.send_btn.config(state="normal", text="Send")
        self.input_field.config(state="normal")
        self.input_field.focus()
        # Speak response
        if hasattr(self.main_app, 'voice') and self.main_app.voice:
            self.main_app.voice.speak(response)

    def quick_action(self, command: str):
        self.input_field.delete(0, "end")
        self.input_field.insert(0, command)
        self.send_message()

    def previous_command(self, event):
        if self.command_history and self.history_index > 0:
            self.history_index -= 1
            self.input_field.delete(0, "end")
            self.input_field.insert(0, self.command_history[self.history_index])

    def next_command(self, event):
        if self.command_history and self.history_index < len(self.command_history) - 1:
            self.history_index += 1
            self.input_field.delete(0, "end")
            self.input_field.insert(0, self.command_history[self.history_index])
        elif self.history_index >= len(self.command_history) - 1:
            self.history_index = len(self.command_history)
            self.input_field.delete(0, "end")

    def toggle_voice(self):
        """Toggle TTS on/off."""
        if hasattr(self.main_app, 'voice') and self.main_app.voice:
            enabled = self.main_app.voice.toggle()
            self.voice_indicator.config(
                fg="#27ae60" if enabled else "#636e72",
                text="🔊" if enabled else "🔇"
            )

    def toggle_mic(self):
        """Toggle microphone listening."""
        if not hasattr(self.main_app, 'speech_listener') or not self.main_app.speech_listener:
            self.add_message("System", "Speech recognition not available. Install: pip install SpeechRecognition pyaudio", "#e74c3c")
            return
        self.main_app.speech_listener.toggle()

    def on_mic_state(self, listening: bool):
        """Called when microphone starts/stops. Updates mic button color."""
        def _update():
            if listening:
                self.mic_btn.config(bg="#e74c3c", text="⏹")
                self.input_field.config(fg="#e74c3c")
            else:
                self.mic_btn.config(bg="#636e72", text="🎤")
                self.input_field.config(fg="#2c3e50")
        try:
            self.root.after(0, _update)
        except Exception:
            pass

    def on_voice_result(self, text: str):
        """Called when speech is recognised — auto-fills and sends."""
        def _send():
            self.input_field.delete(0, "end")
            self.input_field.insert(0, text)
            self.send_message()
        try:
            self.root.after(0, _send)
        except Exception:
            pass

    def show(self, x: int = None, y: int = None):
        if x is not None and y is not None:
            self.root.geometry(f"{CHAT_WIDTH}x{CHAT_HEIGHT}+{x}+{y}")
        self.root.deiconify()
        self.root.lift()
        self.input_field.focus()
        self.is_visible = True

    def hide(self):
        self.root.withdraw()
        self.is_visible = False

    def toggle(self):
        self.hide() if self.is_visible else self.show()

    def on_focus_out(self, event):
        self.root.after(5000, self.auto_hide)

    def auto_hide(self):
        try:
            if self.root.focus_get() is None and self.is_visible:
                self.hide()
        except:
            pass

    def update_status(self, ready: bool):
        self.status_label.config(fg="#27ae60" if ready else "#e74c3c")

    def update_vision(self, frame, gesture):
        if not VISION_AVAILABLE:
            self.vision_status.config(text="Vision: Unavailable", bg="#c0392b")
            return
        if frame is not None:
            target_w = CHAT_WIDTH - 20
            target_h = VISION_HEIGHT
            frame = cv2.resize(frame, (target_w, target_h))
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(img)
            imgtk = ImageTk.PhotoImage(image=img)
            self.camera_label.imgtk = imgtk
            self.camera_label.configure(image=imgtk)
        if gesture and gesture != "None":
            self.vision_status.config(text=f"👋 {gesture}", bg="#e67e22")
        else:
            self.vision_status.config(text="Vision: Active", bg="#27ae60")


class SystemTrayManager:
    """Manages system tray icon"""

    def __init__(self, main_app):
        self.main_app = main_app
        self.icon = None
        if not TRAY_AVAILABLE:
            return
        self.create_icon()

    def create_icon(self):
        width, height = 64, 64
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse([8, 8, width-8, height-8], fill=(52, 152, 219, 255), outline=(41, 128, 185, 255))
        draw.ellipse([18, 20, 26, 28], fill=(255, 255, 255, 255))
        draw.ellipse([38, 20, 46, 28], fill=(255, 255, 255, 255))
        draw.arc([20, 35, 44, 50], start=0, end=180, fill=(255, 255, 255, 255), width=2)

        menu = pystray.Menu(
            item('Show STARK', lambda: self.main_app.show_chat_interface()),
            item('Hide Bot', lambda: self.main_app.toggle_bot_visibility()),
            pystray.Menu.SEPARATOR,
            item('Settings', lambda: self.main_app.show_settings()),
            pystray.Menu.SEPARATOR,
            item('Quit', lambda: self.main_app.quit())
        )
        self.icon = pystray.Icon("STARK", image, "STARK Assistant", menu)

    def start(self):
        if self.icon:
            threading.Thread(target=self.icon.run, daemon=True).start()

    def stop(self):
        if self.icon:
            self.icon.stop()


class STARKGUIApp:
    """Main GUI application controller"""

    def __init__(self):
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        self.is_running = True
        self.root = tk.Tk()
        self.root.withdraw()

        self.stark_ready = False
        self.stark = None
        self.start_minimized = False
        self.initialize_stark()

        # Vision components
        self.camera = None
        self.gesture_detector = None
        self.vision_active = False
        if VISION_AVAILABLE and CameraComponent and GestureDetector:
            self.camera = CameraComponent()
            self.camera.start()
            self.gesture_detector = GestureDetector()
            self.vision_active = True
        self.last_gesture_time = 0
        self.gesture_cooldown = 3.0
        self.last_seen_gesture = None
        self.gesture_streak = 0
        self.gesture_streak_required = 5
        self.last_triggered_gesture = None

        self.workflow_recorder = WorkflowRecorder() if RECORDER_AVAILABLE else None

        # Voice engine (TTS + Mic)
        self.voice = None
        self.speech_listener = None
        if VOICE_AVAILABLE:
            try:
                self.voice = VoiceEngine()
                self.speech_listener = SpeechListener(
                    on_result=lambda text: self.chat_interface.on_voice_result(text),
                    on_state_change=lambda s: self.chat_interface.on_mic_state(s)
                )
                logger.info("VoiceEngine and SpeechListener initialized")
            except Exception as e:
                logger.warning(f"Voice init failed: {e}")

        # GUI components
        self.floating_bot = FloatingBotWidget(self)
        self.chat_interface = ChatInterface(self)

        # Wire speech listener callbacks now that chat_interface exists
        if self.speech_listener and self.voice:
            self.speech_listener.on_result = lambda text: self.chat_interface.on_voice_result(text)
            self.speech_listener.on_state_change = lambda s: self.chat_interface.on_mic_state(s)

        # Start vision loop only when vision stack is available
        if self.vision_active:
            threading.Thread(target=self.vision_loop, daemon=True).start()

        # System tray
        self.tray_manager = SystemTrayManager(self) if TRAY_AVAILABLE else None
        if self.tray_manager:
            self.tray_manager.start()

        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        logger.info("STARK GUI Application initialized")

    def initialize_stark(self):
        try:
            if STARK_AVAILABLE:
                config = STARKConfig.load_from_file()
                self.stark = STARK(config)
                self.root.after(1000, lambda: threading.Thread(target=self.startup_check, daemon=True).start())
            else:
                self.stark = MockSTARK()
                self.stark_ready = True
        except Exception as e:
            logger.error(f"Failed to initialize STARK: {e}")
            self.stark = MockSTARK()
            self.stark_ready = False

    def startup_check(self):
        try:
            if not self.is_running:
                return
            self.stark_ready = self.stark.startup_check()
            logger.info(f"STARK startup check: {'Success' if self.stark_ready else 'Failed'}")
            self.root.after(0, self.update_status_indicators)
        except Exception as e:
            logger.error(f"STARK startup check failed: {e}")
            self.stark_ready = False

    def update_status_indicators(self):
        self.floating_bot.update_status(self.stark_ready)
        self.chat_interface.update_status(self.stark_ready)

    def process_stark_request(self, message: str) -> str:
        try:
            if self.stark and self.stark_ready:
                return self.stark.process_request(message)
            else:
                return "STARK is not ready. Please check the system status."
        except Exception as e:
            logger.error(f"Error processing STARK request: {e}")
            return f"Error processing request: {str(e)}"

    def toggle_chat_interface(self):
        if self.chat_interface.is_visible:
            self.chat_interface.hide()
        else:
            bot_x = self.floating_bot.root.winfo_x()
            bot_y = self.floating_bot.root.winfo_y()
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            chat_x = max(0, min(bot_x - (CHAT_WIDTH // 2), screen_width - CHAT_WIDTH))
            chat_y = max(0, min(bot_y - CHAT_HEIGHT - 20, screen_height - CHAT_HEIGHT))
            self.chat_interface.show(chat_x, chat_y)

    def show_chat_interface(self):
        if not self.chat_interface.is_visible:
            self.toggle_chat_interface()

    def toggle_bot_visibility(self):
        try:
            if self.floating_bot.root.winfo_viewable():
                self.floating_bot.hide()
            else:
                self.floating_bot.show()
        except:
            self.floating_bot.show()

    def show_settings(self):
        win = tk.Toplevel(self.root)
        win.title("STARK Settings")
        win.geometry("360x260")
        win.attributes("-topmost", True)
        win.configure(bg="#ecf0f1")
        tk.Label(win, text="STARK Settings", font=("Arial", 14, "bold"), bg="#ecf0f1").pack(pady=10)
        api_key_status = "Configured" if load_api_key_into_env(prefer_saved=True) else "Not configured"
        tk.Label(
            win,
            text=f"Groq API Key: {api_key_status}",
            font=("Arial", 10),
            bg="#ecf0f1",
        ).pack(pady=5)
        tk.Button(
            win,
            text="Set / Update API Key",
            command=lambda: self.configure_api_key(win),
            bg="#27ae60",
            fg="white",
        ).pack(pady=5)
        tk.Button(
            win,
            text="Clear Saved API Key",
            command=lambda: self.clear_saved_api_key(win),
            bg="#c0392b",
            fg="white",
        ).pack(pady=5)
        tk.Button(win, text="Reset Bot Position", command=self.reset_bot_position,
                  bg="#3498db", fg="white").pack(pady=5)
        tk.Button(win, text="Close", command=win.destroy, bg="#95a5a6", fg="white", padx=20).pack(pady=10)

    def configure_api_key(self, parent_window=None):
        api_key = ensure_api_key(gui=True, force_prompt=True, parent=parent_window or self.root, allow_skip=False)
        if api_key:
            self.chat_interface.add_message(
                "System",
                f"API key saved to {get_settings_path()}",
                "#27ae60",
            )

    def clear_saved_api_key(self, parent_window=None):
        cleared_path = clear_api_key()
        os.environ.pop("GROQ_API_KEY", None)
        if cleared_path:
            self.chat_interface.add_message("System", f"Removed saved API key from {cleared_path}", "#e67e22")
        else:
            self.chat_interface.add_message("System", "No saved API key was found.", "#e67e22")

    def reset_bot_position(self):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.floating_bot.root.geometry(f"60x60+{screen_width - 80}+{screen_height - 160}")

    def start_recording(self):
        if not self.workflow_recorder:
            self.chat_interface.add_message("System", "Workflow recorder unavailable (install pynput).", "#e74c3c")
            return
        self.workflow_recorder.start()
        self.chat_interface.start_rec_btn.config(state="disabled")
        self.chat_interface.stop_rec_btn.config(state="normal")
        self.chat_interface.add_message("System", "Recording started... perform your actions.", "#e67e22")

    def stop_recording(self):
        if not self.workflow_recorder:
            return
        events = self.workflow_recorder.stop()
        self.chat_interface.start_rec_btn.config(state="normal")
        self.chat_interface.stop_rec_btn.config(state="disabled")
        if events:
            gesture_name = simpledialog.askstring("Save Workflow",
                                                   "Enter gesture name to bind (e.g., 'Open Palm'):",
                                                   parent=self.root)
            if gesture_name:
                gesture_name = gesture_name.title()
                self.workflow_recorder.save_to_file(gesture_name)
                self.chat_interface.add_message("System", f"Saved workflow for gesture: '{gesture_name}'", "#27ae60")
            else:
                self.chat_interface.add_message("System", "Recording discarded.", "#e74c3c")
        else:
            self.chat_interface.add_message("System", "No events recorded.", "#e74c3c")

    def try_execute_custom_workflow(self, gesture):
        try:
            workflows = load_workflows()
            gesture_title = normalize_gesture_name(gesture)
            for key, steps in workflows.items():
                if normalize_gesture_name(key) == gesture_title:
                    from core.workflow_engine import WorkflowEngine

                    allowed, remaining = WorkflowEngine.can_trigger_workflow(
                        key,
                        cooldown_seconds=self.gesture_cooldown,
                    )
                    if not allowed:
                        logger.info(
                            "[System] Ignoring gesture %s; cooldown %.2fs remaining",
                            key,
                            remaining,
                        )
                        return False
                    threading.Thread(target=self._run_workflow_steps, args=(key, steps), daemon=True).start()
                    return True
        except Exception as e:
            logger.error(f"Error executing custom workflow for {gesture}: {e}")
        return False

    def _run_workflow_steps(self, gesture, steps):
        self.root.after(0, self.chat_interface.add_message, "System",
                        f"Executing custom workflow for '{gesture}'...", "#8e44ad")
        try:
            from core.workflow_engine import WorkflowEngine
            engine = WorkflowEngine(self.stark.plugin_manager)
            success = engine.execute_workflow(gesture, steps)
            msg = "Workflow completed." if success else "Workflow failed."
            color = "#27ae60" if success else "#e74c3c"
            self.root.after(0, self.chat_interface.add_message, "System", msg, color)
        except Exception as e:
            self.root.after(0, self.chat_interface.add_message, "System", f"Error in workflow: {e}", "#e74c3c")

    def vision_loop(self):
        import builtins
        while self.is_running:
            # Check if activate_listening was triggered by a workflow action
            if getattr(builtins, "_stark_activate_mic", False):
                builtins._stark_activate_mic = False
                if self.speech_listener:
                    try:
                        self.speech_listener.start()
                        self.root.after(0, self.chat_interface.add_message,
                                        "STARK", "Yes. I'm listening.", "#9b59b6")
                    except Exception:
                        pass

            if self.vision_active and self.camera and self.gesture_detector:
                frame = self.camera.get_frame()
                if frame is not None:
                    gesture, annotated_frame = self.gesture_detector.detect_gesture(frame)
                    self.root.after(0, self.chat_interface.update_vision, annotated_frame, gesture)

                    if gesture not in ["None", "Unknown"]:
                        if gesture == self.last_seen_gesture:
                            self.gesture_streak += 1
                        else:
                            self.last_seen_gesture = gesture
                            self.gesture_streak = 1

                        if self.gesture_streak < self.gesture_streak_required:
                            time.sleep(0.05)
                            continue

                        current_time = time.time()
                        # Edge-trigger: run once per stable gesture hold.
                        # Same gesture must be released/changed before retrigger.
                        is_new_trigger = gesture != self.last_triggered_gesture
                        cooldown_ok = (current_time - self.last_gesture_time) > self.gesture_cooldown
                        if is_new_trigger and cooldown_ok:
                            self.last_gesture_time = current_time
                            self.gesture_streak = 0
                            self.last_triggered_gesture = gesture
                            # Custom workflows (from workflows.json) take priority
                            if self.try_execute_custom_workflow(gesture):
                                # Speak the mode name
                                mode_msgs = {
                                    "Open Palm":     "Gesture recognized. Initializing coding workspace.",
                                    "Peace Sign":    "Research mode activated.",
                                    "Rock Sign":     "Entertainment mode activated.",
                                    "Fist":          "Focus mode activated.",
                                    "Pointing":      "Opening browser.",
                                    "Single Finger": "Yes. I'm listening.",
                                    "OK Sign":       "All systems go. Searching documentation.",
                                }
                                msg = mode_msgs.get(gesture, f"{gesture} workflow triggered.")
                                self.root.after(0, self.chat_interface.add_message, "STARK", msg, "#9b59b6")
                                if self.voice:
                                    try:
                                        threading.Thread(target=self.voice.speak, args=(msg,), daemon=True).start()
                                    except Exception:
                                        pass
                                time.sleep(0.1)
                                continue
                    else:
                        self.last_seen_gesture = None
                        self.gesture_streak = 0
                        # Re-arm trigger after hand is neutral/unknown
                        self.last_triggered_gesture = None
            time.sleep(0.05)


    def run(self):
        logger.info("Starting STARK GUI Application")
        print("STARK GUI System Starting...")
        print("- Click the floating bot icon to open chat")
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            logger.info("Application interrupted")
        finally:
            self.cleanup()

    def cleanup(self):
        self.is_running = False
        if self.tray_manager:
            self.tray_manager.stop()
        if self.voice:
            try:
                self.voice.stop()
            except Exception:
                pass
        if self.speech_listener:
            try:
                self.speech_listener.stop()
            except Exception:
                pass
        if self.stark and hasattr(self.stark, 'shutdown'):
            try:
                self.stark.shutdown()
            except Exception:
                pass
        try:
            self.root.quit()
        except Exception:
            pass

    def quit(self):
        self.vision_active = False
        if hasattr(self, 'camera'):
            self.camera.stop()
        self.cleanup()
        sys.exit(0)


def main():
    try:
        ensure_api_key(gui=True, allow_skip=True)
        app = STARKGUIApp()
        app.run()
    except Exception as e:
        print(f"Error starting STARK GUI: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
