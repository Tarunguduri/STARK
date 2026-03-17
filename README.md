# STARK: Hybrid AI Desktop Assistant

STARK is a Windows-focused desktop assistant that combines LLM reasoning with OS automation, computer vision, and voice interaction. It is designed to help with coding workspaces, media control, messaging, and desktop workflows through natural language and gestures.

---

## Key Features

### Smart App Automation
- Multi-discovery engine for Windows apps through Registry, Shell, Start Menu, and WindowsApps.
- Launches apps, opens URLs, runs terminal commands, types text, and presses hotkeys.

### Seamless Media Playback
- YouTube opens the first matching video directly in the browser.
- Spotify launches the desktop app, searches for the requested track, and starts playback.

### Gesture-Triggered Workflows

| Gesture | Mode | Workflow Description |
| :--- | :--- | :--- |
| Open Palm | Coding Workspace | Opens VS Code, creates a project folder, opens terminal, and plays lofi. |
| Peace Sign | Research Mode | Opens Brave browser, searches AI news, and opens arXiv. |
| Rock Sign | Entertainment | Opens a YouTube playlist and sets volume to 70%. |
| Fist | Focus Mode | Mutes system audio and closes distractions. |
| Pointing | Quick Browser | Launches the Brave browser. |
| Single Finger | AI Assistant | Activates listening mode for voice commands. |
| OK Sign | Documentation | Triggers a search for STARK project documentation. |

---

## Natural Language Customization

STARK can be customized directly from chat:

- Contacts: `add contact "John Doe" +91 99999 99999`
- Show contacts: `show contacts`
- Workflows: `set gesture "Open Palm" to open vscode and play coding music`
- Resets: `reset gesture "Open Palm"`

---

## Installation And Setup

### 1. Requirements
Install Python 3.8+.

For screen reading, install Tesseract OCR on Windows and ensure `tesseract` is available in `PATH`.

### 2. Install Dependencies
```powershell
python -m venv stark_venv
.\stark_venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Launch
```powershell
python stark_launcher.py
```

Optional CLI mode:

```powershell
python stark_launcher.py --cli
```

On first run, STARK prompts for the Groq API key and stores it in local user settings.

---

## Project Structure

| File/Directory | Purpose |
| :--- | :--- |
| `stark.py` | Core assistant logic and reasoning entry point |
| `stark_gui.py` | Tkinter UI and gesture loop |
| `stark_launcher.py` | Main application launcher |
| `core/app_scanner.py` | Windows application discovery |
| `core/automation_ops.py` | Desktop action execution |
| `core/media_play.py` | Spotify, YouTube, and Netflix automation |
| `core/whatsapp_message.py` | WhatsApp desktop messaging and contacts |
| `core/reasoning.py` | Workflow and contact parsing plus persistence |
| `core/user_settings.py` | `%APPDATA%\\STARK` data paths |
| `core/workflow_engine.py` | Workflow execution and logging |
| `vision/gesture_detector.py` | MediaPipe-based gesture recognition |

---

## User Data And Privacy

STARK stores persistent data locally in:

`%APPDATA%\STARK\`

This keeps settings, workflows, and contacts private to the user machine and preserved across updates.

---

## Website Download Page

This repo includes a static download website in `docs/`.

- Website entry: `docs/index.html`
- Styles: `docs/styles.css`
- Download link target: `https://github.com/Tarunguduri/STARK/releases/latest/download/STARK_Windows.zip`

### Publish With GitHub Pages

1. Push the repo to GitHub.
2. Open the repository on GitHub.
3. Go to `Settings -> Pages`.
4. Under `Build and deployment`, choose `Deploy from a branch`.
5. Select branch `main` and folder `/docs`.
6. Save.

The site will be hosted at:

`https://tarunguduri.github.io/STARK/`

### Build The Downloadable ZIP

Run:

```powershell
.\build_windows.ps1 -Clean
```

That script creates a stable shareable file at:

`release\STARK_Windows.zip`
