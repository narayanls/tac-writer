"""
TAC Services
Business logic and service classes for project management and export
"""

import json
import zipfile
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

from .models import Project, Paragraph, ParagraphType, DEFAULT_TEMPLATES


class ProjectManager:
    """Manages project creation, loading, saving and organization"""
    
    def __init__(self, projects_directory: Optional[Path] = None):
        if projects_directory:
            self.projects_dir = Path(projects_directory)
        else:
            # Default to user's documents folder
            self.projects_dir = Path.home() / 'Documents' / 'TAC Projects'
        
        # Ensure projects directory exists
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for loaded projects
        self._project_cache: Dict[str, Project] = {}
        
        print(f"ProjectManager initialized with directory: {self.projects_dir}")
    
    def create_project(self, name: str, template_name: str = "Academic Essay") -> Project:
        """Create a new project from template"""
        if not name.strip():
            raise ValueError("Project name cannot be empty")
        
        # Find template
        template = None
        for tmpl in DEFAULT_TEMPLATES:
            if tmpl.name == template_name:
                template = tmpl
                break
        
        if template:
            project = template.create_project(name.strip())
        else:
            # Create basic project if template not found
            project = Project(name.strip())
            project.add_paragraph(ParagraphType.INTRODUCTION)
        
        # Save immediately
        self.save_project(project)
        
        # Add to cache
        self._project_cache[project.id] = project
        
        print(f"Created new project: {project.name}")
        return project
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """List all available projects with basic info"""
        projects = []
        
        try:
            for file_path in self.projects_dir.glob("*.json"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Extract basic project info
                    project_info = {
                        'id': data.get('id', file_path.stem),
                        'name': data.get('name', file_path.stem),
                        'created_at': data.get('created_at', ''),
                        'modified_at': data.get('modified_at', ''),
                        'file_path': str(file_path),
                        'author': data.get('metadata', {}).get('author', ''),
                        'description': data.get('metadata', {}).get('description', ''),
                        'statistics': data.get('statistics', {})
                    }
                    projects.append(project_info)
                    
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Error reading project file {file_path.name}: {e}")
                except Exception as e:
                    print(f"Unexpected error reading {file_path.name}: {e}")
        
        except Exception as e:
            print(f"Error listing projects: {e}")
        
        # Sort by modification date (newest first)
        projects.sort(key=lambda x: x.get('modified_at', ''), reverse=True)
        return projects
    
    def load_project(self, project_identifier: str) -> Optional[Project]:
        """Load a project by ID or file path"""
        # Check cache first
        if project_identifier in self._project_cache:
            return self._project_cache[project_identifier]
        
        try:
            # Try to load by ID
            file_path = self.projects_dir / f"{project_identifier}.json"
            
            # If not found by ID, try as direct file path
            if not file_path.exists():
                file_path = Path(project_identifier)
                if not file_path.exists():
                    # Search by name
                    for candidate in self.projects_dir.glob("*.json"):
                        try:
                            with open(candidate, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            if data.get('name') == project_identifier:
                                file_path = candidate
                                break
                        except:
                            continue
                    else:
                        print(f"Project not found: {project_identifier}")
                        return None
            
            # Load project data
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Create project from data
            project = Project.from_dict(data)
            
            # Add to cache
            self._project_cache[project.id] = project
            
            print(f"Loaded project: {project.name}")
            return project
            
        except Exception as e:
            print(f"Error loading project '{project_identifier}': {e}")
            return None
    
    def save_project(self, project: Project) -> bool:
        """Save a project to disk"""
        try:
            file_path = self.projects_dir / f"{project.id}.json"
            
            # Create backup if file exists
            if file_path.exists():
                backup_path = file_path.with_suffix('.json.bak')
                file_path.replace(backup_path)
            
            # Save project data
            data = project.to_dict()
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Update cache
            self._project_cache[project.id] = project
            
            print(f"Saved project: {project.name}")
            return True
            
        except Exception as e:
            print(f"Error saving project '{project.name}': {e}")
            return False
    
    def delete_project(self, project_identifier: str) -> bool:
        """Delete a project (moves to trash folder)"""
        try:
            # Load project to get correct ID
            project = self.load_project(project_identifier)
            if not project:
                return False
            
            file_path = self.projects_dir / f"{project.id}.json"
            
            if file_path.exists():
                # Create trash directory
                trash_dir = self.projects_dir / '.trash'
                trash_dir.mkdir(exist_ok=True)
                
                # Move to trash with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                trash_path = trash_dir / f"{project.id}_{timestamp}.json"
                file_path.replace(trash_path)
                
                # Remove from cache
                if project.id in self._project_cache:
                    del self._project_cache[project.id]
                
                print(f"Deleted project: {project.name}")
                return True
            
            return False
            
        except Exception as e:
            print(f"Error deleting project: {e}")
            return False
    
    def duplicate_project(self, project_identifier: str, new_name: str) -> Optional[Project]:
        """Create a copy of an existing project"""
        try:
            original = self.load_project(project_identifier)
            if not original:
                return None
            
            # Create new project
            duplicate = Project(new_name)
            
            # Copy data (excluding ID and timestamps)
            duplicate.metadata = original.metadata.copy()
            duplicate.metadata['description'] = f"Copy of: {original.name}"
            duplicate.document_formatting = original.document_formatting.copy()
            
            # Copy paragraphs
            for orig_paragraph in original.paragraphs:
                new_paragraph = Paragraph(
                    paragraph_type=orig_paragraph.type,
                    content=orig_paragraph.content
                )
                new_paragraph.formatting = orig_paragraph.formatting.copy()
                duplicate.paragraphs.append(new_paragraph)
            
            duplicate._reorder_paragraphs()
            
            # Save duplicate
            if self.save_project(duplicate):
                print(f"Duplicated project: {original.name} -> {new_name}")
                return duplicate
            
            return None
            
        except Exception as e:
            print(f"Error duplicating project: {e}")
            return None
    
    def get_project_path(self, project: Project) -> Path:
        """Get the file path for a project"""
        return self.projects_dir / f"{project.id}.json"


class ExportService:
    """Service for exporting projects to various formats"""
    
    def __init__(self):
        self.supported_formats = ['txt', 'html', 'odt', 'rtf']
    
    def export_project(self, project: Project, output_path: str, format_type: str = 'txt') -> bool:
        """Export project to specified format"""
        format_type = format_type.lower()
        
        if format_type not in self.supported_formats:
            print(f"Unsupported format: {format_type}")
            return False
        
        try:
            if format_type == 'txt':
                return self._export_txt(project, output_path)
            elif format_type == 'html':
                return self._export_html(project, output_path)
            elif format_type == 'odt':
                return self._export_odt(project, output_path)
            elif format_type == 'rtf':
                return self._export_rtf(project, output_path)
            
        except Exception as e:
            print(f"Error exporting project to {format_type}: {e}")
            return False
        
        return False
    
    def _export_txt(self, project: Project, output_path: str) -> bool:
        """Export to plain text format"""
        with open(output_path, 'w', encoding='utf-8') as f:
            # Title
            f.write(f"{project.name}\n")
            f.write("=" * len(project.name) + "\n\n")
            
            # Metadata
            if project.metadata.get('author'):
                f.write(f"Author: {project.metadata['author']}\n")
            if project.metadata.get('date'):
                f.write(f"Date: {project.metadata['date']}\n")
            f.write("\n")
            
            # Content
            for i, paragraph in enumerate(project.paragraphs):
                if paragraph.type == ParagraphType.ARGUMENT_QUOTE:
                    f.write(f"[QUOTE {i+1}]\n")
                    # Indent quoted text
                    lines = paragraph.content.split('\n')
                    for line in lines:
                        f.write(f"    {line}\n")
                else:
                    f.write(f"{paragraph.content}\n")
                f.write("\n")
        
        return True
    
    def _export_html(self, project: Project, output_path: str) -> bool:
        """Export to HTML format"""
        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project.name}</title>
    <style>
        body {{
            font-family: '{project.document_formatting.get('font_family', 'Times New Roman')}', serif;
            font-size: {project.document_formatting.get('font_size', 12)}pt;
            line-height: {project.document_formatting.get('line_spacing', 1.5)};
            max-width: 800px;
            margin: 0 auto;
            padding: 40px 20px;
            background-color: #fff;
            color: #000;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 2em;
            border-bottom: 2px solid #333;
            padding-bottom: 0.5em;
        }}
        .paragraph {{
            margin-bottom: 1.5em;
            text-align: justify;
            text-indent: {project.document_formatting.get('margins', {}).get('left', 1.25)}cm;
        }}
        .quote {{
            margin: 2em 0;
            padding: 1em;
            border-left: 4px solid #ccc;
            background-color: #f9f9f9;
            font-style: italic;
            margin-left: 4cm;
            margin-right: 4cm;
        }}
        .metadata {{
            text-align: center;
            margin-bottom: 3em;
            color: #666;
        }}
    </style>
</head>
<body>
    <h1>{project.name}</h1>
'''
        
        # Add metadata
        if project.metadata.get('author') or project.metadata.get('date'):
            html_content += '    <div class="metadata">\n'
            if project.metadata.get('author'):
                html_content += f'        <p>by {project.metadata["author"]}</p>\n'
            if project.metadata.get('date'):
                html_content += f'        <p>{project.metadata["date"]}</p>\n'
            html_content += '    </div>\n'
        
        # Add paragraphs
        for paragraph in project.paragraphs:
            content = paragraph.content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            if paragraph.type == ParagraphType.ARGUMENT_QUOTE:
                html_content += f'    <div class="quote">{content}</div>\n'
            else:
                html_content += f'    <p class="paragraph">{content}</p>\n'
        
        html_content += '''</body>
</html>'''
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return True
    
    def _export_odt(self, project: Project, output_path: str) -> bool:
        """Export to LibreOffice ODT format (simplified)"""
        # This is a basic ODT implementation
        # For production, consider using python-odf library
        
        content_xml = self._generate_odt_content(project)
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create ODT structure
                (temp_path / 'META-INF').mkdir()
                
                # Manifest file
                with open(temp_path / 'META-INF' / 'manifest.xml', 'w', encoding='utf-8') as f:
                    f.write('''<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0">
    <manifest:file-entry manifest:full-path="/" manifest:version="1.2" manifest:media-type="application/vnd.oasis.opendocument.text"/>
    <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
    <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>
</manifest:manifest>''')
                
                # Content file
                with open(temp_path / 'content.xml', 'w', encoding='utf-8') as f:
                    f.write(content_xml)
                
                # Basic styles
                with open(temp_path / 'styles.xml', 'w', encoding='utf-8') as f:
                    f.write('''<?xml version="1.0" encoding="UTF-8"?>
<office:document-styles xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0">
</office:document-styles>''')
                
                # Create ZIP file
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for file_path in temp_path.rglob('*'):
                        if file_path.is_file():
                            arcname = str(file_path.relative_to(temp_path))
                            zf.write(file_path, arcname)
            
            return True
            
        except Exception as e:
            print(f"Error creating ODT file: {e}")
            # Fallback to XML file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content_xml)
            return True
    
    def _generate_odt_content(self, project: Project) -> str:
        """Generate ODT content XML"""
        content = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content 
    xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
    xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
    <office:body>
        <office:text>
'''
        
        # Title
        content += f'            <text:h text:style-name="Heading_20_1" text:outline-level="1">{project.name}</text:h>\n'
        
        # Paragraphs
        for paragraph in project.paragraphs:
            p_content = paragraph.content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            
            if paragraph.type == ParagraphType.ARGUMENT_QUOTE:
                content += f'            <text:p text:style-name="Quotations">{p_content}</text:p>\n'
            else:
                content += f'            <text:p text:style-name="Standard">{p_content}</text:p>\n'
        
        content += '''        </office:text>
    </office:body>
</office:document-content>'''
        
        return content
    
    def _export_rtf(self, project: Project, output_path: str) -> bool:
        """Export to RTF format"""
        rtf_content = r'''{\rtf1\ansi\deff0 {\fonttbl {\f0 Times New Roman;}}
'''
        
        # Title
        rtf_content += f'\\f0\\fs24\\b {project.name}\\b0\\par\\par\n'
        
        # Paragraphs
        for paragraph in project.paragraphs:
            content = paragraph.content.replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}')
            
            if paragraph.type == ParagraphType.ARGUMENT_QUOTE:
                rtf_content += f'\\li720\\i {content}\\i0\\li0\\par\\par\n'
            else:
                rtf_content += f'\\fi720 {content}\\par\\par\n'
        
        rtf_content += '}'
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(rtf_content)
        
        return True