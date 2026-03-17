# STARK

STARK is a Windows-focused desktop assistant that combines:
- chat-based automation
- gesture-triggered workflows
- voice input/output
- screen OCR
- AI planning via Groq

## Features

### App automation
- Finds installed Windows apps through multiple discovery methods
- Launches apps, opens URLs, runs terminal commands, types text, presses keys, and controls media

### Media playback
- YouTube opens the first matching video directly
- Spotify opens the desktop app, searches for the requested track, and starts playback

### Gesture workflows
- `Open Palm`: coding workspace
- `Peace Sign`: research mode
- `Rock Sign`: entertainment mode
- `Fist`: focus mode
- `Pointing`: browser
- `Single Finger`: listening mode
- `OK Sign`: documentation search

These workflows are customizable directly from chat.

### Chat-based customization
Examples:
- `add contact "John Doe" +91 99999 99999`
- `show contacts`
- `remove contact "Dad"`
- `show gestures`
- `set gesture "Open Palm" to open vscode and play coding music`
- `bind gesture "Rock Sign" to entertainment mode`
- `reset gesture "Open Palm"`

### API key onboarding
- On first run, STARK prompts for the Groq API key
- The key is saved automatically
- Users do not need to edit `.env` for normal use

## User Data

STARK stores user-editable files in:

`%APPDATA%\STARK\`

That folder contains:
- `settings.json`
- `contacts.json`
- `workflows.json`
- `stark_config.yaml`

Bundled defaults are copied there automatically on first run.

## Run

### Install
```powershell
python -m venv stark_venv
.\stark_venv\Scripts\pip install -r requirements.txt
```

### Launch
```powershell
python stark_launcher.py
```

### Optional CLI mode
```powershell
python stark_launcher.py --cli
```

## OCR

For `read screen`, install Tesseract OCR on Windows and ensure `tesseract --version` works in a terminal.

## Important Files

| File | Purpose |
|---|---|
| `stark.py` | Core assistant logic |
| `stark_gui.py` | Tkinter GUI and gesture loop |
| `stark_launcher.py` | Main entry point |
| `core/app_scanner.py` | Windows app discovery |
| `core/automation_ops.py` | Desktop action execution |
| `core/media_play.py` | Spotify/YouTube/Netflix actions |
| `core/whatsapp_message.py` | WhatsApp desktop messaging + contacts |
| `core/reasoning.py` | Workflow/contact parsing and persistence |
| `core/user_settings.py` | `%APPDATA%\STARK` settings and data paths |
| `core/workflow_engine.py` | Workflow execution + cooldown logging |
| `vision/gesture_detector.py` | Gesture recognition |

## Windows Build

STARK now includes Windows packaging scaffolding.

### Build requirements
```powershell
.\stark_venv\Scripts\pip install -r requirements_build.txt
```

### Build the app
```powershell
.\build_windows.ps1
```

Output:

`.\dist\STARK\`

### Notes
- The build is configured for Windows `onedir` packaging
- User data stays in `%APPDATA%\STARK`, so updating the app does not wipe contacts/workflows/settings
- Tesseract is still an external Windows dependency for OCR

## Typical Setup For End Users

1. Launch `STARK.exe`
2. Enter the Groq API key once
3. Use the chatbot to manage contacts and gestures
4. Use gestures, chat, voice, and screen automation normally
