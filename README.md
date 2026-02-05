# TAC Writer

<p align="center">
  <img src="https://github.com/big-comm/comm-tac-writer/blob/main/usr/share/icons/hicolor/scalable/apps/tac-writer.svg" alt="Logo do TAC Writer" width="128" height="128">
</p>

<p align="center">
  <strong>Assistente de Escrita Acadêmica para a Técnica da Argumentação Contínua</strong>
</p>

<p align="center">
  <a href="https://github.com/big-comm/comm-tac-writer/releases"><img src="https://img.shields.io/badge/Version-1.2.8-blue.svg" alt="Versão"/></a>
  <a href="https://github.com/big-comm/comm-tac-writer/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-GPL--3.0-green.svg" alt="Licença"/></a>
  <a href="https://www.gtk.org/"><img src="https://img.shields.io/badge/GTK-4.0+-orange.svg" alt="Versão GTK"/></a>
  <a href="https://gnome.pages.gitlab.gnome.org/libadwaita/"><img src="https://img.shields.io/badge/libadwaita-1.0+-purple.svg" alt="Versão libadwaita"/></a>
</p>

---
## Métricas
![Downloads](https://img.shields.io/github/downloads/narayanls/tac-writer/total?style=flat-square&color=D98E04)
![Lançamento GitHub](https://img.shields.io/github/v/release/narayanls/tac-writer?include_releases&style=flat-square)
![Problemas GitHub](https://img.shields.io/github/issues/narayanls/tac-writer?style=flat-square)
![Estrelas GitHub](https://img.shields.io/github/stars/narayanls/tac-writer?style=flat-square)
![Forks GitHub](https://img.shields.io/github/forks/narayanls/tac-writer?style=flat-square)

---
## Visão Geral

O **TAC Writer** é um assistente de escrita acadêmica moderno projetado para ajudar estudantes e pesquisadores a criar textos acadêmicos estruturados usando a **Técnica da Argumentação Contínua (TAC)**. Construído com GTK4 e libadwaita, o TAC oferece uma interface intuitiva para organizar pensamentos, gerenciar a estrutura do documento e produzir conteúdo acadêmico de alta qualidade.

A Técnica da Argumentação Contínua enfatiza parágrafos interconectados que se baseiam uns nos outros, tornando tópicos complexos mais fáceis de entender e argumentos mais convincentes.

## Capturas de Tela

*Interface principal de edição com estrutura de parágrafos*
<img width="814" height="491" alt="tac-main-dark" src="https://github.com/user-attachments/assets/91a345f5-f3c7-46b4-bf17-5a193f1113ad" />

<img width="814" height="491" alt="tac-main-light" src="https://github.com/user-attachments/assets/74c4a7d7-5ef6-4e91-820c-f7148d92f62f" />


----------------------

*Tela de boas-vindas do Tac Writer*

<img width="550" height="450" alt="tac-welcome" src="https://github.com/user-attachments/assets/de3520bf-30bd-4ad6-b520-01926652b44b" />



## Principais Recursos

### 📝 **Escrita Estruturada**
- **Caixas de Diálogo Guiadas para um Parágrafo melhor**: Introdução, Argumento, Citação, Conclusão
- **Reordenação por Arrastar e Soltar**: Reorganize facilmente a estrutura do seu documento
- **Formatação Específica por Tipo**: Formatação automática baseada no tipo de parágrafo
- **Sistema de Modelos**: Comece com estruturas acadêmicas pré-configuradas

### 🎨 **Interface Moderna**
- **GTK4 + libadwaita**: Integração nativa com desktop Linux
- **Design Adaptativo**: Layout responsivo que funciona em vários tamanhos de tela
- **Suporte a Modo Escuro**: Troca automática de tema com as preferências do sistema
- **Acessibilidade**: Navegação completa por teclado e suporte a leitor de tela

### 📊 **Análises em Tempo Real**
- **Estatísticas ao Vivo**: Contagem de palavras, contagem de parágrafos
- **Acompanhamento de Progresso**: Monitore seu progresso de escrita em tempo real
- **Tempo de Leitura**: Cálculo estimado do tempo de leitura

### 💾 **Gerenciamento de Projetos**
- **Salvamento Automático**: Nunca perca seu trabalho com o salvamento automático
- **Biblioteca de Projetos**: Organize e gerencie múltiplos projetos de escrita
- **Pesquisar e Filtrar**: Encontre rapidamente projetos específicos
- **Sistema de Backup**: Criação automática de backup

### 📤 **Opções de Exportação**
- **Múltiplos Formatos**: TXT, ODT, PDF
- **Padrões Acadêmicos**: Formatos de exportação adequados para submissão acadêmica

### ⚡ **Recursos de Produtividade**
- **Temporizador Pomodoro**: Temporizador de foco integrado para sessões de escrita
- **Verificação Ortográfica**: Suporte à verificação ortográfica em tempo real
- **Atalhos de Teclado**: Fluxo de trabalho eficiente com atalhos personalizáveis
- **Modo Livre de Distrações**: Foque na escrita com interface mínima
- **Assistente de IA**: Conecte-se ao Gemini ou OpenRouter para reescrever, resumir ou sugerir parágrafos diretamente do editor (`Ctrl+Shift+I`)

## Requisitos do Sistema

### Requisitos Mínimos
- **SO**: Qualquer SO Linux
- **Python**: 3.11+
- **GTK**: 3.0+
- **libadwaita**: 1.0+
- **Memória**: 2GB RAM
- **CPU**: 2 núcleos / 2 threads
- **Armazenamento**: 400MB de espaço disponível

### Recomendado
- **Memória**: 4GB+ RAM para documentos grandes
- **CPU**: 4 núcleos / 4 threads
- **Armazenamento**: 500MB+ para armazenamento de projetos e backups

## Instalação
### 🔍 Escolha seu pacote:

- **Usuários do Arch Linux**: Prefira o pacote do [AUR](https://aur.archlinux.org/packages/tac-writer). Instale com `yay -S tac-writer` ou `paru -S tac-writer`.
- **Usuários do Debian/Ubuntu e derivados**: Baixe o arquivo `.deb` e instale com `sudo dpkg -i nome-do-pacote.deb` ou clique duas vezes nele no gerenciador de pacotes da sua distribuição (O Tac Writer será adicionado ao seu menu/lançador, você pode abri-lo de lá).
- **Usuários do Fedora e derivados**: Baixe o `.rpm`, abra o terminal na pasta e instale com `sudo dnf install nome-do-pacote.rpm` (O Tac Writer será adicionado ao seu menu/lançador, você pode abri-lo de lá)

### Assistente de IA

1. Abra **Preferências ▸ Assistente de IA**, habilite o recurso e escolha seu provedor (Gemini ou OpenRouter).
2. Informe o **Model ID** e a **API key** correspondente (OpenRouter também aceita Referer e Título opcionais para ranking).
3. Abra o assistente com `Ctrl+Shift+I` (ou clique no avatar da barra superior).
4. Anexe o arquivo pdf que será revisado.  

### Escrevendo com a Metodologia TAC

A **Técnica de Argumentação Contínua** segue esta estrutura:

- **Introdução**: Resume o tópico a ser abordado
- **Argumentação**: Desenvolve os pontos principais e evidências
- **Citação**: Apoia argumentos com citações relevantes
- **Retomada Argumentativa**: Vincula-se aos argumentos anteriores
- **Conclusão**: Sintetiza e encerra as ideias apresentadas

### Atalhos de Teclado

| Atalho | Ação | Descrição |
|----------|--------|-------------|
| `Ctrl+N` | Novo Projeto | Criar um novo projeto de escrita |
| `Ctrl+O` | Abrir Projeto | Abrir um projeto existente |
| `Ctrl+S` | Salvar Projeto | Salvar o projeto atual |
| `Ctrl+E` | Exportar Projeto | Exportar para vários formatos |
| `Ctrl+,` | Preferências | Abrir configurações do aplicativo |
| `Ctrl+Z` | Desfazer | Desfazer a última ação |
| `Ctrl+Shift+Z` | Refazer | Refazer a última ação desfeita |
| `Ctrl+Alt+I` | Inserir Imagem | Abrir o diálogo de inserção de imagem |
| `Ctrl+Shift+I` | Revisão de texto por IA | Abrir o diálogo de prompt de IA |
| `Ctrl+Q` | Sair | Sair do aplicativo |
| `F11` | Modo Foco | Alternar escrita livre de distrações |

## Configuração

O TAC Writer segue a especificação XDG Base Directory:

- **Configuração**: `~/.config/tac/`
- **Dados do Usuário**: `~/.local/share/tac/`
- **Cache**: `~/.cache/tac/`
- **Projetos**: `~/.local/share/tac/projects/`


## Como Contribuir
### Áreas para Contribuição

- **Correção de Bugs**: Ajude a melhorar a estabilidade e a experiência do usuário
- **Desenvolvimento de Recursos**: Implemente itens do nosso roteiro (roadmap)
- **Documentação**: Melhore guias de usuário e documentos de desenvolvedor
- **Testes**: Expanda a cobertura de testes e adicione testes de integração

### Obtendo Ajuda

- **Documentação**: [Wiki do GitHub](https://github.com/narayanls/tac-writer/wiki)
- **Problemas (Issues)**: [Issues do GitHub](https://github.com/narayanls/tac-writer/issues)

### Relatando Bugs

Ao relatar bugs, por favor inclua:

- **Informações do Sistema**: Versão do SO, ambiente de desktop, versão do GTK e versão do Python
- **Passos para Reprodução**: Passos claros para reproduzir o problema
- **Comportamento Esperado vs Real**: O que deveria acontecer vs o que realmente acontece
- **Capturas de tela/Logs**: Auxílios visuais ou arquivos de log relevantes
- **Arquivos de Projeto**: Projetos de exemplo que demonstram o problema (se aplicável)

## Licença

Este projeto está licenciado sob a **GNU General Public License v3.0**. Veja o arquivo [LICENSE](LICENSE) para detalhes.

---

<p align="center">
  <strong>Feito com ❤️ por Narayan Silva</strong><br>
  </p>
