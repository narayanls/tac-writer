"""
TAC Utility Helpers
General utility functions for file operations, validation, and common tasks
"""

import os
import re
import mimetypes
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime


class FileHelper:
    """Helper functions for file operations"""
    
    @staticmethod
    def ensure_extension(filename: str, extension: str) -> str:
        """Ensure filename has the correct extension"""
        if not extension.startswith('.'):
            extension = '.' + extension
        
        if not filename.lower().endswith(extension.lower()):
            return filename + extension
        return filename
    
    @staticmethod
    def get_safe_filename(filename: str) -> str:
        """Convert filename to safe version (remove invalid characters)"""
        # Remove invalid characters for filenames
        safe_chars = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Remove multiple spaces and underscores
        safe_chars = re.sub(r'[ _]+', '_', safe_chars)
        
        # Remove leading/trailing spaces and underscores
        safe_chars = safe_chars.strip(' _')
        
        # Ensure not empty
        if not safe_chars:
            safe_chars = "untitled"
        
        return safe_chars
    
    @staticmethod
    def get_file_size_human(file_path: Path) -> str:
        """Get human-readable file size"""
        try:
            size = file_path.stat().st_size
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.1f} {unit}"
                size /= 1024.0
            return f"{size:.1f} TB"
        except:
            return "Unknown"
    
    @staticmethod
    def get_mime_type(file_path: Path) -> str:
        """Get MIME type of file"""
        mime_type, _ = mimetypes.guess_type(str(file_path))
        return mime_type or 'application/octet-stream'
    
    @staticmethod
    def create_backup_filename(original_path: Path) -> Path:
        """Create backup filename with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{original_path.stem}_{timestamp}_backup{original_path.suffix}"
        return original_path.parent / backup_name
    
    @staticmethod
    def find_available_filename(file_path: Path) -> Path:
        """Find available filename if file already exists"""
        if not file_path.exists():
            return file_path
        
        counter = 1
        while True:
            new_name = f"{file_path.stem}_{counter}{file_path.suffix}"
            new_path = file_path.parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1


class TextHelper:
    """Helper functions for text processing"""
    
    @staticmethod
    def count_words(text: str) -> int:
        """Count words in text"""
        if not text:
            return 0
        return len(text.split())
    
    @staticmethod
    def count_characters(text: str, include_spaces: bool = True) -> int:
        """Count characters in text"""
        if not text:
            return 0
        return len(text) if include_spaces else len(text.replace(' ', ''))
    
    @staticmethod
    def count_sentences(text: str) -> int:
        """Count sentences in text (basic implementation)"""
        if not text:
            return 0
        # Simple sentence counting based on sentence-ending punctuation
        sentences = re.split(r'[.!?]+', text)
        return len([s for s in sentences if s.strip()])
    
    @staticmethod
    def count_paragraphs(text: str) -> int:
        """Count paragraphs in text"""
        if not text:
            return 0
        paragraphs = text.split('\n\n')
        return len([p for p in paragraphs if p.strip()])
    
    @staticmethod
    def extract_first_sentence(text: str) -> str:
        """Extract first sentence from text"""
        if not text:
            return ""
        
        match = re.search(r'^[^.!?]*[.!?]', text.strip())
        if match:
            return match.group(0).strip()
        
        # If no sentence ending found, return first 100 characters
        return text.strip()[:100] + ('...' if len(text.strip()) > 100 else '')
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 100, suffix: str = '...') -> str:
        """Truncate text to specified length"""
        if not text or len(text) <= max_length:
            return text
        
        # Try to break at word boundary
        if ' ' in text[:max_length]:
            truncated = text[:max_length].rsplit(' ', 1)[0]
        else:
            truncated = text[:max_length]
        
        return truncated + suffix
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean text by removing extra whitespace and normalizing"""
        if not text:
            return ""
        
        # Replace multiple spaces with single space
        cleaned = re.sub(r'\s+', ' ', text)
        
        # Remove leading/trailing whitespace
        cleaned = cleaned.strip()
        
        return cleaned
    
    @staticmethod
    def format_reading_time(word_count: int, words_per_minute: int = 200) -> str:
        """Calculate estimated reading time"""
        if word_count == 0:
            return "0 minutes"
        
        minutes = word_count / words_per_minute
        
        if minutes < 1:
            return "< 1 minute"
        elif minutes < 60:
            return f"{int(minutes)} minute{'s' if int(minutes) != 1 else ''}"
        else:
            hours = int(minutes // 60)
            mins = int(minutes % 60)
            return f"{hours}h {mins}m"


class ValidationHelper:
    """Helper functions for validation"""
    
    @staticmethod
    def is_valid_filename(filename: str) -> bool:
        """Check if filename is valid"""
        if not filename or filename.strip() == '':
            return False
        
        # Check for invalid characters
        invalid_chars = '<>:"/\\|?*'
        if any(char in filename for char in invalid_chars):
            return False
        
        # Check for reserved names (Windows)
        reserved_names = [
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        ]
        
        name_without_ext = Path(filename).stem.upper()
        if name_without_ext in reserved_names:
            return False
        
        return True
    
    @staticmethod
    def is_valid_project_name(name: str) -> Tuple[bool, str]:
        """Validate project name and return (is_valid, error_message)"""
        if not name or name.strip() == '':
            return False, "Project name cannot be empty"
        
        name = name.strip()
        
        if len(name) < 2:
            return False, "Project name must be at least 2 characters long"
        
        if len(name) > 100:
            return False, "Project name cannot exceed 100 characters"
        
        if not ValidationHelper.is_valid_filename(name):
            return False, "Project name contains invalid characters"
        
        return True, ""
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Basic email validation"""
        if not email:
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def validate_path(path: str) -> Tuple[bool, str]:
        """Validate file/directory path"""
        if not path:
            return False, "Path cannot be empty"
        
        try:
            path_obj = Path(path)
            
            # Check if parent directory exists (for file paths)
            if not path_obj.parent.exists():
                return False, "Parent directory does not exist"
            
            # Check if path is too long (Windows has 260 char limit)
            if len(str(path_obj.resolve())) > 250:
                return False, "Path is too long"
            
            return True, ""
            
        except Exception as e:
            return False, f"Invalid path: {str(e)}"


class FormatHelper:
    """Helper functions for formatting"""
    
    @staticmethod
    def format_datetime(dt: datetime, format_type: str = 'default') -> str:
        """Format datetime for display"""
        if format_type == 'short':
            return dt.strftime('%m/%d/%Y')
        elif format_type == 'long':
            return dt.strftime('%B %d, %Y at %I:%M %p')
        elif format_type == 'time':
            return dt.strftime('%I:%M %p')
        elif format_type == 'iso':
            return dt.isoformat()
        else:  # default
            return dt.strftime('%Y-%m-%d %H:%M')
    
    @staticmethod
    def format_file_size(size_bytes: int) -> str:
        """Format file size in human-readable format"""
        if size_bytes == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        
        return f"{size_bytes:.1f} PB"
    
    @staticmethod
    def format_statistics(stats: Dict[str, Any]) -> Dict[str, str]:
        """Format statistics for display"""
        formatted = {}
        
        for key, value in stats.items():
            if key.endswith('_count'):
                formatted[key] = f"{value:,}"
            elif key == 'total_words':
                formatted[key] = f"{value:,} words"
            elif key == 'total_characters':
                formatted[key] = f"{value:,} characters"
            elif isinstance(value, dict):
                # Handle nested dictionaries
                formatted[key] = {k: str(v) for k, v in value.items()}
            else:
                formatted[key] = str(value)
        
        return formatted


class DebugHelper:
    """Helper functions for debugging and logging"""
    
    @staticmethod
    def print_object_info(obj: Any, name: str = "Object") -> None:
        """Print detailed information about an object"""
        print(f"\n=== {name} Info ===")
        print(f"Type: {type(obj).__name__}")
        print(f"Module: {type(obj).__module__}")
        
        if hasattr(obj, '__dict__'):
            print("Attributes:")
            for attr, value in obj.__dict__.items():
                print(f"  {attr}: {type(value).__name__} = {repr(value)[:100]}")
        
        print("Methods:")
        methods = [method for method in dir(obj) if callable(getattr(obj, method)) and not method.startswith('_')]
        for method in methods[:10]:  # Limit to first 10 methods
            print(f"  {method}()")
        
        if len(methods) > 10:
            print(f"  ... and {len(methods) - 10} more methods")
        
        print("=" * (len(name) + 10))
    
    @staticmethod
    def log_performance(func_name: str, start_time: datetime, end_time: datetime) -> None:
        """Log performance information"""
        duration = (end_time - start_time).total_seconds()
        print(f"Performance: {func_name} took {duration:.3f} seconds")