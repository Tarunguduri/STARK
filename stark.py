import json
import logging
import os
import sys
import time
import traceback
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import signal
import datetime
import subprocess
import webbrowser
import psutil
import threading
from pathlib import Path
import shutil
import random
import sqlite3
import yaml
from urllib.parse import quote_plus
import re
import winreg  # For Windows app registry search
import hashlib
import fnmatch
from core.ai_reasoning_engine import AIReasoningEngine
from core.automation_ops import execute_automation_action
from core.ghost_controller import GhostController
from core.reasoning import parse_local_instruction
from core.user_settings import (
    clear_api_key,
    ensure_api_key,
    get_runtime_config_path,
    get_saved_api_key,
    get_settings_path,
    load_api_key_into_env,
)
from core.workflow_engine import WorkflowEngine
from core.app_scanner import AppScanner, launch_app as _scanner_launch
from core.media_plugin import play_media as _plugin_play_media
from core.voice_engine import VoiceEngine as _VoiceEngine
from core.whatsapp_message import parse_message_command

# Ensure Windows terminals can print Unicode status text without crashing.
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Optional dependencies with graceful fallbacks
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# NEW: Screen capture and OCR dependencies
try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False
    logger = logging.getLogger(__name__) if 'logger' in dir() else logging.getLogger(__name__)
    if hasattr(logger, 'warning'):
        pass  # Will log after logger is configured

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from PIL import Image
    import numpy as np
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import imagehash
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False

try:
    import pyautogui as _pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

# Configure comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('stark.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Log warnings for missing screen capture dependencies
if not MSS_AVAILABLE:
    logger.warning("mss not available - screen capture disabled")
if not EASYOCR_AVAILABLE:
    logger.warning("easyocr not available")
if not PIL_AVAILABLE:
    logger.warning("PIL not available")


@dataclass
class STARKConfig:
    """Comprehensive configuration for STARK system"""
    # Reasoning Configuration (API-based)
    groq_model: str = "llama-3.1-8b-instant"
    
    # Network & Retry Configuration
    max_retries: int = 3
    timeout: int = 10
    retry_delay: float = 1.0
    
    # Execution Configuration
    max_concurrent_actions: int = 5 
    action_timeout: int = 60
    
    # System Configuration
    debug_mode: bool = False
    voice_enabled: bool = False
    auto_save_conversations: bool = True
    
    # Privacy & Security
    data_retention_days: int = 30
    encrypt_logs: bool = False
    
    # Plugin Configuration
    plugin_directories: List[str] = field(default_factory=lambda: ["plugins"])
    disabled_plugins: List[str] = field(default_factory=list)
    
    # UI Configuration
    interface_mode: str = "cli"  # cli, gui, voice, web
    theme: str = "dark"
    
    # NEW: Resource Management
    cpu_threshold_percent: int = 80
    ram_threshold_percent: int = 85
    adaptive_batch_sizing: bool = True
    
    # NEW: File Operations
    file_index_enabled: bool = True
    auto_index_on_startup: bool = True
    index_locations: List[str] = field(default_factory=lambda: [os.path.expanduser("~")])
    exclude_paths: List[str] = field(default_factory=lambda: [
        "*\\Windows\\*", "*\\Program Files\\*", "*\\node_modules\\*", "*\\.git\\*"
    ])
    protected_paths: List[str] = field(default_factory=lambda: [
        "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)"
    ] if sys.platform == "win32" else ["/bin", "/sbin", "/usr/bin", "/usr/sbin", "/System"])
    backup_location: str = field(default_factory=lambda: 
        "C:\\STARK_Backups" if sys.platform == "win32" else os.path.expanduser("~/STARK_Backups"))
    delete_confirmation_threshold: int = 10
    move_confirmation_threshold: int = 50
    
    # NEW: Screen Intelligence
    screen_enabled: bool = True
    ocr_engine: str = "easyocr"  # or "tesseract"
    use_gpu: bool = False
    screen_capture_interval: int = 5
    
    @classmethod
    def load_from_file(cls, config_path: str = "stark_config.yaml") -> 'STARKConfig':
        """Load configuration from YAML file"""
        if config_path == "stark_config.yaml":
            config_path = str(get_runtime_config_path())
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f)
                return cls(**config_data)
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")
        return cls()
    
    def save_to_file(self, config_path: str = "stark_config.yaml"):
        """Save configuration to YAML file"""
        try:
            if config_path == "stark_config.yaml":
                config_path = str(get_runtime_config_path())
            config_dict = {
                key: getattr(self, key) 
                for key in self.__dataclass_fields__.keys()
            }
            Path(config_path).parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            logger.info(f"Configuration saved to {config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")


class ConversationManager:
    """Manages conversation history and context"""
    
    def __init__(self, db_path: str = "stark_conversations.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database for conversation storage"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        user_input TEXT NOT NULL,
                        stark_response TEXT NOT NULL,
                        actions_executed TEXT,
                        session_id TEXT,
                        metadata TEXT
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize conversation database: {e}")
    
    def save_conversation(self, user_input: str, stark_response: str, 
                         actions: List[Dict] = None, session_id: str = None,
                         metadata: Dict = None):
        """Save conversation to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO conversations 
                    (user_input, stark_response, actions_executed, session_id, metadata)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    user_input,
                    stark_response,
                    json.dumps(actions) if actions else None,
                    session_id or "default",
                    json.dumps(metadata) if metadata else None
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save conversation: {e}")
    
    def get_recent_conversations(self, limit: int = 10, session_id: str = None) -> List[Dict]:
        """Get recent conversations for context"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if session_id:
                    cursor = conn.execute("""
                        SELECT * FROM conversations 
                        WHERE session_id = ? 
                        ORDER BY timestamp DESC LIMIT ?
                    """, (session_id, limit))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM conversations 
                        ORDER BY timestamp DESC LIMIT ?
                    """, (limit,))
                
                return [dict(zip([col[0] for col in cursor.description], row)) 
                       for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to retrieve conversations: {e}")
            return []


# NEW: FileIndexer Class for ultra-fast file searching
class FileIndexer:
    """SQLite-based file indexer for ultra-fast searching"""
    
    def __init__(self, db_path: str = "stark_file_index.db"):
        self.db_path = db_path
        self.indexing = False
        self.init_database()
    
    def init_database(self):
        """Initialize the file index database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    path TEXT UNIQUE NOT NULL,
                    extension TEXT,
                    size_bytes INTEGER,
                    modified_timestamp REAL,
                    created_timestamp REAL,
                    indexed_at REAL
                )
            """)
            
            # Create indexes for fast searching
            conn.execute("CREATE INDEX IF NOT EXISTS idx_filename ON files(filename)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_extension ON files(extension)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_modified ON files(modified_timestamp)")
            conn.commit()
        
        logger.info(f"File index database initialized: {self.db_path}")
    
    def build_index(self, locations: List[str], exclude_patterns: List[str]):
        """Build file index from specified locations"""
        if self.indexing:
            logger.warning("Indexing already in progress")
            return
        
        self.indexing = True
        indexed_count = 0
        start_time = time.time()
        
        logger.info(f"Starting file indexing for: {locations}")
        
        try:
            for location in locations:
                if not os.path.exists(location):
                    continue
                
                for root, dirs, files in os.walk(location):
                    # Skip excluded directories
                    if any(fnmatch.fnmatch(root, pattern) for pattern in exclude_patterns):
                        dirs[:] = []
                        continue
                    
                    # Filter system directories
                    dirs[:] = [d for d in dirs if not d.startswith('.') and 
                              d.lower() not in ['node_modules', '__pycache__', 'venv', '.git']]
                    
                    for filename in files:
                        file_path = os.path.join(root, filename)
                        try:
                            stat = os.stat(file_path)
                            extension = os.path.splitext(filename)[1].lower()
                            
                            with sqlite3.connect(self.db_path) as conn:
                                conn.execute("""
                                    INSERT OR REPLACE INTO files 
                                    (filename, path, extension, size_bytes, modified_timestamp, 
                                     created_timestamp, indexed_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    filename, file_path, extension, stat.st_size,
                                    stat.st_mtime, stat.st_ctime, time.time()
                                ))
                            
                            indexed_count += 1
                            if indexed_count % 1000 == 0:
                                logger.info(f"Indexed {indexed_count} files...")
                        except:
                            continue
        finally:
            self.indexing = False
            elapsed = time.time() - start_time
            logger.info(f"Indexing complete: {indexed_count} files in {elapsed:.2f}s")
    
    def search(self, pattern: str, location: str = None) -> List[Dict]:
        """Search for files matching pattern"""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM files WHERE filename LIKE ?"
            params = [f"%{pattern}%"]
            
            if location:
                query += " AND path LIKE ?"
                params.append(f"{location}%")
            
            query += " ORDER BY modified_timestamp DESC LIMIT 1000"
            
            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            
            results = []
            for row in cursor.fetchall():
                file_dict = dict(zip(columns, row))
                if os.path.exists(file_dict['path']):
                    results.append(file_dict)
            
            return results
    
    def get_files_by_age(self, days_old: int, location: str = None) -> List[Dict]:
        """Get files older than specified days"""
        cutoff_time = time.time() - (days_old * 86400)
        
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM files WHERE modified_timestamp < ?"
            params = [cutoff_time]
            
            if location:
                query += " AND path LIKE ?"
                params.append(f"{location}%")
            
            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


# NEW: ScreenIntelligence Class for OCR and screen reading
class ScreenIntelligence:
    """Screen reading and analysis with OCR"""
    
    def __init__(self, config: STARKConfig):
        self.config = config
        self.enabled = config.screen_enabled
        self.ocr_engine = None
        self.sct = None
        
        if self.enabled:
            self._init_ocr()
            if MSS_AVAILABLE:
                self.sct = mss.mss()
    
    def _init_ocr(self):
        """Initialize OCR engine"""
        def _enable_tesseract_if_available() -> bool:
            if not TESSERACT_AVAILABLE:
                return False
            try:
                # Validate that the native tesseract executable is available.
                pytesseract.get_tesseract_version()
                self.config.ocr_engine = 'tesseract'
                self.ocr_engine = 'tesseract'
                logger.info("Tesseract OCR selected")
                return True
            except Exception as e:
                # Try common Windows install path when PATH is not refreshed yet.
                common_tesseract = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
                if common_tesseract.exists():
                    try:
                        pytesseract.pytesseract.tesseract_cmd = str(common_tesseract)
                        pytesseract.get_tesseract_version()
                        self.config.ocr_engine = 'tesseract'
                        self.ocr_engine = 'tesseract'
                        logger.info("Tesseract OCR selected via default install path")
                        return True
                    except Exception as inner_e:
                        logger.warning(f"Tesseract OCR unavailable: {inner_e}")
                        return False
                logger.warning(f"Tesseract OCR unavailable: {e}")
                return False

        if self.config.ocr_engine == 'easyocr' and EASYOCR_AVAILABLE:
            try:
                self.ocr_engine = easyocr.Reader(['en'], gpu=self.config.use_gpu, verbose=False)
                logger.info("EasyOCR initialized")
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
                # Fallback to tesseract when easyocr initialization fails
                if _enable_tesseract_if_available():
                    logger.info("Falling back to Tesseract OCR")
        elif self.config.ocr_engine == 'tesseract' and TESSERACT_AVAILABLE:
            if not _enable_tesseract_if_available():
                self.enabled = False
        else:
            # Auto-fallback when preferred engine is unavailable
            if _enable_tesseract_if_available():
                logger.info("EasyOCR unavailable; using Tesseract OCR fallback")
            else:
                self.enabled = False
    
    def capture_screen(self, region: Optional[Dict] = None, monitor: int = 1):
        """Capture screen or region"""
        if not MSS_AVAILABLE:
            return None
        
        try:
            # mss uses thread-local state; instantiate per call to avoid
            # cross-thread errors in GUI worker threads.
            with mss.mss() as sct:
                if region:
                    capture_region = region
                else:
                    capture_region = sct.monitors[monitor]
                
                screenshot = sct.grab(capture_region)
                img = np.array(screenshot)
                return img
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            return None
    
    def read_screen(self, region: Optional[Dict] = None) -> Optional[Dict]:
        """Read text from screen using OCR"""
        if not self.enabled or not self.ocr_engine:
            return {"success": False, "message": "OCR not available", "text": ""}
        
        start_time = time.time()
        capture = self.capture_screen(region)
        
        if capture is None:
            return {"success": False, "message": "Screen capture failed", "text": ""}
        
        try:
            if self.config.ocr_engine == 'easyocr':
                results = self.ocr_engine.readtext(capture)
                text_lines = []
                confidence_sum = 0
                for result in results:
                    if len(result) >= 2:
                        text_lines.append(result[1])
                        if len(result) >= 3:
                            confidence_sum += result[2]
                
                full_text = ' '.join(text_lines)
                confidence = (confidence_sum / len(results)) if results and len(results) > 0 else 0
            elif self.config.ocr_engine == 'tesseract':
                img_pil = Image.fromarray(capture)
                full_text = pytesseract.image_to_string(img_pil)
                confidence = 0.8
            else:
                return {"success": False, "message": "OCR engine not configured", "text": ""}
            
            execution_time = time.time() - start_time
            
            return {
                "success": True,
                "text": full_text,
                "confidence": confidence,
                "execution_time": execution_time,
                "word_count": len(full_text.split())
            }
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return {"success": False, "message": f"OCR error: {str(e)}", "text": ""}
    
    def find_text_on_screen(self, search_text: str) -> Dict:
        """Search for specific text on screen"""
        result = self.read_screen()
        
        if not result['success']:
            return {"found": False, "message": result['message']}
        
        found = search_text.lower() in result['text'].lower()
        
        return {
            "found": found,
            "search_text": search_text,
            "full_text": result['text'],
            "confidence": result.get('confidence', 0)
        }


# NEW: IntentRouter Class for Tier 1 pattern matching (no LLM)
class IntentRouter:
    """Fast pattern-based intent classification - Tier 1 (No LLM)"""
    
    def __init__(self, config: STARKConfig):
        self.config = config
        self.patterns = self._define_patterns()
    
    def _define_patterns(self) -> Dict:
        """Define patterns for direct action routing"""
        return {
            'play_spotify': {
                'patterns': [
                    r'(?:play|listen\s+to|search\s+for|find)\s+(.+?)\s+(?:on\s+)?spotify\b',
                    r'^spotify\s+(?:play|search\s+for|search|find)?\s*(.+)$',
                ],
                'action': 'play_media'
            },
            'play_youtube': {
                'patterns': [
                    r'(?:play|watch|search|find)\s+(.+?)\s+(?:on\s+)?youtube\b',
                    r'^youtube\s+(?:play|watch|search\s+for|search|find)?\s*(.+)$',
                ],
                'action': 'play_media'
            },
            'play_netflix': {
                'patterns': [
                    r'(?:play|watch|search|find)\s+(.+?)\s+(?:on\s+)?netflix\b',
                    r'^netflix\s+(?:play|watch|search\s+for|search|find)?\s*(.+)$',
                ],
                'action': 'play_media'
            },
            'send_whatsapp_message': {
                'patterns': [
                    r'^(?:message|text|send whatsapp(?: message)? to)\s+([a-z0-9_+()-]+)\s+(.+)$',
                ],
                'action': 'send_whatsapp_message'
            },
            'file_search': {
                'patterns': [
                    r'find (?:all )?files? (?:named|with|called|containing) ["\']?(\w+)["\']?',
                    r'search for files? (?:named|with) ["\']?(\w+)["\']?',
                ],
                'action': 'file_search'
            },
            'file_organize': {
                'patterns': [
                    r'(?:move|organize|sort) (?:all )?files? (?:with|named) ["\']?(\w+)["\']? (?:to|into) (.+)',
                ],
                'action': 'file_organize'
            },
            'file_cleanup': {
                'patterns': [
                    r'delete (?:old|unused) (?:files?|screenshots?)',
                    r'remove files? older than (\d+) days?',
                ],
                'action': 'file_cleanup'
            },
            'screen_read': {
                'patterns': [
                    r'read (?:my |the )?screen',
                    r'what(?:\'s| is) on (?:my |the )?screen',
                ],
                'action': 'screen_read'
            },
            'system_status': {
                'patterns': [
                    r'(?:show|check) system (?:status|info)',
                    r'system status',
                ],
                'action': 'system_status'
            },
            'launch_app': {
                'patterns': [
                    # Match only pure app-launch commands so mixed commands
                    # (e.g. "open spotify and play ...") are routed to LLM.
                    r'^(?:open|launch|start)\s+([a-z0-9 ._+-]+)$',
                ],
                'action': 'launch_app'
            },
            'get_time': {
                'patterns': [
                    r'what time is it',
                    r'(?:show|tell) (?:me )?(?:the )?time',
                ],
                'action': 'get_time'
            },
        }
    
    def route(self, user_input: str) -> Optional[Tuple[str, Dict]]:
        """
        Route user input to direct action if pattern matches
        Returns: (action_name, params) or None if no match (needs LLM)
        """
        user_input_lower = user_input.lower().strip()

        whatsapp_params = parse_message_command(user_input)
        if whatsapp_params:
            logger.info("Direct route: send_whatsapp_message (Tier 1 - no LLM)")
            return ("send_whatsapp_message", whatsapp_params)

        # Cherry-picked from stark0 intent style: handle mixed commands like
        # "open spotify and play aari aari".
        mixed_media = re.search(
            r'^(?:open|launch|start)\s+(spotify|youtube|netflix)\s+(?:and|then)\s+'
            r'(?:play|watch|search\s+for|find)\s+(.+)$',
            user_input_lower
        )
        if mixed_media:
            platform = mixed_media.group(1).strip()
            query = mixed_media.group(2).strip()
            logger.info("Direct route: play_media (mixed command)")
            return ("play_media", {"platform": platform, "query": query})

        local_result = parse_local_instruction(user_input)
        if local_result:
            if local_result.get("task") == "update_workflow":
                logger.info("Direct route: update_workflow (local parser)")
                return (
                    "update_workflow",
                    {
                        "gesture": local_result.get("gesture", ""),
                        "actions": local_result.get("actions", []),
                    },
                )
            if local_result.get("task") == "bind_workflow":
                logger.info("Direct route: bind_workflow (local parser)")
                return (
                    "bind_workflow",
                    {
                        "gesture": local_result.get("gesture", ""),
                        "workflow": local_result.get("workflow", ""),
                    },
                )
            actions = local_result.get("actions", [])
            if len(actions) == 1:
                action = actions[0].get("action", "")
                if action in {
                    "send_whatsapp_message",
                    "add_contact",
                    "update_contact",
                    "remove_contact",
                    "list_contacts",
                    "list_workflows",
                    "reset_workflow",
                }:
                    logger.info("Direct route: %s (local parser)", action)
                    return (action, actions[0].get("params", {}))
        
        for intent_name, intent_data in self.patterns.items():
            for pattern in intent_data['patterns']:
                match = re.search(pattern, user_input_lower)
                if match:
                    params = self._extract_params(intent_name, match, user_input)
                    action = intent_data['action']
                    logger.info(f"Direct route: {action} (Tier 1 - no LLM)")
                    return (action, params)
        
        logger.info("No pattern match - routing to LLM (Tier 2)")
        return None
    
    def _extract_params(self, intent: str, match: re.Match, original_input: str) -> Dict:
        """Extract parameters from regex match"""
        params = {}
        
        if intent == 'file_search' and match.groups():
            params['pattern'] = match.group(1)
        
        elif intent == 'file_organize':
            if len(match.groups()) >= 1:
                params['pattern'] = match.group(1)
            if len(match.groups()) >= 2:
                params['destination'] = match.group(2).strip()
        
        elif intent == 'file_cleanup':
            age_match = re.search(r'(\d+)\s+days?', original_input.lower())
            params['days_old'] = int(age_match.group(1)) if age_match else 30
            params['file_type'] = 'screenshots' if 'screenshot' in original_input.lower() else 'all'
        
        elif intent == 'launch_app' and match.groups():
            params['app_name'] = match.group(1).strip()

        elif intent == 'play_spotify' and match.groups():
            params['platform'] = 'spotify'
            params['query'] = match.group(1).strip()

        elif intent == 'play_youtube' and match.groups():
            params['platform'] = 'youtube'
            params['query'] = match.group(1).strip()

        elif intent == 'play_netflix' and match.groups():
            params['platform'] = 'netflix'
            params['query'] = match.group(1).strip()

        elif intent == 'send_whatsapp_message' and len(match.groups()) >= 2:
            params['contact'] = match.group(1).strip()
            params['message'] = original_input[match.start(2):].strip()
        
        return params


class AdvancedPlugins:
    """Advanced plugin implementations for STARK"""
    
    @staticmethod
    def voice_control(action: str, params: dict) -> dict:
        """Voice control and speech synthesis plugin"""
        try:
            if action == "speak":
                text = params.get("text", "")
                if not text:
                    return {"success": False, "message": "Text to speak is required"}
                
                if TTS_AVAILABLE:
                    try:
                        engine = pyttsx3.init()
                        engine.say(text)
                        engine.runAndWait()
                        return {"success": True, "message": f"Spoken: {text[:50]}..."}
                    except Exception as e:
                        return {"success": False, "message": f"TTS error: {str(e)}"}
                else:
                    return {"success": False, "message": "Text-to-speech not available (install pyttsx3)"}
            
            elif action == "listen":
                if SPEECH_RECOGNITION_AVAILABLE:
                    try:
                        r = sr.Recognizer()
                        with sr.Microphone() as source:
                            print("Listening...")
                            audio = r.listen(source, timeout=5)
                        
                        text = r.recognize_google(audio)
                        return {"success": True, "message": f"Heard: {text}", "recognized_text": text}
                    except sr.UnknownValueError:
                        return {"success": False, "message": "Could not understand audio"}
                    except sr.RequestError as e:
                        return {"success": False, "message": f"Speech recognition error: {e}"}
                    except Exception as e:
                        return {"success": False, "message": f"Listening error: {str(e)}"}
                else:
                    return {"success": False, "message": "Speech recognition not available"}
            
            else:
                return {"success": False, "message": f"Unknown voice action: {action}"}
                
        except Exception as e:
            return {"success": False, "message": f"Voice control error: {str(e)}"}
    
    @staticmethod
    def smart_automation(action: str, params: dict) -> dict:
        """Smart automation and workflow plugin"""
        try:
            if action == "create_smart_workflow":
                workflow_name = params.get("workflow_name", "")
                description = params.get("description", "")
                trigger = params.get("trigger", "manual")  # manual, time, event
                actions = params.get("actions", [])
                
                if not workflow_name:
                    return {"success": False, "message": "Workflow name is required"}
                
                workflow = {
                    "name": workflow_name,
                    "description": description,
                    "trigger": trigger,
                    "actions": actions,
                    "created": datetime.datetime.now().isoformat(),
                    "version": "1.0"
                }
                
                workflow_dir = Path("workflows")
                workflow_dir.mkdir(exist_ok=True)
                
                workflow_file = workflow_dir / f"{workflow_name.replace(' ', '_')}.json"
                with open(workflow_file, 'w', encoding='utf-8') as f:
                    json.dump(workflow, f, indent=2)
                
                return {"success": True, "message": f"Smart workflow '{workflow_name}' created"}
            
            elif action == "schedule_task":
                task_name = params.get("task_name", "")
                schedule_time = params.get("schedule_time", "")
                task_action = params.get("task_action", "")
                
                if not all([task_name, schedule_time, task_action]):
                    return {"success": False, "message": "Task name, schedule time, and action are required"}
                
                # This would integrate with system scheduler (cron/task scheduler)
                # For now, creating a simple reminder
                def scheduled_task():
                    print(f"🔔 Scheduled Task: {task_name} - {task_action}")
                    logger.info(f"Executed scheduled task: {task_name}")
                
                # Parse schedule time and set up timer (simplified)
                try:
                    delay = int(schedule_time) * 60  # Assuming minutes for now
                    timer = threading.Timer(delay, scheduled_task)
                    timer.daemon = True
                    timer.start()
                    
                    return {"success": True, "message": f"Task '{task_name}' scheduled for {schedule_time} minutes"}
                except ValueError:
                    return {"success": False, "message": "Invalid schedule time format"}
            
            else:
                return {"success": False, "message": f"Unknown automation action: {action}"}
                
        except Exception as e:
            return {"success": False, "message": f"Smart automation error: {str(e)}"}
    
    @staticmethod
    def content_generation(action: str, params: dict) -> dict:
        """Advanced content generation plugin"""
        try:
            if action == "generate_code":
                language = params.get("language", "python")
                description = params.get("description", "")
                complexity = params.get("complexity", "simple")
                
                if not description:
                    return {"success": False, "message": "Code description is required"}
                
                # Template-based code generation (would be enhanced with LLM)
                code_templates = {
                    "python": {
                        "simple": f'''# {description}
def main():
    """
    {description}
    """
    print("Generated code for: {description}")
    # TODO: Implement your logic here
    pass

if __name__ == "__main__":
    main()
''',
                        "advanced": f'''"""
{description}
Advanced implementation with error handling and logging
"""
import logging
import sys
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class {description.replace(' ', '').title()}:
    def __init__(self):
        self.initialized = True
        logger.info("Initialized {description}")
    
    def execute(self) -> bool:
        try:
            # TODO: Implement main logic here
            logger.info("Executing {description}")
            return True
        except Exception as e:
            logger.error(f"Error in {description}: {{e}}")
            return False

def main():
    processor = {description.replace(' ', '').title()}()
    success = processor.execute()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
'''
                    }
                }
                
                template = code_templates.get(language, {}).get(complexity, "# Code generation not available for this combination")
                
                # Save to file
                filename = f"{description.replace(' ', '_').lower()}.{language}"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(template)
                
                return {"success": True, "message": f"Generated {language} code in {filename}"}
            
            elif action == "generate_document":
                doc_type = params.get("doc_type", "report")
                topic = params.get("topic", "")
                length = params.get("length", "medium")
                
                if not topic:
                    return {"success": False, "message": "Document topic is required"}
                
                # Enhanced document templates
                document_content = AdvancedPlugins._generate_document_content(doc_type, topic, length)
                
                filename = f"{topic.replace(' ', '_')}_{doc_type}.txt"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(document_content)
                
                return {"success": True, "message": f"Generated {doc_type} document: {filename}"}
            
            else:
                return {"success": False, "message": f"Unknown content generation action: {action}"}
                
        except Exception as e:
            return {"success": False, "message": f"Content generation error: {str(e)}"}
    
    @staticmethod
    def _generate_document_content(doc_type: str, topic: str, length: str) -> str:
        """Generate structured document content"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if doc_type == "report":
            return f"""COMPREHENSIVE REPORT: {topic.upper()}
Generated by STARK AI Assistant
Date: {timestamp}

EXECUTIVE SUMMARY
================
This report provides a detailed analysis of {topic}, exploring key aspects, current trends, and future implications.

INTRODUCTION
============
{topic} represents a significant area of interest that requires thorough examination and understanding.

KEY FINDINGS
============
1. Primary Analysis
   - Current state assessment of {topic}
   - Market trends and patterns
   - Stakeholder perspectives

2. Critical Factors
   - Technical considerations
   - Economic implications
   - Social impact

3. Challenges and Opportunities
   - Existing barriers
   - Potential solutions
   - Growth opportunities

DETAILED ANALYSIS
================
The comprehensive analysis of {topic} reveals several important insights:

• Strategic Importance: {topic} plays a crucial role in current market dynamics
• Innovation Potential: Emerging technologies are reshaping the landscape
• Implementation Challenges: Various obstacles need to be addressed

METHODOLOGY
===========
This analysis employed a systematic approach combining:
- Literature review and research
- Data analysis and interpretation
- Expert consultation and validation

RECOMMENDATIONS
===============
Based on our findings, we recommend:

1. Immediate Actions
   - Implement core strategies
   - Establish monitoring systems
   - Build stakeholder engagement

2. Medium-term Goals
   - Develop comprehensive frameworks
   - Enhance capabilities and resources
   - Monitor progress and adjust approaches

3. Long-term Vision
   - Achieve strategic objectives
   - Maintain competitive advantage
   - Drive innovation and growth

CONCLUSION
==========
{topic} presents both significant opportunities and challenges. Success requires strategic planning, careful implementation, and continuous adaptation to changing conditions.

NEXT STEPS
==========
- Detailed planning and resource allocation
- Implementation timeline development
- Progress monitoring and evaluation

---
Report generated by STARK AI Assistant
For more information, contact your STARK administrator.
"""
        
        elif doc_type == "guide":
            return f"""COMPLETE GUIDE: {topic.upper()}
Generated by STARK AI Assistant
Date: {timestamp}

TABLE OF CONTENTS
=================
1. Introduction
2. Getting Started
3. Step-by-Step Instructions
4. Best Practices
5. Troubleshooting
6. Advanced Techniques
7. Resources and References

INTRODUCTION
============
Welcome to the comprehensive guide on {topic}. This document provides everything you need to know to get started and become proficient.

GETTING STARTED
===============
Prerequisites:
- Basic understanding of related concepts
- Access to necessary tools and resources
- Willingness to learn and practice

Initial Setup:
1. Prepare your environment
2. Gather required materials
3. Set up your workspace
4. Review safety considerations

STEP-BY-STEP INSTRUCTIONS
=========================

Phase 1: Foundation
-------------------
Step 1: Understanding Basics
- Learn fundamental concepts
- Familiarize yourself with terminology
- Review key principles

Step 2: Initial Practice
- Start with simple exercises
- Build confidence gradually
- Document your progress

Phase 2: Skill Development
--------------------------
Step 3: Intermediate Techniques
- Apply learned concepts
- Practice more complex scenarios
- Seek feedback and guidance

Step 4: Advanced Applications
- Tackle challenging problems
- Develop your own approaches
- Share knowledge with others

BEST PRACTICES
==============
• Always follow established protocols
• Document your work and decisions
• Regular practice and continuous learning
• Stay updated with latest developments
• Build a network of knowledgeable peers

TROUBLESHOOTING
===============
Common Issues and Solutions:

Problem: Getting started difficulties
Solution: Review prerequisites and setup steps

Problem: Performance issues
Solution: Check configuration and optimize settings

Problem: Unexpected results
Solution: Verify inputs and methodology

ADVANCED TECHNIQUES
===================
For experienced practitioners:
- Custom optimization strategies
- Integration with other systems
- Automation and scaling approaches
- Performance monitoring and tuning

RESOURCES AND REFERENCES
========================
• Official documentation and guides
• Community forums and support groups
• Training courses and certifications
• Books and research papers
• Online tutorials and videos

---
Guide generated by STARK AI Assistant
Keep learning and exploring!
"""
        
        else:  # Default format
            return f"""{doc_type.upper()}: {topic.upper()}
Generated by STARK AI Assistant
Date: {timestamp}

Content about {topic} would be generated here based on the specific requirements and available information.

This is a template that can be customized based on your specific needs and preferences.

Key points to cover:
- Overview and introduction
- Main concepts and ideas
- Practical applications
- Examples and case studies
- Conclusions and recommendations

For more detailed content, please specify additional parameters or requirements.
"""
    
    @staticmethod
    def system_intelligence(action: str, params: dict) -> dict:
        """Intelligent system monitoring and optimization"""
        try:
            if action == "analyze_system_health":
                try:
                    # Comprehensive system analysis
                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    disk = psutil.disk_usage('/')
                    
                    # Process analysis
                    processes = list(psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']))
                    high_cpu_processes = [p for p in processes if p.info['cpu_percent'] and p.info['cpu_percent'] > 5]
                    high_memory_processes = sorted(processes, key=lambda x: x.info['memory_percent'] or 0, reverse=True)[:5]
                    
                    # Generate health report
                    health_report = f"""SYSTEM HEALTH ANALYSIS
======================
Timestamp: {datetime.datetime.now()}

CPU Status: {"⚠️ HIGH" if cpu_percent > 80 else "✅ Normal"} ({cpu_percent}%)
Memory Status: {"⚠️ HIGH" if memory.percent > 85 else "✅ Normal"} ({memory.percent}%)
Disk Status: {"⚠️ LOW SPACE" if disk.percent > 90 else "✅ Normal"} ({disk.percent}% used)

High CPU Processes:
{chr(10).join(f"- {p.info['name']} ({p.info['cpu_percent']}%)" for p in high_cpu_processes[:5])}

Top Memory Consumers:
{chr(10).join(f"- {p.info['name']} ({p.info['memory_percent']:.1f}%)" for p in high_memory_processes)}

Recommendations:
"""
                    
                    recommendations = []
                    if cpu_percent > 80:
                        recommendations.append("- Consider closing unnecessary applications")
                    if memory.percent > 85:
                        recommendations.append("- Free up memory by closing unused programs")
                    if disk.percent > 90:
                        recommendations.append("- Clean up disk space and remove temporary files")
                    
                    if not recommendations:
                        recommendations.append("- System is running optimally")
                    
                    health_report += "\n".join(recommendations)
                    
                    # Save report
                    report_file = f"system_health_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    with open(report_file, 'w', encoding='utf-8') as f:
                        f.write(health_report)
                    
                    return {"success": True, "message": f"System health analysis saved to {report_file}"}
                    
                except Exception as e:
                    return {"success": False, "message": f"System analysis error: {str(e)}"}
            
            elif action == "optimize_system":
                optimization_actions = []
                
                try:
                    # Clear temporary files
                    temp_dirs = [
                        os.path.expanduser("~/AppData/Local/Temp") if sys.platform == "win32" else "/tmp",
                        os.path.expanduser("~/.cache") if sys.platform != "win32" else None
                    ]
                    
                    for temp_dir in temp_dirs:
                        if temp_dir and os.path.exists(temp_dir):
                            try:
                                files_removed = 0
                                for root, dirs, files in os.walk(temp_dir):
                                    for file in files:
                                        try:
                                            os.remove(os.path.join(root, file))
                                            files_removed += 1
                                        except:
                                            continue
                                optimization_actions.append(f"Cleaned {files_removed} temporary files")
                            except:
                                optimization_actions.append("Partial cleanup of temporary files")
                    
                    # Memory optimization recommendations
                    memory = psutil.virtual_memory()
                    if memory.percent > 80:
                        optimization_actions.append("Recommendation: Restart applications with high memory usage")
                    
                    return {"success": True, "message": f"System optimization completed: {'; '.join(optimization_actions)}"}
                    
                except Exception as e:
                    return {"success": False, "message": f"System optimization error: {str(e)}"}
            
            else:
                return {"success": False, "message": f"Unknown system intelligence action: {action}"}
                
        except Exception as e:
            return {"success": False, "message": f"System intelligence error: {str(e)}"}


class BuiltInPlugins:
    """Built-in plugin implementations for STARK"""
    
    @staticmethod
    def system_ops(action: str, params: dict) -> dict:
        """System operations and basic commands"""
        try:
            if action == "launch_app":
                app_name = params.get("app_name", "").lower()
                # Normalize common misspellings or short names
                app_map = {
                    "whastapp": "WhatsApp",
                    "whatapp": "WhatsApp",
                    "whatsapp": "WhatsApp",
                    "brave": "Brave",
                    "chrome": "Chrome",
                    "edge": "Edge",
                    "notepad": "Notepad"
                }
                app_name = app_map.get(app_name, app_name)
                
                if not app_name:
                    return {"success": False, "message": "App name is required"}
                
                try:
                    if sys.platform == "win32":
                        # Try different methods to open the app on Windows
                        try:
                            # Method 1: Try direct startfile
                            os.startfile(app_name)
                        except FileNotFoundError:
                            # Method 2: Try with Start-Process PowerShell command
                            try:
                                subprocess.Popen(["powershell", "-Command", f"Start-Process '{app_name}'"], 
                                                shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            except Exception:
                                # Method 3: Try with common Windows app paths
                                common_paths = [
                                    os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), app_name),
                                    os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'), app_name),
                                    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', app_name),
                                    os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs', app_name)
                                ]
                                
                                # Try with .exe extension if not provided
                                if not app_name.lower().endswith('.exe'):
                                    common_paths.extend([
                                        os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), f"{app_name}.exe"),
                                        os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)'), f"{app_name}.exe"),
                                        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', f"{app_name}.exe"),
                                        os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs', f"{app_name}.exe")
                                    ])
                                
                                # Try each path
                                success = False
                                for path in common_paths:
                                    try:
                                        if os.path.exists(path):
                                            os.startfile(path)
                                            success = True
                                            break
                                    except Exception:
                                        continue
                                
                                if not success:
                                    # Method 4: Last resort - try with cmd
                                    subprocess.Popen(["cmd", "/c", f"start {app_name}"], 
                                                    shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", "-a", app_name])
                    else:  # Linux
                        subprocess.Popen(["xdg-open", app_name])
                    return {"success": True, "message": f"Opened {app_name}"}
                except Exception as e:
                    return {"success": False, "message": f"Failed to open {app_name}: {str(e)}"}
            
            elif action == "get_time":
                current_time = datetime.datetime.now().strftime("%H:%M:%S")
                return {"success": True, "message": f"Current time: {current_time}", "time": current_time}
            
            elif action == "get_date":
                current_date = datetime.datetime.now().strftime("%Y-%m-%d")
                return {"success": True, "message": f"Current date: {current_date}", "date": current_date}
            
            else:
                return {"success": False, "message": f"Unknown system action: {action}"}
                
        except Exception as e:
            return {"success": False, "message": f"System operation error: {str(e)}"}
    
    @staticmethod
    def file_manager(action: str, params: dict) -> dict:
        """File and directory management"""
        try:
            if action == "create_file":
                file_path = params.get("file_path", "")
                content = params.get("content", "")
                
                if not file_path:
                    return {"success": False, "message": "File path is required"}
                
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    return {"success": True, "message": f"File created: {file_path}"}
                except Exception as e:
                    return {"success": False, "message": f"Failed to create file: {str(e)}"}
            
            elif action == "list_files":
                directory = params.get("directory", ".")
                
                try:
                    files = os.listdir(directory)
                    return {"success": True, "message": f"Files in {directory}: {len(files)} files", "files": files}
                except Exception as e:
                    return {"success": False, "message": f"Failed to list files: {str(e)}"}
            
            elif action == "delete_file":
                file_path = params.get("file_path", "")
                
                if not file_path:
                    return {"success": False, "message": "File path is required"}
                
                try:
                    os.remove(file_path)
                    return {"success": True, "message": f"File deleted: {file_path}"}
                except Exception as e:
                    return {"success": False, "message": f"Failed to delete file: {str(e)}"}
            
            elif action == "copy_file":
                source = params.get("source", "")
                destination = params.get("destination", "")
                
                if not source or not destination:
                    return {"success": False, "message": "Source and destination paths are required"}
                
                try:
                    shutil.copy2(source, destination)
                    return {"success": True, "message": f"File copied from {source} to {destination}"}
                except Exception as e:
                    return {"success": False, "message": f"Failed to copy file: {str(e)}"}
            
            elif action == "create_directory":
                directory = params.get("directory", "")
                
                if not directory:
                    return {"success": False, "message": "Directory path is required"}
                
                try:
                    os.makedirs(directory, exist_ok=True)
                    return {"success": True, "message": f"Directory created: {directory}"}
                except Exception as e:
                    return {"success": False, "message": f"Failed to create directory: {str(e)}"}
            
            else:
                return {"success": False, "message": f"Unknown file action: {action}"}
                
        except Exception as e:
            return {"success": False, "message": f"File manager error: {str(e)}"}
    
    @staticmethod
    def web_tools(action: str, params: dict) -> dict:
        """Web browsing and search capabilities"""
        try:
            if action == "open_website":
                url = params.get("url", "")
                
                if not url:
                    return {"success": False, "message": "URL is required"}
                
                # Add http:// if not present
                if not url.startswith("http"):
                    url = "https://" + url
                
                try:
                    webbrowser.open(url)
                    return {"success": True, "message": f"Opened website: {url}"}
                except Exception as e:
                    return {"success": False, "message": f"Failed to open website: {str(e)}"}
            
            elif action == "search_google":
                query = params.get("query", "")
                
                if not query:
                    return {"success": False, "message": "Search query is required"}
                
                try:
                    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}" 
                    webbrowser.open(search_url)
                    return {"success": True, "message": f"Searching Google for: {query}"}
                except Exception as e:
                    return {"success": False, "message": f"Failed to search Google: {str(e)}"}
            
            elif action == "search_youtube":
                query = params.get("query", "")
                
                if not query:
                    return {"success": False, "message": "Search query is required"}
                
                try:
                    search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}" 
                    webbrowser.open(search_url)
                    return {"success": True, "message": f"Searching YouTube for: {query}"}
                except Exception as e:
                    return {"success": False, "message": f"Failed to search YouTube: {str(e)}"}
            
            elif action == "play_media":
                platform = params.get("platform", "").lower().strip()
                query = params.get("query", "").strip()
                if not query:
                    query = params.get("search_query", "").strip()
                if not query:
                    for key, value in params.items():
                        if isinstance(value, str) and value.strip() and key not in ["action", "platform"]:
                            query = value.strip()
                            break

                if not platform or not query:
                    return {"success": False, "message": "Platform and query are required"}

                try:
                    # Use the dedicated media plugin so Spotify auto-play
                    # and robust YouTube handling are centralized in one place.
                    from core.media_plugin import play_media as _local_play_media
                    ok, msg = _local_play_media(platform, query)
                    return {"success": ok, "message": msg}
                except Exception as e:
                    return {"success": False, "message": f"Failed to play media: {str(e)}"}
            
            elif action == "search_web":
                query = params.get("query", "")
                if not query:
                    return {"success": False, "message": "Search query is required"}
                try:
                    from urllib.parse import quote_plus
                    search_url = f"https://www.google.com/search?q={quote_plus(query)}"
                    webbrowser.open(search_url)
                    return {"success": True, "message": f"Searching web for: {query}"}
                except Exception as e:
                    return {"success": False, "message": f"Failed to search web: {str(e)}"}
            
            else:
                return {"success": False, "message": f"Unknown web action: {action}"}
                
        except Exception as e:
            return {"success": False, "message": f"Web tools error: {str(e)}"}
    
    @staticmethod
    def system_monitor(action: str, params: dict) -> dict:
        """System monitoring and process management"""
        try:
            if action == "get_system_info":
                try:
                    import platform
                    system_info = {
                        "system": platform.system(),
                        "node": platform.node(),
                        "release": platform.release(),
                        "version": platform.version(),
                        "machine": platform.machine(),
                        "processor": platform.processor()
                    }
                    
                    return {"success": True, "message": f"System: {system_info['system']} {system_info['release']}", "system_info": system_info}
                except Exception as e:
                    return {"success": False, "message": f"Failed to get system info: {str(e)}"}
            
            elif action == "get_running_processes":
                try:
                    processes = []
                    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                        try:
                            processes.append({
                                'pid': proc.info['pid'],
                                'name': proc.info['name'],
                                'cpu': proc.info['cpu_percent'],
                                'memory': proc.info['memory_percent']
                            })
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    
                    return {"success": True, "message": f"Found {len(processes)} running processes", "processes": processes[:20]}
                except Exception as e:
                    return {"success": False, "message": f"Failed to get running processes: {str(e)}"}
            
            elif action == "system_status":
                try:
                    cpu = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    disk = psutil.disk_usage('/')
                    
                    status = f"""System Status:
CPU: {cpu}%
RAM: {memory.percent}% ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)
Disk: {disk.percent}% ({disk.used / (1024**3):.1f}GB / {disk.total / (1024**3):.1f}GB)"""
                    
                    return {
                        "success": True,
                        "message": status,
                        "cpu_percent": cpu,
                        "ram_percent": memory.percent,
                        "disk_percent": disk.percent
                    }
                except Exception as e:
                    return {"success": False, "message": f"Failed to get system status: {str(e)}"}
            
            else:
                return {"success": False, "message": f"Unknown system monitor action: {action}"}
                
        except Exception as e:
            return {"success": False, "message": f"System monitor error: {str(e)}"}

    @staticmethod
    def automation_ops(action: str, params: dict) -> dict:
        """GhostController automation actions (keyboard, mouse, shell)"""
        return execute_automation_action(action, params)
        try:
            ghost = GhostController()

            # ── App Launcher (5-layer AppScanner) ─────────────────────────
            if action in ["launch_app", "open_app"]:
                app_name = params.get("app_name", "").strip()
                logger.info(f"AppScanner: Looking up '{app_name}'")
                try:
                    app_name_lower = app_name.lower()

                    # Strong VS Code fallback path from stark0 behavior.
                    if app_name_lower in {"vscode", "vs code", "visual studio code", "code"}:
                        vscode_candidates = [
                            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "Code.exe"),
                            r"C:\Program Files\Microsoft VS Code\Code.exe",
                            r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
                        ]
                        for candidate in vscode_candidates:
                            if os.path.exists(candidate):
                                subprocess.Popen([candidate])
                                return {"success": True, "message": f"Opened VS Code: {candidate}"}
                        # PATH fallback
                        try:
                            subprocess.Popen(["code"])
                            return {"success": True, "message": "Opened VS Code via PATH command"}
                        except Exception:
                            pass

                    from core.app_scanner import AppScanner, launch_app as _local_scanner_launch
                    scanner = AppScanner()
                    app_path = scanner.find(app_name)
                    if app_path:
                        # Use shell=True specifically for .cmd or .bat files
                        is_shell = app_path.lower().endswith((".cmd", ".bat"))
                        if is_shell:
                            subprocess.Popen(app_path, shell=True)
                            msg = f"Launched {app_name} (shell) ✓"
                            return {"success": True, "message": msg}
                        
                        ok, msg = _local_scanner_launch(app_path, app_name)
                        return {"success": ok, "message": msg}
                    else:
                        # Hard fallback to ghost controller
                        success = ghost.open_application(app_name)
                        return {"success": success, "message": f"{'Opened' if success else 'Could not find'}: {app_name}"}
                except Exception as scan_err:
                    logger.warning(f"AppScanner error: {scan_err} - falling back to ghost")
                    success = ghost.open_application(app_name)
                    return {"success": success, "message": f"Launch {app_name}: {'OK' if success else 'Failed'}"}
            
            elif action == "type_text":
                text = params.get("text", "")
                success = ghost.type_text(text)
                return {"success": success, "message": f"Typed text: {text[:20]}..."}
                
            elif action == "click_mouse":
                x = params.get("x", 0)
                y = params.get("y", 0)
                button = params.get("button", "left")
                success = ghost.click_mouse(x, y, button)
                return {"success": success, "message": f"Clicked {button} at ({x}, {y})"}
            
            elif action == "press_key":
                key = params.get("key", "")
                success = ghost.press_key(key)
                return {"success": success, "message": f"Pressed key: {key}"}
            
            elif action == "run_terminal":
                command = params.get("command", "")
                success = ghost.run_command(command)
                return {"success": success, "message": f"Ran command: {command}"}
            
            elif action == "delay":
                seconds = params.get("seconds", 1)
                time.sleep(float(seconds))
                return {"success": True, "message": f"Delayed for {seconds}s"}
            
            elif action == "open_url":
                url = params.get("url", "")
                webbrowser.open(url)
                return {"success": True, "message": f"Opened URL: {url}"}

            # ── Media (Spotify auto-play, YouTube direct link, Netflix) ────
            elif action == "play_media":
                platform = params.get("platform", "").lower()
                query = params.get("query", "")
                try:
                    from core.media_plugin import play_media as _local_play_media
                    ok, msg = _local_play_media(platform, query)
                    return {"success": ok, "message": msg}
                except Exception as e:
                    return {"success": False, "message": f"play_media error: {e}"}

            elif action == "search_web":
                query = params.get("query", "")
                try:
                    from urllib.parse import quote_plus
                    webbrowser.open(f"https://www.google.com/search?q={quote_plus(query)}")
                    return {"success": True, "message": f"🔍 Searching Google for: {query}"}
                except Exception as e:
                    return {"success": False, "message": f"search_web error: {e}"}

            # ── Close Apps ────────────────────────────────────────────────
            elif action == "close_apps":
                apps = params.get("value", params.get("apps", []))
                if isinstance(apps, str):
                    apps = [apps]
                killed = []
                for app in apps:
                    exe = app if app.endswith(".exe") else f"{app}.exe"
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/IM", exe],
                            capture_output=True, timeout=5
                        )
                        killed.append(app)
                    except Exception:
                        pass
                return {"success": True, "message": f"🔴 Closed: {', '.join(killed) or 'none'}"}

            # ── Set Volume ────────────────────────────────────────────────
            elif action == "set_volume":
                level = int(params.get("value", params.get("level", 50)))
                level = max(0, min(100, level))
                try:
                    # PowerShell approach via WScript
                    ps_cmd = f"""
$wsh = New-Object -ComObject WScript.Shell
$vol = [int]({level} / 100.0 * 65535)
(New-Object -ComObject Shell.Application).SetVolume($vol) 2>$null
# Fallback: set via master volume API
$code = @'
using System.Runtime.InteropServices;
public class AudioCtrl {{
    [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte sc, int flags, int extra);
}}
'@
Add-Type $code -ErrorAction SilentlyContinue
# Use nircmd if available
nircmd.exe setsysvolume {int(level / 100 * 65535)} 2>$null | Out-Null
"""
                    subprocess.Popen(
                        ["powershell", "-NoProfile", "-NonInteractive",
                         "-WindowStyle", "Hidden", "-Command", ps_cmd],
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    return {"success": True, "message": f"🔊 Volume set to {level}%"}
                except Exception:
                    # Fallback: press volume up/down keys
                    if HAS_PYAUTOGUI:
                        try:
                            import pyautogui
                            if level == 0:
                                for _ in range(50):
                                    pyautogui.press("volumedown")
                            else:
                                for _ in range(10):
                                    pyautogui.press("volumeup")
                        except Exception:
                            pass
                    return {"success": True, "message": f"🔊 Volume adjusted"}

            # ── Activate Listening ────────────────────────────────────────
            elif action == "activate_listening":
                # Signal the GUI to start mic — published via a shared flag
                import builtins
                setattr(builtins, "_stark_activate_mic", True)
                return {"success": True, "message": "🎤 STARK is listening..."}

            # ── Create Folder ─────────────────────────────────────────────
            elif action == "create_folder":
                folder = params.get("value", params.get("path", "ai_project"))
                # Default to current working directory for predictable workflow behavior.
                if not os.path.isabs(folder):
                    folder = os.path.join(os.getcwd(), folder)
                abs_path = os.path.abspath(folder)
                existed = os.path.isdir(abs_path)

                try:
                    os.makedirs(abs_path, exist_ok=True)
                except Exception:
                    # Fallback for permission/path edge cases
                    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                    abs_path = os.path.abspath(os.path.join(desktop, os.path.basename(folder)))
                    existed = os.path.isdir(abs_path)
                    os.makedirs(abs_path, exist_ok=True)

                if existed:
                    return {"success": True, "message": f"📁 Folder already exists: {abs_path}"}
                return {"success": True, "message": f"📁 Folder created at: {abs_path}"}

            # ── Open Terminal ─────────────────────────────────────────────
            elif action == "open_terminal":
                try:
                    # Try Windows Terminal first, fall back to cmd
                    subprocess.Popen(["wt"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                except FileNotFoundError:
                    subprocess.Popen("start cmd", shell=True)
                return {"success": True, "message": "💻 Terminal opened"}

            else:
                return {"success": False, "message": f"Unknown automation action: {action}"}
        except Exception as e:
            return {"success": False, "message": f"Automation error: {str(e)}"}


class EnhancedPluginManager:
    """Enhanced plugin management system with file indexer and screen intelligence support"""
    
    def __init__(self, config: STARKConfig, file_indexer=None, screen_intelligence=None):
        self.config = config
        self.file_indexer = file_indexer  # NEW
        self.screen_intelligence = screen_intelligence  # NEW
        self.plugins = {}
        self.plugin_actions = {}
        self.load_core_plugins()
    
    def load_core_plugins(self):
        """Load all core plugins"""
        # Built-in plugins
        self.register_plugin("system_ops", BuiltInPlugins.system_ops)
        self.register_plugin("file_manager", BuiltInPlugins.file_manager)
        self.register_plugin("web_tools", BuiltInPlugins.web_tools)
        self.register_plugin("system_monitor", BuiltInPlugins.system_monitor)
        self.register_plugin("automation_ops", BuiltInPlugins.automation_ops)
        
        # Advanced plugins
        self.register_plugin("voice_control", AdvancedPlugins.voice_control)
        self.register_plugin("smart_automation", AdvancedPlugins.smart_automation)
        self.register_plugin("content_generation", AdvancedPlugins.content_generation)
        self.register_plugin("system_intelligence", AdvancedPlugins.system_intelligence)
        
        logger.info(f"Loaded {len(self.plugins)} core plugins")
    
    def register_plugin(self, name: str, plugin_function):
        """Register a plugin"""
        if name not in self.config.disabled_plugins:
            self.plugins[name] = {
                'function': plugin_function,
                'enabled': True
            }
    
    def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action - handles both plugin actions and enhanced actions"""

        # Priority route for workflow-critical desktop actions.
        # This avoids weaker generic handlers intercepting them.
        if action in {
            "launch_app", "open_app", "create_folder", "open_terminal",
            "run_terminal", "press_key", "type_text", "click_mouse", "delay",
            "close_apps", "set_volume", "activate_listening", "play_media", "open_url",
            "search_web", "send_whatsapp_message", "add_contact", "update_contact",
            "remove_contact", "list_contacts", "update_workflow", "bind_workflow",
            "list_workflows", "reset_workflow"
        }:
            try:
                return BuiltInPlugins.automation_ops(action, params)
            except Exception as e:
                return {"success": False, "message": f"Priority action error: {e}"}
        
        # NEW: Handle file operations with indexer
        if action == 'file_search' and self.file_indexer:
            pattern = params.get('pattern', '')
            location = params.get('location', None)
            files = self.file_indexer.search(pattern, location)
            
            if not files:
                return {"success": False, "message": f"No files found matching '{pattern}'"}
            
            return {
                "success": True,
                "message": f"Found {len(files)} files",
                "count": len(files),
                "files": files[:20]
            }
        
        # NEW: Handle screen operations
        elif action == 'screen_read' and self.screen_intelligence:
            result = self.screen_intelligence.read_screen()
            return result
        
        elif action == 'screen_find_text' and self.screen_intelligence:
            search_text = params.get('text', '')
            if not search_text:
                return {"success": False, "message": "Search text is required"}
            result = self.screen_intelligence.find_text_on_screen(search_text)
            return result
        
        # NEW: Handle system status
        elif action == 'system_status':
            try:
                cpu = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                return {
                    "success": True,
                    "message": f"CPU: {cpu}%, RAM: {memory.percent}%, Disk: {disk.percent}%",
                    "cpu_percent": cpu,
                    "ram_percent": memory.percent,
                    "disk_percent": disk.percent
                }
            except Exception as e:
                return {"success": False, "message": f"Failed to get system status: {str(e)}"}
        
        # Existing plugin execution logic
        for plugin_name, plugin_data in self.plugins.items():
            if plugin_data['enabled']:
                try:
                    result = plugin_data['function'](action, params)
                    if result.get("success") is not False or "Unknown" not in result.get("message", ""):
                        return result
                except Exception as e:
                    logger.error(f"Plugin '{plugin_name}' failed to execute action '{action}': {e}")
                    continue
        
        return {"success": False, "message": f"No plugin found to handle action: {action}"}
    
    def get_available_actions(self) -> List[str]:
        """Get list of all available actions"""
        actions = [
            "open_app", "get_time", "get_date",
            "create_file", "list_files", "delete_file", "copy_file", "create_directory",
            "open_website", "search_google", "search_youtube", "youtube_play_first",
            "get_system_info", "get_running_processes", "system_status",
            "speak", "listen",
            "create_smart_workflow", "schedule_task",
            "generate_code", "generate_document",
            "analyze_system_health", "optimize_system"
        ]
        
        # Add enhanced actions if available
        if self.file_indexer:
            actions.extend(["file_search", "file_cleanup"])
        
        if self.screen_intelligence and self.screen_intelligence.enabled:
            actions.extend(["screen_read", "screen_find_text"])
        
        return actions
    
    def get_plugin_info(self) -> Dict[str, Dict]:
        """Get information about loaded plugins"""
        return {name: {'enabled': data['enabled']} for name, data in self.plugins.items()}


# REPLACED: EnhancedLLMClient removed in favor of API-based reasoning.


class STARK:
    """Main STARK Assistant - Enhanced Production Version with 2-Tier Intelligence"""
    
    def __init__(self, config: Optional[STARKConfig] = None):
        self.config = config or STARKConfig.load_from_file()
        
        # NEW: Initialize file indexer
        self.file_indexer = None
        if self.config.file_index_enabled:
            self.file_indexer = FileIndexer()
            if self.config.auto_index_on_startup:
                # Start indexing in background
                threading.Thread(
                    target=self.file_indexer.build_index,
                    args=(self.config.index_locations, self.config.exclude_paths),
                    daemon=True
                ).start()
        
        # NEW: Initialize screen intelligence
        self.screen_intelligence = ScreenIntelligence(self.config)
        
        # NEW: Initialize intent router (Tier 1)
        self.intent_router = IntentRouter(self.config)
        
        # Update plugin manager initialization with enhanced features
        self.plugin_manager = EnhancedPluginManager(
            self.config,
            file_indexer=self.file_indexer,
            screen_intelligence=self.screen_intelligence
        )
        
        # LLM integration removed in favor of AIReasoningEngine (Groq)
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        api_key = load_api_key_into_env(prefer_saved=True)
        self.ai_engine = AIReasoningEngine(api_key=api_key)
        self.workflow_engine = WorkflowEngine(self.plugin_manager)
        
        self.conversation_manager = ConversationManager()
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_actions)
        self.running = False
        self.session_id = f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # NEW: Context memory for Intent Anticipation
        self.context_memory = {
            "last_media_query": None,
            "last_app_opened": None,
            "last_workflow": None,
            "last_action": None
        }
        
        # Set up signal handlers for graceful shutdown
        try:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        except AttributeError:
            pass
        
        # Initialize voice control if enabled
        self.voice_enabled = self.config.voice_enabled and TTS_AVAILABLE
        
        logger.info(f"STARK Enhanced with 2-Tier Intelligence initialized - Session: {self.session_id}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.shutdown()
    
    def startup_check(self) -> bool:
        """Enhanced startup checks with comprehensive diagnostics"""
        logger.info("Performing enhanced startup checks...")
        
        # Plugin system check
        plugin_info = self.plugin_manager.get_plugin_info()
        enabled_plugins = sum(1 for p in plugin_info.values() if p['enabled'])
        total_actions = len(self.plugin_manager.get_available_actions())
        logger.info(f"Plugin System: {enabled_plugins}/{len(plugin_info)} plugins enabled, {total_actions} actions available")
        
        # File indexer check
        if self.file_indexer:
            logger.info("File Indexer: Enabled and operational")
        else:
            logger.info("File Indexer: Disabled")
        
        # Screen intelligence check
        if self.screen_intelligence and self.screen_intelligence.enabled:
            logger.info(f"Screen Intelligence: Enabled (OCR: {self.config.ocr_engine})")
        else:
            logger.info("Screen Intelligence: Disabled or unavailable")
        
        # LLM check removed (API-only)
        logger.info("Reasoning System: API-driven (Groq) ready for integration")
        
        # Voice system check
        if self.config.voice_enabled:
            if TTS_AVAILABLE and SPEECH_RECOGNITION_AVAILABLE:
                logger.info("Voice System: Fully operational (TTS + Speech Recognition)")
            elif TTS_AVAILABLE:
                logger.info("Voice System: TTS only (install speech_recognition for full voice control)")
            else:
                logger.warning("Voice System: Not available (install pyttsx3 and speech_recognition)")
        
        # Database check
        try:
            recent_conversations = self.conversation_manager.get_recent_conversations(limit=1)
            logger.info("Database System: Operational")
        except Exception as e:
            logger.warning(f"Database System: Issues detected - {e}")
            
        # Groq API check
        api_key = os.environ.get("GROQ_API_KEY")
        logger.info(f"Groq API Key: {'Configured' if api_key else 'Not configured'}")
        return True
    
    def observe_screen(self) -> str:
        """Captures screen and returns OCR text for agent feedback"""
        try:
            result = self.screen_intelligence.read_screen()
            if result.get("success"):
                return result.get("text", "No text found on screen.")[:2000]
            return "Screen capture failed or no text found."
        except Exception as e:
            return f"Error observing screen: {str(e)}"

    def process_request(self, user_input: str, use_context: bool = True) -> str:
        """Enhanced request processing with ReAct Autonomous Intelligence"""
        if not user_input.strip():
            return "Please provide a valid request."
        
        try:
            # Tier 1 - Try pattern-based routing first
            direct_route = self.intent_router.route(user_input)
            if direct_route:
                action_name, params = direct_route
                result = self.plugin_manager.execute_action(action_name, params)
                chat_response = f"✅ {result.get('message', 'Action completed')}" if result.get("success") else f"❌ {result.get('message', 'Action failed')}"
                return chat_response
            
            # Tier 2 - ReAct Autonomous Loop
            logger.info("Initializing ReAct Autonomous Loop")
            
            current_goal = user_input
            max_cycles = 3
            current_cycle = 0
            final_chat = ""
            executed_actions_total = []
            
            # Call AI exactly ONCE for Tier 2 tasks
            screen_state = "None (Initial Step)"
            llm_response = self.ai_engine.parse_instruction(
                current_goal,
                context=self.context_memory,
                params={"screen_state": screen_state}
            )
            
            chat_msg = llm_response.get("chat", "")
            actions = llm_response.get("actions", [])
            final_chat = chat_msg

            if llm_response.get("task") == "update_workflow":
                result = self.plugin_manager.execute_action(
                    "update_workflow",
                    {
                        "gesture": llm_response.get("gesture", ""),
                        "actions": actions,
                    },
                )
                if result.get("success"):
                    return f"{chat_msg or 'Workflow updated.'}\n\n{result.get('message', '')}".strip()
                return f"I hit a snag while updating the workflow: {result.get('message', 'Unknown error')}"

            if llm_response.get("task") == "bind_workflow":
                result = self.plugin_manager.execute_action(
                    "bind_workflow",
                    {
                        "gesture": llm_response.get("gesture", ""),
                        "workflow": llm_response.get("workflow", ""),
                    },
                )
                if result.get("success"):
                    return f"{chat_msg or 'Workflow binding updated.'}\n\n{result.get('message', '')}".strip()
                return f"I hit a snag while binding the workflow: {result.get('message', 'Unknown error')}"
            
            if actions:
                # Execute the actions the AI planned
                logger.info(f"Executing {len(actions)} planned actions...")
                success = self.workflow_engine.execute_workflow("AI_Plan", actions)
                executed_actions_total.extend(actions)
                
                # Update context memory
                for action in actions:
                    act_name = action.get("action")
                    p = action.get("params", {})
                    self.context_memory["last_action"] = act_name
                    if act_name == "play_media":
                        self.context_memory["last_media_query"] = p.get("query")
                    elif act_name in ["launch_app", "open_app"]:
                        self.context_memory["last_app_opened"] = p.get("app_name")
                
                if not success:
                    final_chat = f"I hit a snag during the workflow: {chat_msg}"
            
            # Build final response
            response = final_chat
            if executed_actions_total:
                response += "\n\nActions executed:\n" + "\n".join([f"• {a['action']}" for a in executed_actions_total])
            
            # Save conversation
            if self.config.auto_save_conversations:
                self.conversation_manager.save_conversation(
                    user_input=user_input,
                    stark_response=response,
                    actions=executed_actions_total,
                    session_id=self.session_id,
                    metadata={"cycles": current_cycle, "success": True, "tier": 2}
                )
            
            return response
            
        except Exception as e:
            error_msg = f"Sorry, I encountered an error processing your request: {str(e)}"
            logger.error(f"Request processing error: {e}")
            
            if self.config.auto_save_conversations:
                self.conversation_manager.save_conversation(
                    user_input=user_input,
                    stark_response=error_msg,
                    session_id=self.session_id,
                    metadata={"error": str(e), "success": False}
                )
            
            return error_msg
    
    def _execute_enhanced_actions(self, actions: List[Dict[str, Any]], user_input: str = None) -> List[str]:
        """Enhanced action execution with intelligent error handling"""
        results = []
        
        def execute_single_action(action_data, index):
            """Execute single action with enhanced logging"""
            try:
                action_name = action_data.get("action", "")
                params = action_data.get("params", {})
                
                if not action_name:
                    return f"Action {index + 1}: ❌ Invalid - missing action name"
                
                # Special handling for youtube_play_first action
                if action_name == "youtube_play_first" and not params.get("query") and user_input:
                    # Extract query from user input if not provided in params
                    patterns = [
                        r"(?:search|find|play|youtube)\s+(?:for\s+)?['\"]?([^'\"]+)['\"]?",
                        r"(?:search|find|play)\s+([^\s]+(?:\s+[^\s]+)*)",
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, user_input, re.IGNORECASE)
                        if match:
                            params["query"] = match.group(1).strip()
                            break
                
                start_time = time.time()
                result = self.plugin_manager.execute_action(action_name, params)
                execution_time = time.time() - start_time
                
                if result.get("success", False):
                    return f"Action {index + 1} ({action_name}): ✅ {result.get('message', 'Success')} ({execution_time:.2f}s)"
                else:
                    return f"Action {index + 1} ({action_name}): ❌ {result.get('message', 'Failed')} ({execution_time:.2f}s)"
                    
            except Exception as e:
                logger.error(f"Action execution error: {e}")
                return f"Action {index + 1}: ❌ Error - {str(e)}"
        
        # Execute actions with timeout protection
        try:
            with ThreadPoolExecutor(max_workers=self.config.max_concurrent_actions) as executor:
                future_to_action = {
                    executor.submit(execute_single_action, action, i): (action, i)
                    for i, action in enumerate(actions)
                }
                
                for future in future_to_action:
                    try:
                        result = future.result(timeout=self.config.action_timeout)
                        results.append(result)
                    except TimeoutError:
                        action, index = future_to_action[future]
                        action_name = action.get("action", "unknown")
                        results.append(f"Action {index + 1} ({action_name}): ⏰ Timed out after {self.config.action_timeout}s")
                    except Exception as e:
                        action, index = future_to_action[future]
                        action_name = action.get("action", "unknown")
                        results.append(f"Action {index + 1} ({action_name}): ❌ Execution error - {str(e)}")
                        
        except Exception as e:
            logger.error(f"Error in enhanced concurrent execution: {e}")
            results.append(f"Execution system error: {str(e)}")
        
        return results
    
    def run_interactive(self):
        """Enhanced interactive mode with advanced features"""
        self.running = True
        
        print("=" * 70)
        print("🤖 STARK - Hybrid LLM-powered Smart Desktop Assistant (Enhanced)")
        print("=" * 70)
        print("🚀 2-Tier Intelligence System:")
        print("   • Tier 1: Instant pattern matching (<10ms)")
        print("   • Tier 2: Advanced LLM processing")
        print("\n✨ Enhanced Features:")
        if self.file_indexer:
            print("   • File indexing and ultra-fast search")
        if self.screen_intelligence and self.screen_intelligence.enabled:
            print("   • Screen reading with OCR")
        print("   • Advanced content generation")
        print("   • System intelligence and monitoring")
        print("   • Voice control and automation")
        print("\n📝 Commands:")
        print("   • 'help' - Show available commands")
        print("   • 'status' - Show system status")
        print("   • 'history' - View recent conversations")
        print("   • 'exit' or 'quit' - Exit STARK")
        print("=" * 70)
        
        # Perform startup check
        startup_ok = self.startup_check()
        if startup_ok:
            print("✅ All systems operational!\n")
        else:
            print("⚠️ Some systems have warnings, but STARK is operational.\n")
        
        while self.running:
            try:
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['exit', 'quit', 'bye']:
                    print("👋 Goodbye! STARK shutting down...")
                    self.shutdown()
                    break
                
                if user_input.lower() == 'help':
                    self._show_help()
                    continue
                
                if user_input.lower() == 'status':
                    self._show_status()
                    continue
                
                if user_input.lower() == 'history':
                    self._show_history()
                    continue
                
                if user_input.lower() == 'voice':
                    self._toggle_voice_mode()
                    continue
                
                # Process the request
                response = self.process_request(user_input)
                print(f"\n🤖 STARK: {response}\n")
                
            except EOFError:
                # Non-interactive shell or closed stdin; exit cleanly.
                logger.info("EOF on stdin. Exiting interactive mode.")
                self.shutdown()
                break
            except KeyboardInterrupt:
                print("\n\n👋 Keyboard interrupt detected. Shutting down...")
                self.shutdown()
                break
            except Exception as e:
                logger.error(f"Interactive loop error: {e}")
                print(f"❌ Error: {str(e)}\n")
    
    def _show_help(self):
        """Display help information"""
        print("\n" + "=" * 70)
        print("📚 STARK HELP - Available Commands")
        print("=" * 70)
        print("\n🎯 SYSTEM COMMANDS:")
        print("  • help     - Show this help message")
        print("  • status   - Show system and plugin status")
        print("  • history  - View recent conversation history")
        print("  • voice    - Toggle voice mode on/off")
        print("  • exit     - Exit STARK")
        
        print("\n⚡ TIER 1 COMMANDS (Instant - No LLM):")
        print("  • 'what time is it' - Get current time")
        print("  • 'open <app>' - Open an application")
        print("  • 'read screen' - Read text from screen (OCR)")
        print("  • 'system status' - Get CPU/RAM/Disk stats")
        print("  • 'find files named <pattern>' - Search indexed files")
        
        print("\n🧠 TIER 2 COMMANDS (LLM-Powered):")
        print("  • Complex queries and multi-step workflows")
        print("  • Content generation and code creation")
        print("  • System analysis and optimization")
        print("  • Web searches and automation")
        
        print("\n📋 EXAMPLE COMMANDS:")
        print("  • 'find all Python files'")
        print("  • 'create a todo list app in Python'")
        print("  • 'analyze system health and create a report'")
        print("  • 'search YouTube for Python tutorials and play first'")
        print("  • 'read my screen'")
        print("=" * 70 + "\n")
    
    def _show_status(self):
        """Display system status"""
        print("\n" + "=" * 70)
        print("📊 STARK SYSTEM STATUS")
        print("=" * 70)
        
        # System resources
        try:
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            print(f"\n💻 System Resources:")
            print(f"  • CPU Usage: {cpu}%")
            print(f"  • RAM Usage: {memory.percent}% ({memory.used / (1024**3):.1f}GB / {memory.total / (1024**3):.1f}GB)")
        except:
            print("\n💻 System Resources: Unable to retrieve")
        
        # Plugin status
        plugins = self.plugin_manager.get_plugin_info()
        enabled_count = sum(1 for p in plugins.values() if p['enabled'])
        print(f"\n🔌 Plugins: {enabled_count}/{len(plugins)} enabled")
        
        # Enhanced features status
        print(f"\n✨ Enhanced Features:")
        print(f"  • File Indexer: {'✅ Enabled' if self.file_indexer else '❌ Disabled'}")
        print(f"  • Screen Intelligence: {'✅ Enabled' if (self.screen_intelligence and self.screen_intelligence.enabled) else '❌ Disabled'}")
        print(f"  • Voice Control: {'✅ Enabled' if self.voice_enabled else '❌ Disabled'}")
        print(f"  • 2-Tier Intelligence: ✅ Active")
        
        # Reasoning status
        api_key_present = bool(os.environ.get("GROQ_API_KEY"))
        print(
            f"  • Groq API: {'✅ Configured (Tier 2 available)' if api_key_present else '⚠️ Missing key (Tier 1 only)'}"
        )
        
        print(f"\n📅 Session: {self.session_id}")
        print("=" * 70 + "\n")
    
    def _show_history(self):
        """Display conversation history"""
        print("\n" + "=" * 70)
        print("📜 RECENT CONVERSATION HISTORY")
        print("=" * 70)
        
        try:
            history = self.conversation_manager.get_recent_conversations(
                limit=5, session_id=self.session_id
            )
            
            if not history:
                print("\nNo conversation history for this session yet.\n")
            else:
                for i, conv in enumerate(reversed(history), 1):
                    timestamp = conv.get('timestamp', 'Unknown')
                    user_input = conv.get('user_input', '')[:100]
                    stark_response = conv.get('stark_response', '')[:100]
                    
                    print(f"\n[{i}] {timestamp}")
                    print(f"You: {user_input}...")
                    print(f"STARK: {stark_response}...")
                
            print("\n" + "=" * 70 + "\n")
        except Exception as e:
            print(f"Error retrieving conversation history: {e}")
    
    def _toggle_voice_mode(self):
        """Toggle voice mode on/off"""
        if TTS_AVAILABLE and SPEECH_RECOGNITION_AVAILABLE:
            self.voice_enabled = not self.voice_enabled
            status = "enabled" if self.voice_enabled else "disabled"
            print(f"🎤 Voice mode {status}")
        else:
            print("❌ Voice mode not available. Install pyttsx3 and speech_recognition packages.")
    
    def shutdown(self):
        """Enhanced graceful shutdown"""
        logger.info("Shutting down STARK Enhanced...")
        self.running = False
        
        # Save final configuration
        try:
            self.config.save_to_file()
        except Exception as e:
            logger.error(f"Error saving config during shutdown: {e}")
        
        # Shutdown executor
        try:
            self.executor.shutdown(wait=True)
        except Exception as e:
            logger.error(f"Error shutting down executor: {e}")
        
        logger.info("STARK Enhanced shutdown complete")


def main():
    """Enhanced main entry point for STARK"""
    print("🚀 Initializing STARK - Hybrid LLM-powered Smart Desktop Assistant (Enhanced)")
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="STARK - Smart Desktop Assistant with 2-Tier Intelligence")
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--voice', action='store_true', help='Enable voice control')
    parser.add_argument('--config', type=str, help='Configuration file path')
    parser.add_argument('--no-index', action='store_true', help='Disable file indexing on startup')
    parser.add_argument('--set-api-key', action='store_true', help='Prompt to save/update the Groq API key')
    parser.add_argument('--clear-api-key', action='store_true', help='Remove the saved Groq API key')
    parser.add_argument('command', nargs='*', help='Single command to execute')
    
    args = parser.parse_args()
    
    # Load configuration
    config_path = args.config or "stark_config.yaml"
    config = STARKConfig.load_from_file(config_path)
    
    # Apply command line overrides
    if args.debug:
        config.debug_mode = True
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled via command line")
    
    if args.voice:
        config.voice_enabled = True
    
    if args.no_index:
        config.auto_index_on_startup = False

    if args.clear_api_key:
        cleared_path = clear_api_key()
        os.environ.pop("GROQ_API_KEY", None)
        if cleared_path:
            print(f"Saved API key removed from {cleared_path}")
        else:
            print(f"No saved API key found in {get_settings_path()}")
        return

    api_key = ensure_api_key(gui=False, force_prompt=args.set_api_key, allow_skip=True)
    saved_api_key = get_saved_api_key()
    if api_key and saved_api_key and api_key == saved_api_key:
        print(f"Using saved API key from {get_settings_path()}")
    elif api_key:
        print("Using GROQ_API_KEY from the current environment.")
    else:
        load_api_key_into_env(prefer_saved=True)
        print("No saved API key found. STARK will continue in limited Tier 1 mode.")

    # Initialize STARK
    try:
        stark = STARK(config)
        
        # Check for single command mode
        if args.command:
            command = ' '.join(args.command)
            print(f"🎯 Executing: {command}")
            response = stark.process_request(command)
            print(f"💬 {response}")
        else:
            # Interactive mode
            stark.run_interactive()
            
    except KeyboardInterrupt:
        print("\n👋 STARK interrupted by user.")
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        print(f"❌ Fatal error: {str(e)}")
        if config.debug_mode:
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
