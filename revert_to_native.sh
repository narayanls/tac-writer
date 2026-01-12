#!/bin/bash

echo "=== Iniciando reversão de tac-writer para tac-writer ==="

# 1. RENOMEAR ARQUIVOS FÍSICOS
# Verifica se os arquivos existem antes de tentar mover para evitar erros

# Renomear o arquivo .desktop
if [ -f "usr/share/applications/tac-writer.desktop" ]; then
    echo "Renomeando .desktop..."
    mv "usr/share/applications/tac-writer.desktop" "usr/share/applications/tac-writer.desktop"
fi

# Renomear o ícone principal do aplicativo
if [ -f "usr/share/icons/hicolor/scalable/apps/tac-writer.svg" ]; then
    echo "Renomeando ícone do app..."
    mv "usr/share/icons/hicolor/scalable/apps/tac-writer.svg" "usr/share/icons/hicolor/scalable/apps/tac-writer.svg"
fi

# Renomear o arquivo AppStream/Metainfo
# Nota: Ajustando também o nome longo do metainfo se necessário
if [ -f "usr/share/metainfo/tac-writer.metainfo.xml" ]; then
    echo "Renomeando metainfo..."
    mv "usr/share/metainfo/tac-writer.metainfo.xml" "usr/share/metainfo/tac-writer.metainfo.xml"
fi

# 2. SUBSTITUIR CONTEÚDO NOS ARQUIVOS (TEXTO)
echo "Substituindo ocorrências de texto nos arquivos..."

# Encontra todos os arquivos (excluindo .git, __pycache__, imagens e binários de tradução .mo)
# E executa o sed para substituir as strings.

# Substituição 1: tac-writer -> tac-writer
grep -rIl "tac-writer" . | \
    grep -vE "\.git|\.png$|\.jpg$|\.mo$|\.pyc$|__pycache__" | \
    xargs sed -i 's/org\.tac\.writer/tac-writer/g'

# Substituição 2: tac-writer -> tac-writer
# (Caso tenha sobrado algo no arquivo metainfo ou referências antigas)
grep -rIl "tac-writer" . | \
    grep -vE "\.git|\.png$|\.jpg$|\.mo$|\.pyc$|__pycache__" | \
    xargs sed -i 's/io\.github\.narayanls_tacwriter/tac-writer/g'

# 3. LIMPEZA
echo "Limpando caches do Python (__pycache__)..."
find . -type d -name "__pycache__" -exec rm -rf {} +

echo "=== Concluído! ==="
echo "Verifique se o arquivo 'usr/share/applications/tac-writer.desktop' contém 'Icon=tac-writer' e 'Exec=tac-writer'."
