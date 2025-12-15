"""
TAC Data Models
Pure data models for projects, paragraphs and documents
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from utils.i18n import _


class ParagraphType(Enum):
    """Types of paragraphs in academic writing"""
    TITLE_1 = "title_1"
    TITLE_2 = "title_2"
    INTRODUCTION = "introduction"
    ARGUMENT = "argument"
    ARGUMENT_RESUMPTION = "argument_resumption"
    QUOTE = "quote"
    EPIGRAPH = "epigraph"
    CONCLUSION = "conclusion"
    IMAGE = "image"

class Paragraph:
    """Represents a single paragraph in a document"""
    
    def __init__(self, paragraph_type: ParagraphType, content: str = "",
                 paragraph_id: Optional[str] = None):
        self.id = paragraph_id or str(uuid.uuid4())
        self.type = paragraph_type
        self.content = content
        self.footnotes = []  # List of footnote texts
        self.created_at = datetime.now()
        self.modified_at = self.created_at
        self.order = 0
        
        # Default formatting options
        self.formatting = {
            'font_family': 'Adwaita Sans',
            'font_size': 12,
            'line_spacing': 1.5,
            'alignment': 'justify',
            'indent_first_line': 0.0,
            'indent_left': 0.0,
            'indent_right': 0.0,
            'bold': False,
            'italic': False,
            'underline': False,
        }
        
        # Apply type-specific formatting
        self._apply_type_formatting()

    def _apply_type_formatting(self):
        """Apply formatting specific to paragraph type"""
        if self.type == ParagraphType.TITLE_1:
            self.formatting.update({
                'font_size': 18,
                'bold': True,
                'alignment': 'left',
                'line_spacing': 1.2,
            })
        elif self.type == ParagraphType.TITLE_2:
            self.formatting.update({
                'font_size': 16,
                'bold': True,
                'alignment': 'left',
                'line_spacing': 1.2,
            })
        elif self.type == ParagraphType.INTRODUCTION:
            self.formatting.update({
                'indent_first_line': 1.5,
            })
        elif self.type == ParagraphType.ARGUMENT_RESUMPTION:
            self.formatting.update({
                'indent_first_line': 1.5,
            })
        elif self.type == ParagraphType.QUOTE:
            self.formatting.update({
                'font_size': 10,
                'indent_left': 4.0,
                'line_spacing': 1.0,
                'italic': True
            })
        elif self.type == ParagraphType.EPIGRAPH:
            self.formatting.update({
                'font_size': 12,
                'indent_left': 7.5,
                'line_spacing': 1.5,
                'alignment': 'right',
                'italic': True
            })

    def update_content(self, content: str) -> None:
        """Update paragraph content"""
        self.content = content
        self.modified_at = datetime.now()

    def update_formatting(self, formatting_updates: Dict[str, Any]) -> None:
        """Update paragraph formatting"""
        # Preserve type-specific font sizes if not explicitly changed
        if self.type in [ParagraphType.TITLE_1, ParagraphType.TITLE_2]:
            if 'font_size' not in formatting_updates:
                formatting_updates = formatting_updates.copy()
                formatting_updates['font_size'] = 18 if self.type == ParagraphType.TITLE_1 else 16
    
        self.formatting.update(formatting_updates)
        self.modified_at = datetime.now()

    def get_word_count(self) -> int:
        """Get word count for this paragraph"""
        return len(self.content.split()) if self.content else 0

    def get_character_count(self, include_spaces: bool = True) -> int:
        """Get character count for this paragraph"""
        if not self.content:
            return 0
        return len(self.content) if include_spaces else len(self.content.replace(' ', ''))
    
    def set_image_metadata(self, filename: str, path: str, original_size: tuple, 
                          display_size: tuple, alignment: str = 'center', 
                          caption: str = '', alt_text: str = '', width_percent: float = 80.0) -> None:
        """Set metadata for image paragraph"""
        import json
        if self.type != ParagraphType.IMAGE:
            raise ValueError("Can only set image metadata on IMAGE type paragraphs")
        
        metadata = {
            'filename': filename,
            'path': path,
            'original_size': original_size,
            'display_size': display_size,
            'alignment': alignment,
            'caption': caption,
            'alt_text': alt_text,
            'width_percent': width_percent
        }
        self.content = json.dumps(metadata)
        self.modified_at = datetime.now()
    
    def get_image_metadata(self) -> Optional[Dict[str, Any]]:
        """Get metadata from image paragraph"""
        import json
        if self.type != ParagraphType.IMAGE:
            return None
        
        try:
            return json.loads(self.content) if self.content else None
        except json.JSONDecodeError:
            return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert paragraph to dictionary"""
        return {
            'id': self.id,
            'type': self.type.value,
            'content': self.content,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
            'order': self.order,
            'formatting': self.formatting.copy(),
            'footnotes': self.footnotes.copy()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Paragraph':
        """Create paragraph from dictionary"""
        # Handle migration from old 'argument_quote' to new 'quote'
        paragraph_type_str = data['type']
        if paragraph_type_str == 'argument_quote':
            paragraph_type_str = 'quote'
        
        paragraph = cls(
            paragraph_type=ParagraphType(paragraph_type_str),
            content=data.get('content', ''),
            paragraph_id=data.get('id')
        )
        
        paragraph.created_at = datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
        paragraph.modified_at = datetime.fromisoformat(data.get('modified_at', datetime.now().isoformat()))
        paragraph.order = data.get('order', 0)
        
        if 'formatting' in data:
            paragraph.formatting.update(data['formatting'])
        
        # Load footnotes from saved data
        if 'footnotes' in data:
            paragraph.footnotes = data['footnotes'].copy()
        
        return paragraph


class Project:
    """Represents a writing project with multiple paragraphs"""
    
    def __init__(self, name: str, project_id: Optional[str] = None):
        self.id = project_id or str(uuid.uuid4())
        self.name = name
        self.created_at = datetime.now()
        self.modified_at = self.created_at
        self.paragraphs: List[Paragraph] = []
        
        # Project metadata
        self.metadata = {
            'author': '',
            'description': '',
            'tags': [],
            'version': '1.0',
            'language': 'en',
            'subject': '',
            'institution': '',
            'course': '',
            'professor': '',
            'due_date': None,
        }
        
        # Document formatting
        self.document_formatting = {
            'page_size': 'A4',
            'margins': {
                'top': 2.5,
                'bottom': 2.5,
                'left': 3.0,
                'right': 3.0
            },
            'line_spacing': 1.5,
            'font_family': 'Adwaita Sans',
            'font_size': 12,
            'header_footer': {
                'show_page_numbers': True,
                'show_header': False,
                'show_footer': False,
                'header_text': '',
                'footer_text': ''
            }
        }

    def add_paragraph(self, paragraph_type: ParagraphType, content: str = "",
                     position: Optional[int] = None, inherit_formatting: bool = True) -> Paragraph:
        """Add a new paragraph to the project"""
        paragraph = Paragraph(paragraph_type, content)
        
        # Inherit formatting from previous paragraphs if enabled
        if inherit_formatting:
            base_formatting = self._get_inherited_formatting()
            if base_formatting:
                self._apply_inherited_formatting(paragraph, base_formatting)
        
        # Add paragraph at specified position
        if position is None:
            paragraph.order = len(self.paragraphs)
            self.paragraphs.append(paragraph)
        else:
            paragraph.order = position
            self.paragraphs.insert(position, paragraph)
            self._reorder_paragraphs()
        
        self._update_modified_time()
        return paragraph

    def _get_inherited_formatting(self) -> Optional[Dict[str, Any]]:
        """Get formatting to inherit from existing paragraphs"""
        # Try preferred formatting first
        if 'preferred_formatting' in self.metadata:
            return self.metadata['preferred_formatting'].copy()
        
        # Find last content paragraph to inherit from
        for paragraph in reversed(self.paragraphs):
            if paragraph.type not in [ParagraphType.TITLE_1, ParagraphType.TITLE_2, ParagraphType.QUOTE]:
                return {
                    'font_family': paragraph.formatting.get('font_family', 'Adwaita Sans'),
                    'font_size': paragraph.formatting.get('font_size', 12),
                    'line_spacing': paragraph.formatting.get('line_spacing', 1.5),
                    'alignment': paragraph.formatting.get('alignment', 'justify'),
                    'bold': paragraph.formatting.get('bold', False),
                    'italic': paragraph.formatting.get('italic', False),
                    'underline': paragraph.formatting.get('underline', False),
                }
        
        return None

    def _apply_inherited_formatting(self, paragraph: Paragraph, base_formatting: Dict[str, Any]):
        """Apply inherited formatting while preserving type-specific settings"""
        current_formatting = paragraph.formatting.copy()
        current_formatting.update(base_formatting)
        
        # Preserve type-specific formatting
        if paragraph.type == ParagraphType.INTRODUCTION:
            current_formatting['indent_first_line'] = 1.5
        elif paragraph.type == ParagraphType.QUOTE:
            current_formatting.update({
                'font_size': 10,
                'indent_left': 4.0,
                'line_spacing': 1.0,
                'italic': True
            })
        elif paragraph.type in [ParagraphType.TITLE_1, ParagraphType.TITLE_2]:
            if paragraph.type == ParagraphType.TITLE_1:
                current_formatting.update({
                    'font_size': 18,
                    'bold': True,
                    'alignment': 'left',
                    'line_spacing': 1.2,
                })
            elif paragraph.type == ParagraphType.TITLE_2:
                current_formatting.update({
                    'font_size': 16,
                    'bold': True,
                    'alignment': 'left',
                    'line_spacing': 1.2,
                })
        
        paragraph.formatting = current_formatting

    def update_preferred_formatting(self, formatting: Dict[str, Any]) -> None:
        """Update preferred formatting for new paragraphs"""
        self.metadata['preferred_formatting'] = formatting.copy()
        self._update_modified_time()

    def remove_paragraph(self, paragraph_id: str) -> bool:
        """Remove a paragraph by ID"""
        original_count = len(self.paragraphs)
        self.paragraphs = [p for p in self.paragraphs if p.id != paragraph_id]
        
        if len(self.paragraphs) < original_count:
            self._reorder_paragraphs()
            self._update_modified_time()
            return True
        return False

    def get_paragraph(self, paragraph_id: str) -> Optional[Paragraph]:
        """Get a paragraph by ID"""
        for paragraph in self.paragraphs:
            if paragraph.id == paragraph_id:
                return paragraph
        return None

    def move_paragraph(self, paragraph_id: str, new_position: int) -> bool:
        """Move a paragraph to a new position"""
        paragraph = self.get_paragraph(paragraph_id)
        if not paragraph:
            return False
        
        # Remove from current position
        self.paragraphs = [p for p in self.paragraphs if p.id != paragraph_id]
        
        # Insert at new position
        new_position = max(0, min(new_position, len(self.paragraphs)))
        self.paragraphs.insert(new_position, paragraph)
        
        self._reorder_paragraphs()
        self._update_modified_time()
        return True

    @staticmethod
    def _calculate_word_count(content: str) -> int:
        """
        Calculate accurate word count from text content.
        
        Args:
            content: Text content to count words in
            
        Returns:
            int: Number of words
        """
        if not content or not content.strip():
            return 0
        # Split on whitespace and filter empty strings
        words = [word for word in content.split() if word.strip()]
        return len(words)

    @staticmethod
    def _count_logical_paragraphs(paragraphs: List['Paragraph']) -> int:
        """
        Count logical paragraphs following TAC methodology.
        
        TAC logical paragraphs are defined as:
        - Starting with INTRODUCTION type
        - Followed by optional ARGUMENT and CONCLUSION types
        - TITLE_1, TITLE_2, and QUOTE types don't count as logical paragraphs
        
        Args:
            paragraphs: List of Paragraph objects
            
        Returns:
            int: Number of logical paragraphs
        """
        total_paragraphs = 0
        is_in_paragraph = False
        
        for p in paragraphs:
            # Types that always start a new logical paragraph block
            if p.type == ParagraphType.INTRODUCTION:
                total_paragraphs += 1
                is_in_paragraph = True
            # Types that continue a paragraph, but only if one was already started
            elif p.type in [ParagraphType.ARGUMENT, ParagraphType.CONCLUSION]:
                if not is_in_paragraph:
                    # If we find an argument without an introduction before,
                    # count it as a separate paragraph to not lose it
                    total_paragraphs += 1
                    is_in_paragraph = False  # Reset for the next one
            # Other types (TITLE_1, TITLE_2, QUOTE) don't affect main paragraph counting
        
        return total_paragraphs

    def get_statistics(self) -> Dict[str, int]:
        """
        Get comprehensive project statistics.
        
        Returns:
            dict: Statistics including word count, character count, and paragraph counts
        """
        # Calculate word counts using static method for consistency
        total_words = sum(self._calculate_word_count(p.content) for p in self.paragraphs)
        total_chars = sum(p.get_character_count() for p in self.paragraphs)
        total_chars_no_spaces = sum(p.get_character_count(False) for p in self.paragraphs)
        
        # Count paragraphs by type
        type_counts = {}
        for paragraph_type in ParagraphType:
            type_counts[paragraph_type.value] = sum(
                1 for p in self.paragraphs if p.type == paragraph_type
            )
        
        # Count logical paragraphs using static method
        total_paragraphs = self._count_logical_paragraphs(self.paragraphs)
        
        return {
            'total_paragraphs': total_paragraphs,
            'total_words': total_words,
            'total_characters': total_chars,
            'total_characters_no_spaces': total_chars_no_spaces,
            'paragraph_types': type_counts
        }

    def update_metadata(self, metadata_updates: Dict[str, Any]) -> None:
        """Update project metadata"""
        self.metadata.update(metadata_updates)
        self._update_modified_time()

    def update_document_formatting(self, formatting_updates: Dict[str, Any]) -> None:
        """Update document formatting"""
        self.document_formatting.update(formatting_updates)
        self._update_modified_time()

    def _reorder_paragraphs(self) -> None:
        """Reorder paragraph numbers"""
        for i, paragraph in enumerate(self.paragraphs):
            paragraph.order = i
    
    def update_paragraph_order(self) -> None:
        """Public method to update paragraph order after manual reordering"""
        self._reorder_paragraphs()
        self._update_modified_time()

    def _update_modified_time(self) -> None:
        """Update the modification timestamp"""
        self.modified_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary for serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
            'metadata': self.metadata.copy(),
            'document_formatting': self.document_formatting.copy(),
            'paragraphs': [p.to_dict() for p in self.paragraphs],
            'statistics': self.get_statistics()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Create project from dictionary"""
        project = cls(
            name=data['name'],
            project_id=data.get('id')
        )
        
        project.created_at = datetime.fromisoformat(data.get('created_at', datetime.now().isoformat()))
        project.modified_at = datetime.fromisoformat(data.get('modified_at', datetime.now().isoformat()))
        
        if 'metadata' in data:
            project.metadata.update(data['metadata'])
        
        if 'document_formatting' in data:
            project.document_formatting.update(data['document_formatting'])
        
        # Load paragraphs
        if 'paragraphs' in data:
            project.paragraphs = [
                Paragraph.from_dict(p_data) for p_data in data['paragraphs']
            ]
        
        # Sort by order
        project.paragraphs.sort(key=lambda p: p.order)
        
        return project


class DocumentTemplate:
    """Template for creating new documents"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.paragraph_structure: List[ParagraphType] = []
        self.default_formatting = {}
        self.metadata_template = {}

    def create_project(self, project_name: str) -> Project:
        """Create a new project based on this template"""
        project = Project(project_name)
        
        # Apply template metadata
        project.metadata.update(self.metadata_template)
        
        # Apply template formatting
        if self.default_formatting:
            project.document_formatting.update(self.default_formatting)
        
        # Create paragraphs from structure
        for paragraph_type in self.paragraph_structure:
            project.add_paragraph(paragraph_type)
        
        return project


# Predefined templates
ACADEMIC_ESSAY_TEMPLATE = DocumentTemplate(
    name=_("Academic Essay"),
    description=_("Standard academic essay structure")
)

ACADEMIC_ESSAY_TEMPLATE.paragraph_structure = [
    ParagraphType.INTRODUCTION
]

DEFAULT_TEMPLATES = [
    ACADEMIC_ESSAY_TEMPLATE,
]