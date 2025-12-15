"""
TAC Core Services
Business logic and data services for the TAC application
"""

import json
import shutil
import zipfile
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from .config import Config
from .models import Project, Paragraph, ParagraphType
from utils.helpers import FileHelper
from utils.i18n import _

# ODT export dependencies
try:
    from xml.etree import ElementTree as ET
    ODT_AVAILABLE = True
except ImportError:
    ODT_AVAILABLE = False

# PDF export dependencies
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph as RLParagraph, Spacer, Image as RLImage
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# Image processing dependencies
try:
    from PIL import Image as PILImage
    import base64
    IMAGE_PROCESSING_AVAILABLE = True
except ImportError:
    IMAGE_PROCESSING_AVAILABLE = False


class ProjectManager:
    """Manages project operations using a SQLite database"""
    
    def __init__(self):
        self.config = Config()
        self.db_path = self.config.database_path
        self._migration_lock = threading.Lock()
        self._init_db()
        self._run_migration_if_needed()
        
        print(_("ProjectManager initialized with database: {}").format(self.db_path))

    def _get_db_connection(self):
        """Get a new database connection with optimized settings"""
        try:
            conn = sqlite3.connect(
                self.db_path, 
                timeout=30.0,
                check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            return conn
        except sqlite3.Error as e:
            print(_("Database connection error: {}").format(e))
            raise
    
    def _project_exists(self, project_id: str) -> bool:
        """Check if project exists in database"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM projects WHERE id = ? LIMIT 1", (project_id,))
                return cursor.fetchone() is not None
        except sqlite3.Error as e:
            print(_("Error checking project existence: {}").format(e))
            return False

    def _validate_json_data(self, data: Dict[str, Any]) -> bool:
        """Validate that project data has required fields"""
        required_fields = ['id', 'name', 'created_at', 'modified_at']
        
        for field in required_fields:
            if field not in data:
                print(_("Invalid project data: missing field '{}'").format(field))
                return False
        
        # Validate paragraphs if present
        if 'paragraphs' in data:
            for i, para_data in enumerate(data['paragraphs']):
                required_para_fields = ['id', 'type', 'content', 'order']
                for field in required_para_fields:
                    if field not in para_data:
                        print(_("Invalid paragraph {}: missing field '{}'").format(i, field))
                        return False
        
        return True

    def _create_migration_backup(self, json_files: List[Path]) -> Optional[Path]:
        """Create a backup of JSON files before migration"""
        try:
            backup_dir = self.config.data_dir / 'migration_backup'
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"projects_backup_{timestamp}.zip"
            
            with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                for json_file in json_files:
                    zf.write(json_file, json_file.name)
            
            print(_("Created migration backup: {}").format(backup_file))
            return backup_file
            
        except (OSError, zipfile.BadZipFile) as e:
            print(_("Failed to create migration backup: {}").format(e))
            return None

    def _run_migration_if_needed(self):
        """Check for old JSON files and migrate them to SQLite with full transaction support"""
        with self._migration_lock:
            old_projects_dir = self.config.data_dir / 'projects'
            if not old_projects_dir.exists():
                return

            json_files = list(old_projects_dir.glob("*.json"))
            if not json_files:
                return

            print(_("Found {} old JSON projects. Starting migration...").format(len(json_files)))
            
            # Create backup first
            backup_file = self._create_migration_backup(json_files)
            if not backup_file:
                print(_("Migration aborted: Could not create backup"))
                return
            
            # Load and validate all projects before migration
            projects_to_migrate = []
            invalid_files = []
            
            for project_file in json_files:
                try:
                    with open(project_file, 'r', encoding='utf-8') as f:
                        project_data = json.load(f)
                    
                    if not self._validate_json_data(project_data):
                        invalid_files.append(project_file)
                        continue
                        
                    project = Project.from_dict(project_data)
                    projects_to_migrate.append((project, project_file))
                    
                except (json.JSONDecodeError, OSError) as e:
                    print(_("Error loading {}: {}").format(project_file.name, e))
                    invalid_files.append(project_file)
            
            if invalid_files:
                print(_("Warning: {} files have validation errors and will be skipped").format(len(invalid_files)))
            
            if not projects_to_migrate:
                print(_("No valid projects to migrate"))
                return
            
            # Perform migration in single transaction
            migrated_count = 0
            failed_projects = []
            
            try:
                with self._get_db_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Begin transaction
                    cursor.execute("BEGIN IMMEDIATE;")
                    
                    try:
                        for project, project_file in projects_to_migrate:
                            if self._save_project_to_db(cursor, project):
                                migrated_count += 1
                            else:
                                failed_projects.append(project_file)
                        
                        if failed_projects:
                            raise RuntimeError(_("Failed to migrate {} projects").format(len(failed_projects)))
                        
                        # Commit transaction
                        conn.commit()
                        print(_("Migration transaction committed successfully"))
                        
                        # Mark files as migrated only after successful DB commit
                        for project, project_file in projects_to_migrate:
                            try:
                                migrated_file = project_file.with_suffix('.json.migrated')
                                project_file.rename(migrated_file)
                            except OSError as e:
                                print(_("Warning: Could not rename {}: {}").format(project_file.name, e))
                        
                    except Exception as e:
                        # Rollback transaction
                        conn.rollback()
                        print(_("Migration failed, transaction rolled back: {}").format(e))
                        return
                        
            except sqlite3.Error as e:
                print(_("Migration failed with database error: {}").format(e))
                return
            
            print(_("Migration complete. {} projects successfully migrated.").format(migrated_count))
            
            # Run database maintenance after migration
            self._vacuum_database()

    def _save_project_to_db(self, cursor: sqlite3.Cursor, project: Project) -> bool:
        """Save project using provided cursor (for transaction support)"""
        try:
            # Validate JSON serialization
            try:
                metadata_json = json.dumps(project.metadata)
                formatting_json = json.dumps(project.document_formatting)
            except (TypeError, ValueError) as e:
                print(_("JSON serialization error for project {}: {}").format(project.name, e))
                return False
            
            cursor.execute("""
                INSERT INTO projects (id, name, created_at, modified_at, metadata, document_formatting)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    modified_at=excluded.modified_at,
                    metadata=excluded.metadata,
                    document_formatting=excluded.document_formatting;
            """, (
                project.id,
                project.name,
                project.created_at.isoformat(),
                datetime.now().isoformat(),
                metadata_json,
                formatting_json
            ))

            # Delete existing paragraphs for this project
            cursor.execute("DELETE FROM paragraphs WHERE project_id = ?", (project.id,))

            # Insert paragraphs
            paragraphs_data = []
            for p in project.paragraphs:
                try:
                    formatting_json = json.dumps(p.formatting)
                    footnotes_json = json.dumps(p.footnotes if hasattr(p, 'footnotes') else [])
                except (TypeError, ValueError) as e:
                    print(_("JSON serialization error for paragraph {}: {}").format(p.id, e))
                    return False
                    
                paragraphs_data.append((
                    p.id, project.id, p.type.value, p.content,
                    p.created_at.isoformat(), p.modified_at.isoformat(),
                    p.order, formatting_json, footnotes_json
                ))

            if paragraphs_data:
                cursor.executemany("""
                    INSERT INTO paragraphs (id, project_id, type, content, created_at, modified_at, "order", formatting, footnotes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, paragraphs_data)
            
            return True
            
        except sqlite3.Error as e:
            print(_("Database error saving project {}: {}").format(project.name, e))
            return False

    def save_project(self, project: Project, is_migration: bool = False) -> bool:
        """Save project to the database (UPSERT)"""
        if is_migration:
            return True
        
        # Create database backup before saving
        self._create_database_backup()
            
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("BEGIN IMMEDIATE;")
                
                try:
                    success = self._save_project_to_db(cursor, project)
                    if success:
                        conn.commit()
                        print(_("Saved project to database: {}").format(project.name))
                        return True
                    else:
                        conn.rollback()
                        print(_("Failed to save project to database: {}").format(project.name))
                        return False
                except sqlite3.Error as db_error:
                    conn.rollback()
                    print(_("Database error saving project '{}': {}").format(project.name, db_error))
                    raise
                except Exception as e:
                    conn.rollback()
                    print(_("Unexpected error saving project '{}': {}: {}").format(
                        project.name, type(e).__name__, e))
                    raise
                    
        except sqlite3.Error as db_error:
            print(_("Database connection error for project '{}': {}").format(project.name, db_error))
            return False
        except Exception as e:
            print(_("Unexpected error in save_project for '{}': {}: {}").format(
                project.name, type(e).__name__, e))
            import traceback
            traceback.print_exc()
            return False
        
    def _create_database_backup(self) -> bool:
        """Create backup of database file maintaining only 3 most recent backups"""
        if not self.config.get('backup_files', False):
            return True  # Backup disabled, consider success
        
        try:
            # Ensure database file exists
            if not self.db_path.exists():
                return False
            
            # Detect user's Documents directory (language-aware)
            documents_dir = self._get_documents_directory()
            backup_dir = documents_dir / "TAC Projects" / "database_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_{timestamp}.db"
            backup_path = backup_dir / backup_filename
            
            # Copy database file
            shutil.copy2(self.db_path, backup_path)
            
            # Clean old backups - keep only 3 most recent
            self._cleanup_old_backups(backup_dir)
            
            print(_("Database backup created: {}").format(backup_path))
            return True
            
        except (OSError, shutil.Error) as e:
            print(_("Warning: Database backup failed: {}").format(e))
            return False

    def _cleanup_old_backups(self, backup_dir: Path, max_backups: int = 3):
        """Keep only the most recent backups"""
        try:
            backup_files = list(backup_dir.glob("backup_*.db"))
            
            # Sort by modification time (most recent first)
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Remove files beyond the limit
            for old_backup in backup_files[max_backups:]:
                old_backup.unlink()
                print(_("Removed old backup: {}").format(old_backup))
                
        except OSError as e:
            print(_("Warning: Cleanup of old backups failed: {}").format(e))
            
    def _get_documents_directory(self) -> Path:
        """Get user's Documents directory in a language-aware way"""
        home = Path.home()
        
        # Try XDG user dirs first (Linux)
        try:
            import subprocess
            result = subprocess.run(['xdg-user-dir', 'DOCUMENTS'], 
                                capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                documents_path = Path(result.stdout.strip())
                if documents_path.exists():
                    return documents_path
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
            pass
        
        # Try common localized directory names
        possible_names = [
            'Documents', 'Documentos', 'Dokumente', 'Documenti',
            'Документы', 'Документи', 'Dokumenty', 'Dokumenter',
            'Έγγραφα', 'Dokumendid', 'Asiakirjat', 'מסמכים',
            'Dokumenti', 'Dokumentumok', 'Skjöl', 'ドキュメント',
            '문서', 'Documenten', 'Documente', 'Dokument',
            'Belgeler', '文档',
        ]
        
        for name in possible_names:
            candidate = home / name
            if candidate.exists() and candidate.is_dir():
                return candidate
        
        # Fallback: use data directory
        return self.config.data_dir

    def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects from the database with optimized statistics"""
        projects_info = []
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get all projects first
                cursor.execute("""
                    SELECT p.id, p.name, p.created_at, p.modified_at
                    FROM projects p
                    ORDER BY p.modified_at DESC;
                """)
                projects = cursor.fetchall()
                
                for project_row in projects:
                    project_id = project_row['id']
                    
                    # Get paragraphs for this project in correct order
                    cursor.execute("""
                        SELECT type, content FROM paragraphs 
                        WHERE project_id = ? ORDER BY "order" ASC
                    """, (project_id,))
                    paragraphs_rows = cursor.fetchall()
                    
                    # Convert database rows to lightweight paragraph objects for calculation
                    paragraph_data = []
                    for p_row in paragraphs_rows:
                        # Create a simple object with the attributes needed for statistics
                        class LightParagraph:
                            def __init__(self, p_type, content):
                                try:
                                    self.type = ParagraphType(p_type)
                                except ValueError:
                                    # Handle old 'argument_quote' -> 'quote' migration
                                    if p_type == 'argument_quote':
                                        self.type = ParagraphType.QUOTE
                                    else:
                                        # Skip invalid types
                                        self.type = None
                                self.content = content or ''
                        
                        light_p = LightParagraph(p_row['type'], p_row['content'])
                        if light_p.type is not None:
                            paragraph_data.append(light_p)
                    
                    # Use consolidated static methods from Project class
                    total_words = sum(
                        Project._calculate_word_count(p.content) 
                        for p in paragraph_data
                    )
                    total_paragraphs = Project._count_logical_paragraphs(paragraph_data)
                    
                    stats = {
                        'total_paragraphs': total_paragraphs,
                        'total_words': total_words,
                    }
                    
                    projects_info.append({
                        'id': project_row['id'],
                        'name': project_row['name'],
                        'created_at': project_row['created_at'],
                        'modified_at': project_row['modified_at'],
                        'statistics': stats,
                        'file_path': None
                    })
                    
        except sqlite3.Error as e:
            print(_("Database error listing projects: {}").format(e))
        except Exception as e:
            print(_("Unexpected error listing projects: {}: {}").format(type(e).__name__, e))
        
        return projects_info

    def _vacuum_database(self):
        """Perform database maintenance"""
        try:
            with self._get_db_connection() as conn:
                conn.execute("VACUUM;")
                conn.execute("ANALYZE;")
                print(_("Database maintenance completed"))
        except sqlite3.Error as e:
            print(_("Database maintenance failed: {}").format(e))

    def get_database_info(self) -> Dict[str, Any]:
        """Get database statistics and health information"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get table sizes
                cursor.execute("SELECT COUNT(*) as project_count FROM projects;")
                project_count = cursor.fetchone()['project_count']
                
                cursor.execute("SELECT COUNT(*) as paragraph_count FROM paragraphs;")
                paragraph_count = cursor.fetchone()['paragraph_count']
                
                # Get database file size
                db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
                
                return {
                    'database_path': str(self.db_path),
                    'database_size_bytes': db_size,
                    'project_count': project_count,
                    'paragraph_count': paragraph_count,
                    'health_status': 'healthy'
                }
                
        except sqlite3.Error as e:
            return {
                'database_path': str(self.db_path),
                'health_status': _('error: {}').format(e),
                'project_count': 0,
                'paragraph_count': 0
            }
        except Exception as e:
            return {
                'database_path': str(self.db_path),
                'health_status': _('unexpected error: {}').format(e),
                'project_count': 0,
                'paragraph_count': 0
            }
    
    def _init_db(self):
        """Initialize the database and create tables if they don't exist"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS projects (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        modified_at TEXT NOT NULL,
                        metadata TEXT,
                        document_formatting TEXT
                    );
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS paragraphs (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        type TEXT NOT NULL,
                        content TEXT,
                        created_at TEXT NOT NULL,
                        modified_at TEXT NOT NULL,
                        "order" INTEGER NOT NULL,
                        formatting TEXT,
                        footnotes TEXT,
                        FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
                    );
                """)
                
                # Add footnotes column if it doesn't exist (migration)
                try:
                    cursor.execute("ALTER TABLE paragraphs ADD COLUMN footnotes TEXT")
                except sqlite3.OperationalError:
                    # Column already exists
                    pass
                    
                conn.commit()
        except sqlite3.Error as e:
            print(_("Database initialization error: {}").format(e))
            raise

    def create_project(self, name: str, template: str = "academic_essay") -> Project:
        """Create a new project"""
        try:
            project = Project(name)
            
            if template == "academic_essay":
                pass
            
            if self.save_project(project):
                print(_("Created project: {} ({})").format(project.name, project.id))
                return project
            else:
                raise RuntimeError(_("Failed to save new project to database"))
        except Exception as e:
            print(_("Error creating project: {}: {}").format(type(e).__name__, e))
            raise

    def load_project(self, project_id: str) -> Optional[Project]:
        """Load project by ID from the database"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
                project_row = cursor.fetchone()
                
                if not project_row:
                    print(_("Project with ID {} not found in database.").format(project_id))
                    return None
                
                project_data = dict(project_row)
                project_data['metadata'] = json.loads(project_data['metadata'])
                project_data['document_formatting'] = json.loads(project_data['document_formatting'])
                
                cursor.execute("SELECT * FROM paragraphs WHERE project_id = ? ORDER BY \"order\" ASC", (project_id,))
                paragraphs_rows = cursor.fetchall()

                paragraphs_data = []
                for p_row in paragraphs_rows:
                    p_data = dict(p_row)
                    p_data['formatting'] = json.loads(p_data['formatting'])
                    
                    # Handle footnotes (with backward compatibility)
                    if p_data.get('footnotes'):
                        try:
                            p_data['footnotes'] = json.loads(p_data['footnotes'])
                        except (json.JSONDecodeError, TypeError):
                            p_data['footnotes'] = []
                    else:
                        p_data['footnotes'] = []
                        
                    paragraphs_data.append(p_data)
                
                project_data['paragraphs'] = paragraphs_data
                
                project = Project.from_dict(project_data)
                print(_("Loaded project from database: {}").format(project.name))
                return project
                
        except sqlite3.Error as e:
            print(_("Database error loading project: {}").format(e))
            return None
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(_("Data error loading project: {}: {}").format(type(e).__name__, e))
            return None
        except Exception as e:
            print(_("Unexpected error loading project: {}: {}").format(type(e).__name__, e))
            import traceback
            traceback.print_exc()
            return None

    def delete_project(self, project_id: str) -> bool:
        """Delete project from the database"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
                conn.commit()
                
                print(_("Deleted project from database: {}").format(project_id))
                return True
        except sqlite3.Error as e:
            print(_("Database error deleting project: {}").format(e))
            return False

    def create_manual_backup(self) -> Optional[Path]:
        """Create a manual backup of the database"""
        try:
            if not self.db_path.exists():
                return None
                
            # Get backup directory
            documents_dir = self._get_documents_directory()
            backup_dir = documents_dir / "TAC Projects" / "database_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"manual_backup_{timestamp}.db"
            backup_path = backup_dir / backup_filename
            
            # Copy database file
            shutil.copy2(self.db_path, backup_path)
            
            # Clean old backups - keep only 10 most recent
            self._cleanup_old_backups(backup_dir, max_backups=10)
            
            print(_("Manual backup created: {}").format(backup_path))
            return backup_path
            
        except (OSError, shutil.Error) as e:
            print(_("Error creating manual backup: {}").format(e))
            return None

    def list_available_backups(self) -> List[Dict[str, Any]]:
        """List available backup files with metadata"""
        backups = []
        try:
            documents_dir = self._get_documents_directory()
            backup_dir = documents_dir / "TAC Projects" / "database_backups"
            
            if not backup_dir.exists():
                return backups
                
            # Find all backup files
            backup_files = list(backup_dir.glob("*.db"))
            
            for backup_file in backup_files:
                try:
                    # Get file stats
                    stat = backup_file.stat()
                    
                    # Try to get project count from backup
                    project_count = 0
                    try:
                        with sqlite3.connect(backup_file) as conn:
                            cursor = conn.cursor()
                            cursor.execute("SELECT COUNT(*) FROM projects")
                            project_count = cursor.fetchone()[0]
                    except sqlite3.Error:
                        pass
                    
                    backups.append({
                        'path': backup_file,
                        'name': backup_file.name,
                        'size': stat.st_size,
                        'created_at': datetime.fromtimestamp(stat.st_mtime),
                        'project_count': project_count,
                        'is_valid': self._validate_backup_file(backup_file)
                    })
                except (OSError, ValueError) as e:
                    print(_("Error reading backup file {}: {}").format(backup_file, e))
                    continue
            
            # Sort by creation date (newest first)
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            
        except OSError as e:
            print(_("Error listing backups: {}").format(e))
            
        return backups

    def _validate_backup_file(self, backup_path: Path) -> bool:
        """Validate if backup file is a valid TAC database"""
        try:
            with sqlite3.connect(backup_path) as conn:
                cursor = conn.cursor()
                
                # Check if required tables exist
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name IN ('projects', 'paragraphs')
                """)
                tables = cursor.fetchall()
                
                if len(tables) != 2:
                    return False
                
                # Check table structure
                cursor.execute("PRAGMA table_info(projects)")
                project_columns = [row[1] for row in cursor.fetchall()]
                required_project_columns = ['id', 'name', 'created_at', 'modified_at']
                
                for col in required_project_columns:
                    if col not in project_columns:
                        return False
                
                return True
                
        except sqlite3.Error as e:
            print(_("Backup validation error: {}").format(e))
            return False

    def import_database(self, backup_path: Path) -> bool:
        """Import database from backup file"""
        try:
            # Validate backup file
            if not self._validate_backup_file(backup_path):
                print(_("Invalid backup file"))
                return False
            
            # Create backup of current database
            current_backup_path = None
            if self.db_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                current_backup_path = self.db_path.with_suffix(f'.backup_{timestamp}.db')
                shutil.copy2(self.db_path, current_backup_path)
                print(_("Current database backed up to: {}").format(current_backup_path))
            
            try:
                # Replace current database
                shutil.copy2(backup_path, self.db_path)
                
                # Test the imported database
                with self._get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM projects")
                    project_count = cursor.fetchone()[0]
                    print(_("Successfully imported database with {} projects").format(project_count))
                
                return True
                
            except (shutil.Error, sqlite3.Error) as e:
                # Restore backup if import failed
                if current_backup_path and current_backup_path.exists():
                    shutil.copy2(current_backup_path, self.db_path)
                    print(_("Import failed, restored previous database"))
                raise e
                
        except Exception as e:
            print(_("Error importing database: {}: {}").format(type(e).__name__, e))
            import traceback
            traceback.print_exc()
            return False

    def delete_backup(self, backup_path: Path) -> bool:
        """Delete a backup file"""
        try:
            if backup_path.exists():
                backup_path.unlink()
                print(_("Deleted backup: {}").format(backup_path))
                return True
            return False
        except OSError as e:
            print(_("Error deleting backup: {}").format(e))
            return False

    @property
    def projects_dir(self) -> Path:
        """Get projects directory for compatibility"""
        return self.config.data_dir / 'projects'


class ExportService:
    """Handles document export operations"""
    
    def __init__(self):
        self.odt_available = ODT_AVAILABLE
        self.pdf_available = PDF_AVAILABLE
        
        if not self.odt_available:
            print(_("Warning: ODT export not available (missing xml dependencies)"))
        if not self.pdf_available:
            print(_("Warning: PDF export not available (missing reportlab)"))
    
    def _collect_footnotes(self, project: Project) -> tuple:
        """
        Collect all unique footnotes from project and create mapping.
        
        Returns:
            tuple: (all_footnotes list, footnote_map dict)
        """
        all_footnotes = []
        footnote_map = {}
        
        for paragraph in project.paragraphs:
            if hasattr(paragraph, 'footnotes') and paragraph.footnotes:
                paragraph_footnotes = []
                for footnote_text in paragraph.footnotes:
                    # Check if footnote already exists
                    existing_num = None
                    for i, existing_footnote in enumerate(all_footnotes):
                        if footnote_text == existing_footnote:
                            existing_num = i + 1
                            break
                    
                    if existing_num is None:
                        # New footnote
                        footnote_num = len(all_footnotes) + 1
                        all_footnotes.append(footnote_text)
                        paragraph_footnotes.append(footnote_num)
                    else:
                        # Reuse existing footnote
                        paragraph_footnotes.append(existing_num)
                
                footnote_map[paragraph.id] = paragraph_footnotes
        
        return all_footnotes, footnote_map
    
    def _group_paragraphs(self, project: Project, footnote_map: dict) -> list:
        """
        Group paragraphs following TAC methodology.
        
        Returns:
            list: List of grouped paragraph dictionaries with structure:
                {
                    'type': 'title1' | 'title2' | 'quote' | 'content',
                    'content': str,
                    'indent': bool (for content type only)
                }
        """
        grouped = []
        current_paragraph_content = []
        paragraph_starts_with_introduction = False
        last_was_quote = False
        
        for i, paragraph in enumerate(project.paragraphs):
            content = paragraph.content.strip()
            
            if paragraph.type == ParagraphType.TITLE_1:
                # Write accumulated content first
                if current_paragraph_content:
                    combined = " ".join(current_paragraph_content)
                    grouped.append({
                        'type': 'content',
                        'content': combined,
                        'indent': paragraph_starts_with_introduction
                    })
                    current_paragraph_content = []
                    paragraph_starts_with_introduction = False
                
                grouped.append({'type': 'title1', 'content': content})
                last_was_quote = False
            
            elif paragraph.type == ParagraphType.TITLE_2:
                # Write accumulated content first
                if current_paragraph_content:
                    combined = " ".join(current_paragraph_content)
                    grouped.append({
                        'type': 'content',
                        'content': combined,
                        'indent': paragraph_starts_with_introduction
                    })
                    current_paragraph_content = []
                    paragraph_starts_with_introduction = False
                
                grouped.append({'type': 'title2', 'content': content})
                last_was_quote = False
            
            elif paragraph.type == ParagraphType.QUOTE:
                # Write accumulated content first
                if current_paragraph_content:
                    combined = " ".join(current_paragraph_content)
                    grouped.append({
                        'type': 'content',
                        'content': combined,
                        'indent': paragraph_starts_with_introduction
                    })
                    current_paragraph_content = []
                    paragraph_starts_with_introduction = False
                
                grouped.append({'type': 'quote', 'content': content})
                last_was_quote = True
            
            elif paragraph.type == ParagraphType.EPIGRAPH: # New block
                # Write accumulated content first
                if current_paragraph_content:
                    combined = " ".join(current_paragraph_content)
                    grouped.append({
                        'type': 'content',
                        'content': combined,
                        'indent': paragraph_starts_with_introduction
                    })
                    current_paragraph_content = []
                    paragraph_starts_with_introduction = False
                
                # Add epigraph with its own type for special formatting
                grouped.append({'type': 'epigraph', 'content': content})
                last_was_quote = True # Treat it like a quote to start a new paragraph after
            
            elif paragraph.type == ParagraphType.IMAGE:
                # Write accumulated content first
                if current_paragraph_content:
                    combined = " ".join(current_paragraph_content)
                    grouped.append({
                        'type': 'content',
                        'content': combined,
                        'indent': paragraph_starts_with_introduction
                    })
                    current_paragraph_content = []
                    paragraph_starts_with_introduction = False
                
                # Add image to grouped list
                img_metadata = paragraph.get_image_metadata()
                if img_metadata:
                    grouped.append({'type': 'image', 'metadata': img_metadata})
                last_was_quote = False
            
            elif paragraph.type in [ParagraphType.INTRODUCTION, ParagraphType.ARGUMENT, ParagraphType.CONCLUSION, ParagraphType.ARGUMENT_RESUMPTION]:
                # Determine if should start new paragraph
                should_start_new = (
                    paragraph.type == ParagraphType.INTRODUCTION or
                    paragraph.type == ParagraphType.ARGUMENT_RESUMPTION or
                    last_was_quote or
                    not current_paragraph_content
                )
                
                if should_start_new and current_paragraph_content:
                    combined = " ".join(current_paragraph_content)
                    grouped.append({
                        'type': 'content',
                        'content': combined,
                        'indent': paragraph_starts_with_introduction
                    })
                    current_paragraph_content = []
                    paragraph_starts_with_introduction = False
                
                # Determine paragraph style
                if not current_paragraph_content:
                    if paragraph.type == ParagraphType.INTRODUCTION or paragraph.type == ParagraphType.ARGUMENT_RESUMPTION:
                        paragraph_starts_with_introduction = True
                    elif last_was_quote:
                        paragraph_starts_with_introduction = False
                
                # Add footnote references
                if paragraph.id in footnote_map:
                    for footnote_num in footnote_map[paragraph.id]:
                        content += f"^{footnote_num}"
                
                current_paragraph_content.append(content)
                
                # Check if next paragraph starts new group
                next_is_new = False
                if i + 1 < len(project.paragraphs):
                    next_p = project.paragraphs[i + 1]
                    if next_p.type in [ParagraphType.INTRODUCTION, ParagraphType.TITLE_1, 
                                      ParagraphType.TITLE_2, ParagraphType.QUOTE]:
                        next_is_new = True
                else:
                    next_is_new = True
                
                if next_is_new:
                    combined = " ".join(current_paragraph_content)
                    grouped.append({
                        'type': 'content',
                        'content': combined,
                        'indent': paragraph_starts_with_introduction
                    })
                    current_paragraph_content = []
                    paragraph_starts_with_introduction = False
                
                last_was_quote = False
        
        # Write any remaining content
        if current_paragraph_content:
            combined = " ".join(current_paragraph_content)
            grouped.append({
                'type': 'content',
                'content': combined,
                'indent': paragraph_starts_with_introduction
            })
        
        return grouped

    def get_available_formats(self) -> List[str]:
        """Get list of available export formats"""
        formats = ['txt']
        
        if self.odt_available:
            formats.append('odt')
        if self.pdf_available:
            formats.append('pdf')
            
        return formats

    def export_project(self, project: Project, file_path: str, format_type: str) -> bool:
        """Export project to specified format"""
        try:
            if format_type.lower() == 'txt':
                return self._export_txt(project, file_path)
            elif format_type.lower() == 'odt' and self.odt_available:
                return self._export_odt(project, file_path)
            elif format_type.lower() == 'pdf' and self.pdf_available:
                return self._export_pdf(project, file_path)
            else:
                print(_("Export format '{}' not available").format(format_type))
                return False
                
        except Exception as e:
            print(_("Error exporting project: {}: {}").format(type(e).__name__, e))
            import traceback
            traceback.print_exc()
            return False

    def _export_txt(self, project: Project, file_path: str) -> bool:
        """Export to plain text format"""
        try:
            # Ensure parent directory exists
            file_path_obj = Path(file_path)
            file_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # Collect footnotes and group paragraphs
            all_footnotes, footnote_map = self._collect_footnotes(project)
            grouped = self._group_paragraphs(project, footnote_map)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                # Project title
                f.write(f"{project.name}\n")
                f.write("=" * len(project.name) + "\n\n")
                
                # Write grouped content
                for item in grouped:
                    if item['type'] == 'title1':
                        f.write(f"\n{item['content']}\n")
                        f.write("-" * len(item['content']) + "\n\n")
                    
                    elif item['type'] == 'title2':
                        f.write(f"\n{item['content']}\n\n")
                    
                    elif item['type'] == 'quote':
                        f.write(f"        {item['content']}\n\n")

                    elif item['type'] == 'epigraph': # New block
                        # Indent epigraph significantly to the right
                        f.write(f"                            {item['content']}\n\n")
                    
                    elif item['type'] == 'image':
                        # Add image placeholder in TXT
                        metadata = item['metadata']
                        caption = metadata.get('caption', '')
                        if caption:
                            f.write(f"\n[IMAGE: {metadata.get('filename', 'image')} - {caption}]\n\n")
                        else:
                            f.write(f"\n[IMAGE: {metadata.get('filename', 'image')}]\n\n")
                    
                    elif item['type'] == 'content':
                        if item['indent']:
                            f.write(f"    {item['content']}\n\n")
                        else:
                            f.write(f"{item['content']}\n\n")
                
                # Write footnotes
                if all_footnotes:
                    f.write("\n" + "=" * 20 + "\n")
                    f.write(_("Footnotes:") + "\n\n")
                    for i, footnote in enumerate(all_footnotes):
                        f.write(f"{i + 1}. {footnote}\n\n")
            
            return True
            
        except OSError as e:
            print(_("File error exporting to TXT: {}").format(e))
            return False
        except Exception as e:
            print(_("Unexpected error exporting to TXT: {}: {}").format(type(e).__name__, e))
            import traceback
            traceback.print_exc()
            return False

    def _export_odt(self, project: Project, file_path: str) -> bool:
        """Export to OpenDocument Text format"""
        try:
            # Ensure parent directory exists
            odt_path = Path(file_path)
            odt_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create temporary directory
            temp_dir = odt_path.parent / f"temp_odt_{project.id}"
            temp_dir.mkdir(exist_ok=True)
            
            try:
                # Create ODT directory structure
                (temp_dir / "META-INF").mkdir(exist_ok=True)
                (temp_dir / "Pictures").mkdir(exist_ok=True)
                
                # Collect image files and copy them to Pictures directory
                image_files = []
                for paragraph in project.paragraphs:
                    if paragraph.type == ParagraphType.IMAGE:
                        img_metadata = paragraph.get_image_metadata()
                        if img_metadata:
                            img_path = Path(img_metadata['path'])
                            if img_path.exists():
                                # Copy image to Pictures directory
                                dest_name = img_metadata['filename']
                                dest_path = temp_dir / "Pictures" / dest_name
                                shutil.copy2(img_path, dest_path)
                                image_files.append(dest_name)
                
                # Create manifest.xml (with images)
                self._create_manifest(temp_dir / "META-INF" / "manifest.xml", image_files)
                
                # Create styles.xml
                self._create_styles(temp_dir / "styles.xml")
                
                # Create content.xml
                content_xml = self._generate_odt_content(project)
                with open(temp_dir / "content.xml", 'w', encoding='utf-8') as f:
                    f.write(content_xml)
                
                # Create meta.xml
                self._create_meta(temp_dir / "meta.xml", project)
                
                # Create ZIP archive
                with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    # Add mimetype first (uncompressed)
                    zf.writestr("mimetype", "application/vnd.oasis.opendocument.text", 
                            compress_type=zipfile.ZIP_STORED)
                    
                    # Add other files
                    for root, dirs, files in temp_dir.walk():
                        for file in files:
                            file_path_obj = root / file
                            arc_name = file_path_obj.relative_to(temp_dir)
                            zf.write(file_path_obj, arc_name)
                
                return True
                
            finally:
                # Clean up temp directory
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        except (OSError, zipfile.BadZipFile) as e:
            print(_("File error exporting to ODT: {}").format(e))
            return False
        except Exception as e:
            print(_("Unexpected error exporting to ODT: {}: {}").format(type(e).__name__, e))
            import traceback
            traceback.print_exc()
            return False

    def _generate_odt_content(self, project: Project) -> str:
        """Generate content.xml for ODT with proper formatting"""
        
        # Collect footnotes and group paragraphs
        all_footnotes, footnote_map = self._collect_footnotes(project)
        
        # Build grouped structure with footnote references for ODT
        grouped_odt = []
        current_paragraph_content = []
        paragraph_starts_with_introduction = False
        last_was_quote = False
        
        for i, paragraph in enumerate(project.paragraphs):
            content = paragraph.content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            if paragraph.type == ParagraphType.TITLE_1:
                if current_paragraph_content:
                    combined = " ".join(current_paragraph_content)
                    style = "Introduction" if paragraph_starts_with_introduction else "Normal"
                    grouped_odt.append({'type': 'content', 'content': combined, 'style': style})
                    current_paragraph_content = []
                    paragraph_starts_with_introduction = False
                
                grouped_odt.append({'type': 'title1', 'content': content})
                last_was_quote = False
            
            elif paragraph.type == ParagraphType.TITLE_2:
                if current_paragraph_content:
                    combined = " ".join(current_paragraph_content)
                    style = "Introduction" if paragraph_starts_with_introduction else "Normal"
                    grouped_odt.append({'type': 'content', 'content': combined, 'style': style})
                    current_paragraph_content = []
                    paragraph_starts_with_introduction = False
                
                grouped_odt.append({'type': 'title2', 'content': content})
                last_was_quote = False
            
            elif paragraph.type == ParagraphType.QUOTE:
                if current_paragraph_content:
                    combined = " ".join(current_paragraph_content)
                    style = "Introduction" if paragraph_starts_with_introduction else "Normal"
                    grouped_odt.append({'type': 'content', 'content': combined, 'style': style})
                    current_paragraph_content = []
                    paragraph_starts_with_introduction = False
                
                grouped_odt.append({'type': 'quote', 'content': content})
                last_was_quote = True
                
            elif paragraph.type == ParagraphType.EPIGRAPH:
                if current_paragraph_content:
                    combined = " ".join(current_paragraph_content)
                    style = "Introduction" if paragraph_starts_with_introduction else "Normal"
                    grouped_odt.append({'type': 'content', 'content': combined, 'style': style})
                    current_paragraph_content = []
                    paragraph_starts_with_introduction = False
                
                grouped_odt.append({'type': 'epigraph', 'content': content})
                last_was_quote = True
            
            elif paragraph.type == ParagraphType.IMAGE:
                # Write accumulated content first
                if current_paragraph_content:
                    combined = " ".join(current_paragraph_content)
                    style = "Introduction" if paragraph_starts_with_introduction else "Normal"
                    grouped_odt.append({'type': 'content', 'content': combined, 'style': style})
                    current_paragraph_content = []
                    paragraph_starts_with_introduction = False
                
                # Add image to grouped list
                img_metadata = paragraph.get_image_metadata()
                if img_metadata:
                    grouped_odt.append({'type': 'image', 'metadata': img_metadata})
                last_was_quote = False
            
            elif paragraph.type in [ParagraphType.INTRODUCTION, ParagraphType.ARGUMENT, ParagraphType.CONCLUSION, ParagraphType.ARGUMENT_RESUMPTION]:
                should_start_new = (
                    paragraph.type == ParagraphType.INTRODUCTION or
                    paragraph.type == ParagraphType.ARGUMENT_RESUMPTION or
                    last_was_quote or
                    not current_paragraph_content
                )
                
                if should_start_new and current_paragraph_content:
                    combined = " ".join(current_paragraph_content)
                    style = "Introduction" if paragraph_starts_with_introduction else "Normal"
                    grouped_odt.append({'type': 'content', 'content': combined, 'style': style})
                    current_paragraph_content = []
                    paragraph_starts_with_introduction = False
                
                if not current_paragraph_content:
                    if paragraph.type == ParagraphType.INTRODUCTION or paragraph.type == ParagraphType.ARGUMENT_RESUMPTION:
                        paragraph_starts_with_introduction = True
                    elif last_was_quote:
                        paragraph_starts_with_introduction = False
                
                # Add ODT footnote references
                if paragraph.id in footnote_map:
                    for footnote_num in footnote_map[paragraph.id]:
                        footnote_text = all_footnotes[footnote_num - 1]
                        content += f'<text:note text:id="ftn{footnote_num}" text:note-class="footnote"><text:note-citation>{footnote_num}</text:note-citation><text:note-body><text:p text:style-name="Footnote">{footnote_text}</text:p></text:note-body></text:note>'
                
                current_paragraph_content.append(content.strip())
                
                next_is_new = False
                if i + 1 < len(project.paragraphs):
                    next_p = project.paragraphs[i + 1]
                    if next_p.type in [ParagraphType.INTRODUCTION, ParagraphType.TITLE_1, 
                                      ParagraphType.TITLE_2, ParagraphType.QUOTE]:
                        next_is_new = True
                else:
                    next_is_new = True
                
                if next_is_new:
                    combined = " ".join(current_paragraph_content)
                    style = "Introduction" if paragraph_starts_with_introduction else "Normal"
                    grouped_odt.append({'type': 'content', 'content': combined, 'style': style})
                    current_paragraph_content = []
                    paragraph_starts_with_introduction = False
                
                last_was_quote = False
        
        # Write remaining
        if current_paragraph_content:
            combined = " ".join(current_paragraph_content)
            style = "Introduction" if paragraph_starts_with_introduction else "Normal"
            grouped_odt.append({'type': 'content', 'content': combined, 'style': style})
        
        # Generate XML
        content_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" 
                        xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" 
                        xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" 
                        xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
                        xmlns:xlink="http://www.w3.org/1999/xlink"
                        xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
                        xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0">
<office:automatic-styles/>
<office:body>
<office:text>'''
        
        # Project title
        content_xml += f'<text:p text:style-name="Title">{project.name}</text:p>\n'
        
        # Write grouped content
        for item in grouped_odt:
            if item['type'] == 'title1':
                content_xml += f'<text:p text:style-name="Title1">{item["content"]}</text:p>\n'
            elif item['type'] == 'title2':
                content_xml += f'<text:p text:style-name="Title2">{item["content"]}</text:p>\n'
            elif item['type'] == 'quote':
                content_xml += f'<text:p text:style-name="Quote">{item["content"]}</text:p>\n'
            elif item['type'] == 'epigraph':
                content_xml += f'<text:p text:style-name="Epigraph">{item["content"]}</text:p>\n'
            elif item['type'] == 'image':
                # Add actual image to ODT
                metadata = item['metadata']
                filename = metadata.get('filename', 'image')
                original_size = metadata.get('original_size', (800, 600))
                width_percent = metadata.get('width_percent', 80.0)
                alignment = metadata.get('alignment', 'center')
                caption = metadata.get('caption', '')
                
                # Calculate image size for ODT
                # A4 page width is 21cm, minus 6cm margins (3cm each side) = 15cm usable
                usable_page_width_cm = 15.0
                img_width_cm = usable_page_width_cm * (width_percent / 100.0)
                
                # Calculate height maintaining aspect ratio
                aspect_ratio = original_size[1] / original_size[0]
                img_height_cm = img_width_cm * aspect_ratio
                
                # Determine alignment style name
                if alignment == 'center':
                    style_name = 'GraphicsCenter'
                elif alignment == 'right':
                    style_name = 'GraphicsRight'
                else:  # left
                    style_name = 'GraphicsLeft'
                
                # Create draw:frame with image
                content_xml += f'''<text:p text:style-name="Normal">
  <draw:frame draw:style-name="{style_name}" draw:name="{filename}" text:anchor-type="paragraph" 
              svg:width="{img_width_cm:.2f}cm" svg:height="{img_height_cm:.2f}cm" 
              draw:z-index="0">
    <draw:image xlink:href="Pictures/{filename}" xlink:type="simple" xlink:show="embed" xlink:actuate="onLoad"/>
  </draw:frame>
</text:p>\n'''
                
                # Add caption if exists
                if caption:
                    content_xml += f'<text:p text:style-name="ImageCaption">{caption}</text:p>\n'
                    
            elif item['type'] == 'content':
                content_xml += f'<text:p text:style-name="{item["style"]}">{item["content"]}</text:p>\n'
        
        content_xml += '''</office:text>
</office:body>
</office:document-content>'''
        
        return content_xml

    def _create_manifest(self, file_path: Path, image_files: list = None):
        """Create manifest.xml for ODT"""
        manifest_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">
  <manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.text"/>
  <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
  <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>
  <manifest:file-entry manifest:full-path="meta.xml" manifest:media-type="text/xml"/>'''
        
        # Add image file entries
        if image_files:
            for img_file in image_files:
                # Determine MIME type based on extension
                ext = Path(img_file).suffix.lower()
                mime_types = {
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.webp': 'image/webp'
                }
                mime_type = mime_types.get(ext, 'image/png')
                
                manifest_xml += f'\n  <manifest:file-entry manifest:full-path="Pictures/{img_file}" manifest:media-type="{mime_type}"/>'
        
        manifest_xml += '\n</manifest:manifest>'
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(manifest_xml)

    def _create_styles(self, file_path: Path):
        """Create styles.xml for ODT"""
        styles_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" 
                       xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" 
                       xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0">
<office:styles>
  <style:style style:name="Title" style:family="paragraph">
    <style:text-properties fo:font-size="18pt" fo:font-weight="bold"/>
    <style:paragraph-properties fo:text-align="center" fo:margin-bottom="0.5cm"/>
  </style:style>
  
  <style:style style:name="Title1" style:family="paragraph">
    <style:text-properties fo:font-size="16pt" fo:font-weight="bold"/>
    <style:paragraph-properties fo:margin-top="0.5cm" fo:margin-bottom="0.3cm"/>
  </style:style>
  
  <style:style style:name="Title2" style:family="paragraph">
    <style:text-properties fo:font-size="14pt" fo:font-weight="bold"/>
    <style:paragraph-properties fo:margin-top="0.4cm" fo:margin-bottom="0.2cm"/>
  </style:style>
  
  <style:style style:name="Introduction" style:family="paragraph">
    <style:text-properties fo:font-size="12pt"/>
    <style:paragraph-properties fo:text-align="justify" fo:text-indent="1.5cm" fo:margin-bottom="0.0cm" fo:line-height="150%"/>
  </style:style>
  
  <style:style style:name="Normal" style:family="paragraph">
    <style:text-properties fo:font-size="12pt"/>
    <style:paragraph-properties fo:text-align="justify" fo:margin-bottom="0.0cm" fo:line-height="150%"/>
  </style:style>
  
  <style:style style:name="Quote" style:family="paragraph">
    <style:text-properties fo:font-size="10pt" fo:font-style="italic"/>
    <style:paragraph-properties fo:text-align="justify" fo:margin-left="4cm" fo:margin-bottom="0.3cm" fo:line-height="100%"/>
  </style:style>
  
  <style:style style:name="Epigraph" style:family="paragraph"> <!-- New style -->
    <style:text-properties fo:font-size="12pt" fo:font-style="italic"/>
    <style:paragraph-properties fo:text-align="right" fo:margin-left="7.5cm" fo:margin-bottom="0.3cm" fo:line-height="150%"/>
  </style:style>

  <style:style style:name="Footnote" style:family="paragraph">
    <style:text-properties fo:font-size="9pt"/>
    <style:paragraph-properties fo:text-align="justify" fo:margin-bottom="0.2cm" fo:line-height="100%"/>
  </style:style>
  
  <style:style style:name="ImageCaption" style:family="paragraph">
    <style:text-properties fo:font-size="10pt" fo:font-style="italic"/>
    <style:paragraph-properties fo:text-align="center" fo:margin-top="0.2cm" fo:margin-bottom="0.5cm"/>
  </style:style>
  
  <style:style style:name="GraphicsLeft" style:family="graphic">
    <style:graphic-properties style:run-through="foreground" style:wrap="none" style:horizontal-pos="left" style:horizontal-rel="paragraph" style:vertical-pos="top" style:vertical-rel="paragraph"/>
  </style:style>
  
  <style:style style:name="GraphicsCenter" style:family="graphic">
    <style:graphic-properties style:run-through="foreground" style:wrap="none" style:horizontal-pos="center" style:horizontal-rel="paragraph" style:vertical-pos="top" style:vertical-rel="paragraph"/>
  </style:style>
  
  <style:style style:name="GraphicsRight" style:family="graphic">
    <style:graphic-properties style:run-through="foreground" style:wrap="none" style:horizontal-pos="right" style:horizontal-rel="paragraph" style:vertical-pos="top" style:vertical-rel="paragraph"/>
  </style:style>
</office:styles>
</office:document-styles>'''
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(styles_xml)

    def _create_meta(self, file_path: Path, project: Project):
        """Create meta.xml for ODT"""
        meta_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-meta xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
                     xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
                     xmlns:dc="http://purl.org/dc/elements/1.1/">
<office:meta>
  <meta:generator>TAC - Continuous Argumentation Technique</meta:generator>
  <dc:title>{project.name}</dc:title>
  <dc:creator>{project.metadata.get('author', '')}</dc:creator>
  <dc:description>{project.metadata.get('description', '')}</dc:description>
  <meta:creation-date>{project.created_at.isoformat()}</meta:creation-date>
  <dc:date>{project.modified_at.isoformat()}</dc:date>
</office:meta>
</office:document-meta>'''
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(meta_xml)

    def _export_pdf(self, project: Project, file_path: str) -> bool:
        """Export to PDF format"""
        try:
            # Ensure parent directory exists
            file_path_obj = Path(file_path)
            file_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            # Create document
            doc = SimpleDocTemplate(
                file_path,
                pagesize=A4,
                rightMargin=3*cm,
                leftMargin=3*cm,
                topMargin=2.5*cm,
                bottomMargin=2.5*cm
            )
            
            # Get styles
            styles = getSampleStyleSheet()
            
            # Create custom styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Title'],
                fontSize=18,
                spaceAfter=30,
                alignment=TA_CENTER,
                fontName='Times-Bold'
            )

            title1_style = ParagraphStyle(
                'CustomTitle1',
                parent=styles['Heading1'],
                fontSize=16,
                spaceBefore=24,
                spaceAfter=12,
                leftIndent=0,
                fontName='Times-Bold'
            )

            title2_style = ParagraphStyle(
                'CustomTitle2',
                parent=styles['Heading2'],
                fontSize=14,
                spaceBefore=18,
                spaceAfter=9,
                leftIndent=0,
                fontName='Times-Bold'
            )

            introduction_style = ParagraphStyle(
                'Introduction',
                parent=styles['Normal'],
                fontSize=12,
                leading=18,
                firstLineIndent=1.5*cm,
                spaceBefore=12,
                spaceAfter=12,
                alignment=TA_JUSTIFY,
                fontName='Times-Roman'
            )

            normal_style = ParagraphStyle(
                'Normal',
                parent=styles['Normal'],
                fontSize=12,
                leading=18,
                spaceBefore=12,
                spaceAfter=12,
                alignment=TA_JUSTIFY,
                fontName='Times-Roman'
            )

            quote_style = ParagraphStyle(
                'Quote',
                parent=styles['Normal'],
                fontSize=10,
                leading=12,
                leftIndent=4*cm,
                spaceBefore=12,
                spaceAfter=12,
                fontName='Times-Italic',
                alignment=TA_JUSTIFY
            )
            
            epigraph_style = ParagraphStyle(
                'Epigraph',
                parent=styles['Normal'],
                fontSize=12,
                leading=18, # 12 * 1.5
                leftIndent=7.5*cm,
                spaceBefore=12,
                spaceAfter=12,
                fontName='Times-Italic',
                alignment=TA_RIGHT
            )
            
            footnote_style = ParagraphStyle(
                'Footnote',
                parent=styles['Normal'],
                fontSize=9,
                leading=11,
                spaceBefore=6,
                spaceAfter=6,
                fontName='Times-Roman',
                alignment=TA_JUSTIFY
            )
            
            # Collect footnotes and group paragraphs (with PDF-specific footnote formatting)
            all_footnotes, footnote_map = self._collect_footnotes(project)
            
            # Build PDF-specific grouped structure
            grouped_pdf = []
            current_paragraph_content = []
            current_style = None
            paragraph_starts_with_introduction = False
            last_was_quote = False
            
            for i, paragraph in enumerate(project.paragraphs):
                content = paragraph.content.strip()
                
                if paragraph.type == ParagraphType.TITLE_1:
                    if current_paragraph_content:
                        combined = " ".join(current_paragraph_content)
                        grouped_pdf.append({'type': 'content', 'content': combined, 'style': current_style})
                        current_paragraph_content = []
                        current_style = None
                        paragraph_starts_with_introduction = False
                    
                    grouped_pdf.append({'type': 'title1', 'content': content})
                    last_was_quote = False
                
                elif paragraph.type == ParagraphType.TITLE_2:
                    if current_paragraph_content:
                        combined = " ".join(current_paragraph_content)
                        grouped_pdf.append({'type': 'content', 'content': combined, 'style': current_style})
                        current_paragraph_content = []
                        current_style = None
                        paragraph_starts_with_introduction = False
                    
                    grouped_pdf.append({'type': 'title2', 'content': content})
                    last_was_quote = False
                
                elif paragraph.type == ParagraphType.QUOTE:
                    if current_paragraph_content:
                        combined = " ".join(current_paragraph_content)
                        grouped_pdf.append({'type': 'content', 'content': combined, 'style': current_style})
                        current_paragraph_content = []
                        current_style = None
                        paragraph_starts_with_introduction = False
                    
                    grouped_pdf.append({'type': 'quote', 'content': content})
                    last_was_quote = True
                
                elif paragraph.type == ParagraphType.EPIGRAPH: # New block
                    if current_paragraph_content:
                        combined = " ".join(current_paragraph_content)
                        grouped_pdf.append({'type': 'content', 'content': combined, 'style': current_style})
                        current_paragraph_content = []
                        current_style = None
                        paragraph_starts_with_introduction = False
                    
                    grouped_pdf.append({'type': 'epigraph', 'content': content})
                    last_was_quote = True
                
                elif paragraph.type == ParagraphType.IMAGE:
                    if current_paragraph_content:
                        combined = " ".join(current_paragraph_content)
                        grouped_pdf.append({'type': 'content', 'content': combined, 'style': current_style})
                        current_paragraph_content = []
                        current_style = None
                        paragraph_starts_with_introduction = False
                    
                    # Add image to grouped list
                    img_metadata = paragraph.get_image_metadata()
                    if img_metadata:
                        grouped_pdf.append({'type': 'image', 'metadata': img_metadata})
                    last_was_quote = False
                
                elif paragraph.type in [ParagraphType.INTRODUCTION, ParagraphType.ARGUMENT, ParagraphType.CONCLUSION, ParagraphType.ARGUMENT_RESUMPTION]:
                    should_start_new = (
                        paragraph.type == ParagraphType.INTRODUCTION or
                        paragraph.type == ParagraphType.ARGUMENT_RESUMPTION or
                        last_was_quote or
                        not current_paragraph_content
                    )
                    
                    if should_start_new and current_paragraph_content:
                        combined = " ".join(current_paragraph_content)
                        grouped_pdf.append({'type': 'content', 'content': combined, 'style': current_style})
                        current_paragraph_content = []
                        current_style = None
                        paragraph_starts_with_introduction = False
                    
                    if not current_paragraph_content:
                        if paragraph.type == ParagraphType.INTRODUCTION or paragraph.type == ParagraphType.ARGUMENT_RESUMPTION:
                            paragraph_starts_with_introduction = True
                            current_style = introduction_style
                        elif last_was_quote:
                            paragraph_starts_with_introduction = False
                            current_style = normal_style
                        else:
                            if current_style is None:
                                current_style = normal_style
                    
                    # Add PDF footnote references
                    if paragraph.id in footnote_map:
                        for footnote_num in footnote_map[paragraph.id]:
                            content += f"<sup>{footnote_num}</sup>"
                    
                    current_paragraph_content.append(content)
                    
                    next_is_new = False
                    if i + 1 < len(project.paragraphs):
                        next_p = project.paragraphs[i + 1]
                        if next_p.type in [ParagraphType.INTRODUCTION, ParagraphType.TITLE_1, 
                                          ParagraphType.TITLE_2, ParagraphType.QUOTE]:
                            next_is_new = True
                    else:
                        next_is_new = True
                    
                    if next_is_new:
                        combined = " ".join(current_paragraph_content)
                        grouped_pdf.append({'type': 'content', 'content': combined, 'style': current_style})
                        current_paragraph_content = []
                        current_style = None
                        paragraph_starts_with_introduction = False
                    
                    last_was_quote = False
            
            # Write remaining
            if current_paragraph_content:
                combined = " ".join(current_paragraph_content)
                grouped_pdf.append({'type': 'content', 'content': combined, 'style': current_style})
            
            # Build story
            story = []
            story.append(RLParagraph(project.name, title_style))
            story.append(Spacer(1, 20))
            
            # Write grouped content
            for item in grouped_pdf:
                if item['type'] == 'title1':
                    story.append(RLParagraph(item['content'], title1_style))
                elif item['type'] == 'title2':
                    story.append(RLParagraph(item['content'], title2_style))
                elif item['type'] == 'quote':
                    story.append(RLParagraph(item['content'], quote_style))
                elif item['type'] == 'epigraph':
                    story.append(RLParagraph(item['content'], epigraph_style))
                elif item['type'] == 'image':
                    # Add image to PDF
                    try:
                        metadata = item['metadata']
                        img_path = Path(metadata['path'])
                        
                        if img_path.exists():
                            # Get metadata
                            original_size = metadata.get('original_size', (800, 600))
                            width_percent = metadata.get('width_percent', 80.0)
                            alignment = metadata.get('alignment', 'center')
                            
                            # Calculate image size for PDF based on page width percentage
                            # A4 width is 21cm, minus 6cm margins (3cm each side) = 15cm usable
                            usable_page_width = 15.0  # cm
                            img_width_cm = usable_page_width * (width_percent / 100.0)
                            
                            # Calculate height maintaining aspect ratio
                            aspect_ratio = original_size[1] / original_size[0]
                            img_height_cm = img_width_cm * aspect_ratio
                            
                            # Create image with correct size
                            pdf_img = RLImage(str(img_path), width=img_width_cm*cm, height=img_height_cm*cm)
                            
                            # Set alignment
                            if alignment == 'center':
                                pdf_img.hAlign = 'CENTER'
                            elif alignment == 'right':
                                pdf_img.hAlign = 'RIGHT'
                            else:
                                pdf_img.hAlign = 'LEFT'
                            
                            story.append(pdf_img)
                            story.append(Spacer(1, 12))
                            
                            # Add caption if exists
                            caption = metadata.get('caption', '')
                            if caption:
                                # Caption alignment should match image alignment
                                if alignment == 'left':
                                    caption_alignment = TA_LEFT
                                elif alignment == 'right':
                                    caption_alignment = TA_RIGHT
                                else:
                                    caption_alignment = TA_CENTER
                                
                                caption_style = ParagraphStyle(
                                    'ImageCaption',
                                    parent=normal_style,
                                    fontSize=10,
                                    alignment=caption_alignment,
                                    fontName='Times-Italic'
                                )
                                story.append(RLParagraph(caption, caption_style))
                                story.append(Spacer(1, 12))
                    except Exception as e:
                        print(_("Error adding image to PDF: {}").format(e))
                        # Add placeholder text if image fails
                        story.append(RLParagraph(f"[Image: {metadata.get('filename', 'image')}]", normal_style))
                
                elif item['type'] == 'content':
                    story.append(RLParagraph(item['content'], item['style']))
            
            # Add footnotes
            if all_footnotes:
                story.append(Spacer(1, 20))
                story.append(RLParagraph(_("Footnotes:"), title2_style))
                for i, footnote_text in enumerate(all_footnotes):
                    footnote_content = f"{i + 1}. {footnote_text}"
                    story.append(RLParagraph(footnote_content, footnote_style))
            
            # Build PDF
            doc.build(story)
            return True
            
        except OSError as e:
            print(_("File error exporting to PDF: {}").format(e))
            return False
        except Exception as e:
            print(_("Unexpected error exporting to PDF: {}: {}").format(type(e).__name__, e))
            import traceback
            traceback.print_exc()
            return False