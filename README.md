# TAC Writer

<p align="center">
  <img src="https://github.com/big-comm/comm-tac-writer/blob/main/usr/share/icons/hicolor/scalable/apps/tac-writer.svg" alt="TAC Writer Logo" width="128" height="128">
</p>

<p align="center">
  <strong>Academic Writing Assistant for Continuous Argumentation Technique</strong>
</p>

<p align="center">
  <a href="https://github.com/big-comm/comm-tac-writer/releases"><img src="https://img.shields.io/badge/Version-1.2.0-blue.svg" alt="Version"/></a>
  <a href="https://github.com/big-comm/comm-tac-writer/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-GPL--3.0-green.svg" alt="License"/></a>
  <a href="https://www.gtk.org/"><img src="https://img.shields.io/badge/GTK-4.0+-orange.svg" alt="GTK Version"/></a>
  <a href="https://gnome.pages.gitlab.gnome.org/libadwaita/"><img src="https://img.shields.io/badge/libadwaita-1.0+-purple.svg" alt="libadwaita Version"/></a>
</p>

---
## Metrics

![GitHub Release](https://img.shields.io/github/v/release/narayanls/tac-writer?include_prereleases&style=flat-square)
![GitHub Issues](https://img.shields.io/github/issues/narayanls/tac-writer?style=flat-square)
![GitHub Stars](https://img.shields.io/github/stars/narayanls/tac-writer?style=flat-square)
![GitHub Forks](https://img.shields.io/github/forks/narayanls/tac-writer?style=flat-square)

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
- **Storage**: 500MB+ for project storage and backups

## Installation
### 🔍 Choose your package:

- **Arch Linux users**: Prefer the [AUR](https://aur.archlinux.org/packages/tac-writer) package. Install with `yay -S tac-writer` or `paru -S tac-writer`.
- **Debian/Ubuntu and derivative users**: Download the `.deb` file and install it with `sudo dpkg -i package-name.deb` or double-click it in your distribution's package manager (Tac Writer will be added to your menu/launcher, you can open it from there).
- **Fedora and derivative user**: Download the `.rpm`, open the terminal in the folder and install with `sudo dnf install package-name.rpm` (Tac Writer will be added to your menu/launcher, you can open it from there)

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



## How to Contribute
### Areas for Contribution

- **Bug Fixes**: Help improve stability and user experience
- **Feature Development**: Implement items from our roadmap
- **Documentation**: Improve user guides and developer docs
- **Translations**: Add support for additional languages
- **Testing**: Expand test coverage and add integration tests

### Getting Help

- **Documentation**: [GitHub Wiki](https://github.com/narayanls/tac-writer/wiki)
- **Issues**: [GitHub Issues](https://github.com/narayanls/tac-writer/issues)

### Reporting Bugs

When reporting bugs, please include:

- **System Information**: OS version, desktop environment, GTK version
- **Reproduction Steps**: Clear steps to reproduce the issue
- **Expected vs Actual Behavior**: What should happen vs what actually happens
- **Screenshots/Logs**: Visual aids or relevant log files
- **Project Files**: Sample projects that demonstrate the issue (if applicable)

## License

This project is licensed under the **GNU General Public License v3.0**. See the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <strong>Made with ❤️ by Narayan Silva</strong><br>
  </p>
