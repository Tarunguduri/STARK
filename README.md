# 🦾 STARK: Hybrid AI Desktop Assistant

STARK is a powerful, Windows-focused desktop assistant that merges LLM reasoning with advanced OS automation, computer vision, and voice interaction. It's designed to be your ultimate digital companion, handling everything from coding workspaces to media control via natural language and gestures.

---

## 🚀 Key Features

### 🔍 Smart App Automation
- **Multi-Discovery Engine:** Finds apps via Registry, Shell, Start Menu, and WindowsApps (UWP).
- **Control Everything:** Launch apps, open URLs, run terminal commands, type text, and press hotkeys.

### 🎵 Seamless Media Playback
- **YouTube Direct:** Instantly opens and plays the first matching video result in your browser.
- **Spotify Pro:** Launches the desktop app, searches for your track, and hits play automatically.

### 🖐 Gesture-Triggered Workflows
STARK recognizes distinct hand gestures to trigger complex multi-step automations:

| Gesture | Mode | Workflow Description |
| :--- | :--- | :--- |
| ✋ **Open Palm** | **Coding Workspace** | Opens VS Code, creates project folder, opens terminal, plays lofi. |
| ✌️ **Peace Sign** | **Research Mode** | Opens Brave browser, searches AI news, opens arXiv. |
| 🤟 **Rock Sign** | **Entertainment** | Opens YouTube party playlist and sets volume to 70%. |
| ✊ **Fist** | **Focus Mode** | Mutes system, closes distractions (Chrome/Spotify), opens Notepad. |
| 👉 **Pointing** | **Quick Browser** | Instantly launches the Brave browser. |
| ☝️ **Single Finger** | **AI Assistant** | Activates "Listening Mode" for voice commands. |
| 👌 **OK Sign** | **Documentation** | Triggers a search for STARK project documentation. |

---

## 💬 Natural Language Customization

STARK is highly flexible. You can manage contacts and customize your assistant directly through the chat:

- **Contacts:** `"add contact 'John Doe' +91 99999 99999"` | `"show contacts"`
- **Workflows:** `"set gesture 'Open Palm' to open vscode and play coding music"`
- **Resets:** `"reset gesture 'Open Palm'"`

---

## 🛠 Installation & Setup

### 1. Requirements
Ensure you have **Python 3.8+** installed. For screen reading (OCR), [install Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) and ensure `tesseract` is in your PATH.

### 2. Install Dependencies
```powershell
python -m venv stark_venv
.\stark_venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Launch
```powershell
# Standard GUI Mode
python stark_launcher.py

# Optional CLI Mode
python stark_launcher.py --cli
```

> [!NOTE]
> On the first run, STARK will prompt you for your **Groq API Key**. This is saved securely to your local configuration.

---

## 📂 Project Structure

| File/Directory | Purpose |
| :--- | :--- |
| `stark.py` | Core assistant brain and reasoning engine. |
| `stark_gui.py` | Tkinter-based interface and gesture loop. |
| `stark_launcher.py` | Main entry point for the application. |
| `core/app_scanner.py` | Advanced Windows application discovery. |
| `core/automation_ops.py`| Desktop action execution (GhostController). |
| `core/media_play.py` | Spotify, YouTube, and Netflix automation. |
| `core/whatsapp_message.py`| WhatsApp Desktop messaging and contacts. |
| `core/reasoning.py` | AI workflow parsing and persistence. |
| `core/user_settings.py` | Handles `%APPDATA%\STARK` data paths. |
| `core/workflow_engine.py` | Executes multi-step gesture sequences. |
| `vision/gesture_detector.py`| MediaPipe-powered gesture recognition. |

---

## 🔐 User Data & Privacy
STARK stores all persistent data (settings, workflows, contacts) locally in:
`%APPDATA%\STARK\`

This ensures your configurations are preserved between updates and remain private on your machine.
