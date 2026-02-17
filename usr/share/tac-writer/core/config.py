"""
TAC Configuration Module
Application configuration management - cross-platform (Linux/Windows)
"""

import os
import json
import platform
from pathlib import Path
from typing import Dict, Any, Optional, List

IS_WINDOWS = platform.system() == 'Windows'


class Config:
    """Application configuration manager"""

    # Application version and metadata
    APP_VERSION = "1.33.1"
    APP_NAME = "TAC"
    APP_FULL_NAME = "TAC - Continuous Argumentation Technique"
    APP_DESCRIPTION = "Academic Writing Assistant"
    APP_WEBSITE = "https://tacwriter.com.br"
    APP_COPYRIGHT = "© 2025 TAC Development"
    APP_DEVELOPERS = ["Tales Mendonça, Narayan Silva, Jibreel al-Yahya"]
    APP_DESIGNERS = ["Narayan Silva"]

    def __init__(self):
        self._setup_directories()
        self._load_defaults()
        self.load()

    def _setup_directories(self):
        """Setup application directories - cross-platform"""
        home = Path.home()

        if IS_WINDOWS:
            # Windows: use APPDATA / LOCALAPPDATA
            appdata = Path(os.environ.get('APPDATA', home / 'AppData' / 'Roaming'))
            localappdata = Path(os.environ.get('LOCALAPPDATA', home / 'AppData' / 'Local'))

            self.data_dir = localappdata / 'tac'
            self.config_dir = appdata / 'tac'
            self.cache_dir = localappdata / 'tac' / 'cache'
        else:
            # Linux/macOS: follow XDG standards
            xdg_data_home = os.environ.get('XDG_DATA_HOME')
            if xdg_data_home:
                self.data_dir = Path(xdg_data_home) / 'tac'
            else:
                self.data_dir = home / '.local' / 'share' / 'tac'

            xdg_config_home = os.environ.get('XDG_CONFIG_HOME')
            if xdg_config_home:
                self.config_dir = Path(xdg_config_home) / 'tac'
            else:
                self.config_dir = home / '.config' / 'tac'

            xdg_cache_home = os.environ.get('XDG_CACHE_HOME')
            if xdg_cache_home:
                self.cache_dir = Path(xdg_cache_home) / 'tac'
            else:
                self.cache_dir = home / '.cache' / 'tac'

        # Create directories if they don't exist
        for directory in [self.data_dir, self.config_dir, self.cache_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def _load_defaults(self):
        """Load default configuration values"""

        # Platform-aware defaults
        if IS_WINDOWS:
            default_font = 'Times New Roman'
        else:
            default_font = 'Liberation Serif'

        # Documents folder (works on both platforms)
        documents_dir = str(Path.home() / 'Documents')

        self._config = {
            # Window settings
            'window_width': 1200,
            'window_height': 800,
            'window_maximized': False,
            'window_position': None,

            # Editor settings
            'font_family': default_font,
            'font_size': 12,
            'line_spacing': 1.5,
            'show_line_numbers': True,
            'word_wrap': True,
            'highlight_current_line': True,
            'auto_save': True,
            'auto_save_interval': 5,

            # Spell checking settings
            'spell_check_enabled': True,
            'spell_check_language': 'pt_BR',
            'spell_check_show_language_menu': True,
            'spell_check_available_languages': ['pt_BR', 'en_US', 'es_ES', 'fr_FR', 'de_DE', 'it_IT', 'ru_RU', 'zh_CH'],
            'spell_check_personal_dictionary': str(self.config_dir / 'personal_dict.txt'),

            # Formatting defaults
            'default_paragraph_indent': 1.25,
            'quote_indent': 4.0,
            'page_margins': {
                'top': 2.5,
                'bottom': 2.5,
                'left': 3.0,
                'right': 3.0
            },

            # Application behavior
            'backup_files': True,
            'recent_files_limit': 10,
            'confirm_on_close': True,
            'restore_session': True,
            'show_welcome_dialog': True,
            'show_first_run_tutorial': True,
            'show_post_creation_tip': True,

            # Update checking
            'check_for_updates': True,
            'update_check_interval_hours': 24,
            'last_update_check': '',
            'skipped_version': '',

            # Theme and appearance
            'use_dark_theme': False,
            'adaptive_theme': True,
            'enable_animations': True,
            'color_bg': '#ffffff',
            'color_font': '#2e2e2e',
            'color_accent': '#3584e4',

            # Project defaults
            'database_file': str(self.data_dir / 'projects.db'),
            'project_template': 'academic_essay',

            # Export settings
            'export_location': documents_dir,
            'default_export_format': 'odt',
            'include_metadata': True,

            # AI assistant
            'ai_assistant_enabled': False,
            'ai_assistant_api_key': '',
            'ai_openrouter_site_url': '',
            'ai_openrouter_site_name': '',

            # Recent projects list
            'recent_projects': []
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        self._config[key] = value

    def update(self, updates: Dict[str, Any]) -> None:
        """Update multiple configuration values"""
        self._config.update(updates)

    def reset(self, key: Optional[str] = None) -> None:
        """Reset configuration to defaults"""
        if key:
            defaults = Config()._config
            if key in defaults:
                self._config[key] = defaults[key]
        else:
            self._load_defaults()

    @property
    def config_file(self) -> Path:
        """Path to the configuration file"""
        return self.config_dir / 'config.json'

    @property
    def database_path(self) -> Path:
        """Path to the SQLite database file"""
        db_path = Path(self.get('database_file'))
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    def save(self) -> bool:
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving configuration: {e}")
            return False

    def load(self) -> bool:
        """Load configuration from file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                self._config.update(saved_config)
            return True
        except Exception as e:
            print(f"Error loading configuration: {e}")
            return False

    def get_recent_projects(self) -> list:
        """Get list of recent projects"""
        return self.get('recent_projects', [])

    def add_recent_project(self, project_path: str) -> None:
        """Add project to recent projects list"""
        recent = self.get_recent_projects()
        if project_path in recent:
            recent.remove(project_path)
        recent.insert(0, project_path)
        limit = self.get('recent_files_limit', 10)
        recent = recent[:limit]
        self.set('recent_projects', recent)

    def remove_recent_project(self, project_path: str) -> None:
        """Remove project from recent projects list"""
        recent = self.get_recent_projects()
        if project_path in recent:
            recent.remove(project_path)
            self.set('recent_projects', recent)

    def export_config(self, file_path: str) -> bool:
        """Export configuration to file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error exporting configuration: {e}")
            return False

    def import_config(self, file_path: str) -> bool:
        """Import configuration from file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)
            self._config.update(imported_config)
            return True
        except Exception as e:
            print(f"Error importing configuration: {e}")
            return False

    # Spell checking methods
    def get_spell_check_enabled(self) -> bool:
        return self.get('spell_check_enabled', True)

    def set_spell_check_enabled(self, enabled: bool) -> None:
        self.set('spell_check_enabled', enabled)

    def get_spell_check_language(self) -> str:
        return self.get('spell_check_language', 'pt_BR')

    def set_spell_check_language(self, language: str) -> None:
        if self.is_spell_language_available(language):
            self.set('spell_check_language', language)

    def get_available_spell_languages(self) -> List[str]:
        return self.get('spell_check_available_languages', ['pt_BR', 'en_US', 'es_ES', 'fr_FR', 'de_DE', 'it_IT'])

    def is_spell_language_available(self, language: str) -> bool:
        return language in self.get_available_spell_languages()

    def get_spell_check_show_language_menu(self) -> bool:
        return self.get('spell_check_show_language_menu', True)

    def set_spell_check_show_language_menu(self, show: bool) -> None:
        self.set('spell_check_show_language_menu', show)

    def get_personal_dictionary_path(self) -> str:
        return self.get('spell_check_personal_dictionary', str(self.config_dir / 'personal_dict.txt'))

    def set_available_spell_languages(self, languages: List[str]) -> None:
        self.set('spell_check_available_languages', languages)

    # AI assistant helpers
    def get_ai_assistant_enabled(self) -> bool:
        return self.get('ai_assistant_enabled', False)

    def set_ai_assistant_enabled(self, enabled: bool) -> None:
        self.set('ai_assistant_enabled', enabled)

    def get_ai_assistant_provider(self) -> str:
        return self.get('ai_assistant_provider', 'gemini')

    def set_ai_assistant_provider(self, provider: str) -> None:
        self.set('ai_assistant_provider', provider)

    def get_ai_assistant_model(self) -> str:
        return self.get('ai_assistant_model', '')

    def set_ai_assistant_model(self, model: str) -> None:
        self.set('ai_assistant_model', model)

    def get_ai_assistant_api_key(self) -> str:
        return self.get('ai_assistant_api_key', '')

    def set_ai_assistant_api_key(self, api_key: str) -> None:
        self.set('ai_assistant_api_key', api_key)

    def get_openrouter_site_url(self) -> str:
        return self.get('ai_openrouter_site_url', '')

    def set_openrouter_site_url(self, url: str) -> None:
        self.set('ai_openrouter_site_url', url)

    def get_openrouter_site_name(self) -> str:
        return self.get('ai_openrouter_site_name', '')

    def set_openrouter_site_name(self, name: str) -> None:
        self.set('ai_openrouter_site_name', name)

    # Color scheme helpers
    def get_color_scheme_enabled(self) -> bool:
        return self.get('color_scheme_enabled', False)

    def set_color_scheme_enabled(self, enabled: bool) -> None:
        self.set('color_scheme_enabled', enabled)

    def get_color_bg(self) -> str:
        return self.get('color_bg', '#ffffff')

    def set_color_bg(self, color: str) -> None:
        self.set('color_bg', color)

    def get_color_font(self) -> str:
        return self.get('color_font', '#2e2e2e')

    def set_color_font(self, color: str) -> None:
        self.set('color_font', color)

    def get_color_accent(self) -> str:
        return self.get('color_accent', '#3584e4')

    def set_color_accent(self, color: str) -> None:
        self.set('color_accent', color)