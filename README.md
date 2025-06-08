# TAC - Text Analysis and Creation

![TAC Logo](https://via.placeholder.com/128x128/4a90e2/ffffff?text=TAC)

**TAC** is a modern academic writing assistant built with GTK4 and libadwaita, designed specifically for creating structured academic texts with guided paragraph types.

## ✨ Features

- **🎯 Structured Writing**: Guided paragraph types (Introduction, Topic Sentence, Argument, Quote, Conclusion)
- **📝 Modern Interface**: Clean, responsive design using GTK4 + libadwaita
- **📊 Real-time Statistics**: Word count, character count, reading time estimation
- **💾 Project Management**: Save, load, and organize multiple writing projects
- **📤 Multiple Export Formats**: TXT, HTML, ODT (LibreOffice), RTF
- **🎨 Customizable Formatting**: Font selection, sizing, and paragraph styling
- **🌙 Dark Mode Support**: Automatic theme switching with system preferences
- **⚡ Auto-save**: Never lose your work with automatic project saving

## 🖥️ System Requirements

- **Operating System**: Arch Linux, Manjaro, BigCommunity, or other Arch-based distributions
- **Desktop Environment**: Any modern DE with GTK4 support (GNOME, KDE, Cinnamon, etc.)
- **Python**: 3.9 or higher
- **GTK**: 4.0 or higher
- **libadwaita**: 1.0 or higher

## 📦 Installation

### Prerequisites (Arch/Manjaro/BigCommunity)

First, install the required system packages:

```bash
# Update system
sudo pacman -Syu

# Install core dependencies
sudo pacman -S python gtk4 libadwaita python-gobject python-cairo

# Optional: Install development tools
sudo pacman -S python-pip git base-devel
```

### Install TAC

1. **Clone the repository**:
   ```bash
   git clone https://github.com/user/tac.git
   cd tac
   ```

2. **Install Python dependencies**:
   ```bash
   pip install --user -r requirements.txt
   ```

3. **Make executable**:
   ```bash
   chmod +x tac.py
   ```

### Optional: System Installation

To install TAC system-wide:

```bash
# Copy to system applications
sudo cp -r tac/ /opt/tac/

# Create desktop entry
sudo tee /usr/share/applications/tac.desktop << EOF
[Desktop Entry]
Name=TAC
Comment=Text Analysis and Creation
Exec=/opt/tac/tac.py
Icon=document-edit-symbolic
Type=Application
Categories=Office;WordProcessor;Education;
Keywords=writing;academic;text;analysis;creation;
StartupNotify=true
EOF

# Create system launcher
sudo tee /usr/local/bin/tac << 'EOF'
#!/bin/bash
cd /opt/tac
python3 tac.py "$@"
EOF
sudo chmod +x /usr/local/bin/tac
```

## 🚀 Usage

### Running TAC

From the project directory:
```bash
python3 tac.py
```

Or if installed system-wide:
```bash
tac
```

### Basic Workflow

1. **Create a New Project**:
   - Click "Start" on a template or use Ctrl+N
   - Enter project name and details
   - Choose from academic templates

2. **Write Your Content**:
   - Add different paragraph types using the toolbar
   - Use the guided structure for academic writing
   - Format text with the built-in tools

3. **Save and Export**:
   - Projects auto-save as you work
   - Export to various formats (TXT, HTML, ODT, RTF)
   - Share or submit your completed work

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New Project |
| `Ctrl+O` | Open Project |
| `Ctrl+S` | Save Project |
| `Ctrl+E` | Export Project |
| `Ctrl+,` | Preferences |
| `Ctrl+Q` | Quit Application |

## 🏗️ Project Structure

```
tac/
├── tac.py              # Main entry point
├── application.py      # Application class
├── requirements.txt    # Python dependencies
├── README.md          # This file
├── core/              # Core functionality
│   ├── __init__.py
│   ├── config.py      # Configuration management
│   ├── models.py      # Data models
│   └── services.py    # Business logic
├── ui/                # User interface
│   ├── __init__.py
│   ├── main_window.py # Main window
│   ├── components.py  # UI components
│   └── dialogs.py     # Dialog windows
└── utils/             # Utilities
    ├── __init__.py
    └── helpers.py     # Helper functions
```

## 🎨 Themes and Customization

TAC follows your system theme automatically and supports:

- **Light/Dark Mode**: Switches with system preference
- **Accent Colors**: Uses system accent colors
- **Font Customization**: Choose from system fonts
- **Custom Templates**: Create your own document templates

## 🔧 Configuration

TAC stores configuration in XDG-compliant directories:

- **Config**: `~/.config/tac/`
- **Data**: `~/.local/share/tac/`
- **Cache**: `~/.cache/tac/`

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### Development Setup

```bash
# Clone repository
git clone https://github.com/user/tac.git
cd tac

# Install development dependencies
sudo pacman -S python-pytest python-black python-flake8 python-mypy

# Install pre-commit hooks (optional)
pip install --user pre-commit
pre-commit install
```

### Code Style

- **Python**: Follow PEP 8, use `black` for formatting
- **Comments**: English only, clear and concise
- **UI Strings**: Translatable (future i18n support)
- **Git Commits**: Conventional commits format

### Testing

```bash
# Run tests
python -m pytest

# Type checking
mypy tac/

# Code formatting
black tac/

# Linting
flake8 tac/
```

## 🐛 Bug Reports

Found a bug? Please report it on our [GitHub Issues](https://github.com/user/tac/issues) with:

- **System info**: OS, DE, GTK version
- **Steps to reproduce**: Clear, numbered steps
- **Expected vs actual behavior**
- **Screenshots** (if applicable)

## 📋 Roadmap

- [ ] **Internationalization** (i18n) support
- [ ] **Plugin system** for custom paragraph types
- [ ] **Collaborative editing** features
- [ ] **Advanced formatting** (tables, images, citations)
- [ ] **Integration** with reference managers
- [ ] **Export to LaTeX** and academic formats
- [ ] **Grammar and style checking**

## 📄 License

This project is licensed under the **GNU General Public License v3.0**.

See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **GNOME Team** for GTK4 and libadwaita
- **Python GObject** community
- **Arch Linux** and **Manjaro** communities
- **BigCommunity** for inspiration and support

## 📞 Support

- **Documentation**: [GitHub Wiki](https://github.com/user/tac/wiki)
- **Community**: [Discussions](https://github.com/user/tac/discussions)
- **Issues**: [Bug Tracker](https://github.com/user/tac/issues)

---

<div align="center">

**Made with ❤️ for the academic writing community**

[Website](https://github.com/user/tac) • [Issues](https://github.com/user/tac/issues) • [Discussions](https://github.com/user/tac/discussions)

</div>