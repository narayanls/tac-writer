# TAC Writer

<p align="center">
  <img src="https://github.com/big-comm/comm-tac-writer/blob/main/usr/share/icons/hicolor/scalable/apps/tac-writer.svg" alt="TAC Writer Logo" width="128" height="128">
</p>

<p align="center">
  <strong>Academic Writing Assistant for Continuous Argumentation Technique</strong>
</p>

<p align="center">
  <a href="https://github.com/big-comm/comm-tac-writer/releases"><img src="https://img.shields.io/badge/Version-1.1.0-blue.svg" alt="Version"/></a>
  <a href="https://bigcommunity.com"><img src="https://img.shields.io/badge/BigCommunity-Platform-blue" alt="BigCommunity Platform"/></a>
  <a href="https://github.com/big-comm/comm-tac-writer/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-GPL--3.0-green.svg" alt="License"/></a>
  <a href="https://www.gtk.org/"><img src="https://img.shields.io/badge/GTK-4.0+-orange.svg" alt="GTK Version"/></a>
  <a href="https://gnome.pages.gitlab.gnome.org/libadwaita/"><img src="https://img.shields.io/badge/libadwaita-1.0+-purple.svg" alt="libadwaita Version"/></a>
</p>

---

## Overview

**TAC Writer** is a modern academic writing assistant designed to help students and researchers create structured academic texts using the **Continuous Argumentation Technique (TAC in portuguese)**. Built with GTK4 and libadwaita, TAC provides an intuitive interface for organizing thoughts, managing document structure, and producing high-quality academic content.

The Continuous Argumentation Technique emphasizes interconnected paragraphs that build upon each other, making complex topics easier to understand and arguments more compelling.

## Screenshots


![tac-new](https://github.com/user-attachments/assets/abaabe8f-b104-47dd-b917-bfcae093b9d8)


*Main editing interface with paragraph structure*

<img width="731" height="531" alt="tac-modal" src="https://github.com/user-attachments/assets/90599550-95e1-476e-9691-c57ab7cec911" />

*Welcome Tac Writer*

## Key Features

### 📝 **Structured Writing**
- **Guided Dialog Boxes Types for a better Paragraph**: Introduction, Argument, Quote, Conclusion
- **Drag-and-Drop Reordering**: Easily reorganize your document structure
- **Type-Specific Formatting**: Automatic formatting based on paragraph type
- **Template System**: Start with pre-configured academic structures

### 🎨 **Modern Interface**
- **GTK4 + libadwaita**: Native Linux desktop integration
- **Adaptive Design**: Responsive layout that works on various screen sizes
- **Dark Mode Support**: Automatic theme switching with system preferences
- **Accessibility**: Full keyboard navigation and screen reader support

### 📊 **Real-Time Analytics**
- **Live Statistics**: Word count, paragraph count
- **Progress Tracking**: Monitor your writing progress in real-time
- **Reading Time**: Estimated reading time calculation

### 💾 **Project Management**
- **Auto-Save**: Never lose your work with automatic saving
- **Project Library**: Organize and manage multiple writing projects
- **Search & Filter**: Quickly find specific projects
- **Backup System**: Automatic backup creation

### 📤 **Export Options**
- **Multiple Formats**: TXT, ODT, PDF
- **Academic Standards**: Export formats suitable for academic submission

### ⚡ **Productivity Features**
- **Pomodoro Timer**: Built-in focus timer for writing sessions
- **Spell Checking**: Real-time spell checking support
- **Keyboard Shortcuts**: Efficient workflow with customizable shortcuts
- **Distraction-Free Mode**: Focus on writing with minimal UI
- **AI Assistant**: Connect to Gemini or OpenRouter to rewrite, resume or suggest paragraphs directly from the editor (`Ctrl+Shift+I`)

## System Requirements

### Minimum Requirements
- **OS**: Arch Linux, Manjaro, BigCommunity, or Arch-based distributions
- **Python**: 3.9+
- **GTK**: 4.0+
- **libadwaita**: 1.0+
- **Memory**: 2GB RAM
- **Storage**: 100MB available space

### Recommended
- **Memory**: 4GB+ RAM for large documents
- **Display**: 1920x1080 or higher resolution
- **Storage**: 1GB+ for project storage and backups

## Installation

### Option 1: Package Manager (Recommended)

For Arch-based distributions, add the BigCommunity repository and install via pacman:

#### 1. Add Repository Key
```bash
sudo pacman-key --recv-keys 1EA0CEEEB09B44A3
sudo pacman-key --lsign-key 1EA0CEEEB09B44A3
```

#### 2. Add Repository
Edit `/etc/pacman.conf` and add:
```ini
[community-stable]
SigLevel = PackageRequired
Server = https://repo.communitybig.org/stable/$arch
```

#### 3. Install Package
```bash
sudo pacman -Sy comm-tac-writer
```

### Option 2: Manual Installation

#### Prerequisites
```bash
# Install system dependencies
sudo pacman -Sy python gtk4 libadwaita python-gobject python-cairo

# Optional: Development tools
sudo pacman -S python-pip git base-devel
```

#### Install from Source
```bash
# Clone repository
git clone https://github.com/big-comm/comm-tac-writer.git
cd comm-tac-writer

# Install Python dependencies
pip install --user -r requirements.txt

# Run application
python main.py
```

## Usage

### Getting Started

1. **Launch TAC Writer**
   ```bash
   tac-writer  # If installed via package manager
   # OR
   python main.py  # If running from source
   ```

2. **Create Your First Project**
   - Click "Start" on the Academic Essay template
   - Enter your project name and details
   - Begin writing with guided paragraph types

3. **Structure Your Document**
   - Add different paragraph types using the toolbar
   - Use drag-and-drop to reorder paragraphs
   - Apply consistent formatting across your document

4. **Export and Share**
   - Use Ctrl+E to open export dialog
   - Choose your preferred format (ODT, PDF, TXT, HTML)
   - Configure export settings and metadata

### AI Assistant

1. Open **Preferences ▸ AI Assistant**, enable the feature and choose your provider (Gemini ou OpenRouter).
2. Informe o **Model ID** e a **API key** correspondente (OpenRouter também aceita Referer e Título opcionais para ranking).
3. No editor, posicione o cursor ou selecione o trecho desejado e pressione `Ctrl+Shift+I` (ou clique no avatar da barra superior).
4. Descreva como quer melhorar o parágrafo, escolha uma sugestão rápida se quiser e envie.  
5. Analise o retorno: copie, insira diretamente no texto ou aproveite as sugestões adicionais.

### Writing with TAC Methodology

The **Continuous Argumentation Technique** follows this structure:

- **Introduction**: Summarizes the topic to be addressed
- **Argumentation**: Develops the main points and evidence
- **Quote**: Supports arguments with relevant citations
- **Argumentative Resumption**: Links back to previous arguments
- **Conclusion**: Synthesizes and closes the presented ideas

### Keyboard Shortcuts

| Shortcut | Action | Description |
|----------|--------|-------------|
| `Ctrl+N` | New Project | Create a new writing project |
| `Ctrl+O` | Open Project | Open an existing project |
| `Ctrl+S` | Save Project | Save current project |
| `Ctrl+E` | Export Project | Export to various formats |
| `Ctrl+,` | Preferences | Open application settings |
| `Ctrl+Z` | Undo | Undo last action |
| `Ctrl+Shift+Z` | Redo | Redo last undone action |
| `Ctrl+Alt+I` | Insert Image | Open the insert image dialog |
| `Ctrl+Shift+I` | Ask AI Assistant | Open the AI prompt dialog |
| `Ctrl+Q` | Quit | Exit application |
| `F11` | Focus Mode | Toggle distraction-free writing |

## Configuration

TAC Writer follows XDG Base Directory specification:

- **Configuration**: `~/.config/tac/`
- **User Data**: `~/.local/share/tac/`
- **Cache**: `~/.cache/tac/`
- **Projects**: `~/.local/share/tac/projects/`

### Customization Options

- **Themes**: Light, dark, or system preference
- **Fonts**: Choose from installed system fonts
- **Templates**: Create custom document templates
- **Export Settings**: Configure default export formats
- **Shortcuts**: Customize keyboard shortcuts

## Architecture

```
tac/
├── main.py              # Application entry point
├── application.py       # Main application controller
├── requirements.txt     # Python dependencies
├── core/               # Core business logic
│   ├── models.py       # Data models (Project, Paragraph)
│   ├── services.py     # Business services (ProjectManager, ExportService)
│   └── config.py       # Configuration management
├── ui/                 # User interface components
│   ├── main_window.py  # Primary application window
│   ├── components.py   # Reusable UI components
│   └── dialogs.py      # Dialog windows and forms
├── utils/              # Utility functions
│   ├── helpers.py      # Text processing, validation
│   └── i18n.py         # Internationalization support
└── data/               # Application data
    ├── templates/      # Document templates
    └── icons/          # Application icons
```

## Development

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/big-comm/comm-tac-writer.git
cd comm-tac-writer

# Install development dependencies
sudo pacman -S python-pytest python-black python-flake8 python-mypy

# Install Python development packages
pip install --user pre-commit black flake8 mypy pytest

# Set up pre-commit hooks
pre-commit install
```

### Code Standards

- **Python Style**: PEP 8 compliance, formatted with Black
- **Type Hints**: Use type annotations for better code clarity
- **Documentation**: Docstrings for all public functions and classes
- **Testing**: Unit tests for core functionality
- **Commits**: Follow Conventional Commits specification

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=src

# Run specific test file
python -m pytest tests/test_models.py
```

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### How to Contribute

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Areas for Contribution

- **Bug Fixes**: Help improve stability and user experience
- **Feature Development**: Implement items from our roadmap
- **Documentation**: Improve user guides and developer docs
- **Translations**: Add support for additional languages
- **Testing**: Expand test coverage and add integration tests

### Getting Help

- **Documentation**: [GitHub Wiki](https://github.com/narayanls/tac-writer/wiki)
- **Community**: [BigCommunity Telegram](https://t.me/+kmobYSt2PMhhZTFh)
- **Issues**: [GitHub Issues](https://github.com/big-comm/comm-tac-writer/issues)

### Reporting Bugs

When reporting bugs, please include:

- **System Information**: OS version, desktop environment, GTK version
- **Reproduction Steps**: Clear steps to reproduce the issue
- **Expected vs Actual Behavior**: What should happen vs what actually happens
- **Screenshots/Logs**: Visual aids or relevant log files
- **Project Files**: Sample projects that demonstrate the issue (if applicable)

## License

This project is licensed under the **GNU General Public License v3.0**. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **GNOME Project** for GTK4 and libadwaita framework
- **Python GObject** community for excellent Python bindings
- **BigCommunity** platform for hosting and support
- **Academic Community** for feedback and testing
- **Contributors** who help improve TAC Writer

## Citation

If you use TAC Writer in academic work, please cite:

```bibtex
@software{tac_writer,
  title = {TAC Writer: Academic Writing Assistant for Continuous Argumentation Technique},
  author = {BigCommunity Development Team},
  year = {2024},
  url = {https://github.com/big-comm/comm-tac-writer},
  version = {1.1.0}
}
```

---

<p align="center">
  <strong>Made with ❤️ by the BigCommunity Team</strong><br>
  <a href="https://bigcommunity.com">BigCommunity.com</a> • <a href="https://github.com/big-comm">GitHub</a>
</p>
