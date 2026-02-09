#!/bin/bash

# ==========================================
# LEITURA DA DISTRIBUIÇÃO (ANTECIPADA)
# ==========================================
if [ -f /etc/os-release ]; then . /etc/os-release; else echo "Erro: /etc/os-release não encontrado."; exit 1; fi
DISTRO_ID=$(echo "$ID" | tr '[:upper:]' '[:lower:]')
DISTRO_LIKE_ID=$(echo "$ID_LIKE" | tr '[:upper:]' '[:lower:]')
PRETTY_NAME_LOWER=$(echo "$PRETTY_NAME" | tr '[:upper:]' '[:lower:]')

# ==========================================
# CONFIGURAÇÕES GERAIS
# ==========================================
APP_NAME="tac-writer"
GITHUB_USER="narayanls"
VERSION_TAG="v1.2.8-7"     # Tag da Release no Github
VERSION_FILE="1.2.8-7"     # Versão no nome do arquivo
DEBUG_MODE="1"             # 1 = Ativa logs detalhados e não apaga temp imediatamente

# --- LÓGICA DE DEPENDÊNCIAS SUSE (Leap/Regata vs Tumbleweed) ---
SUSE_BASE="typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 libadwaita-1-0 gettext-runtime liberation-fonts myspell-pt_BR myspell-en_US myspell-es"

if [[ "$PRETTY_NAME_LOWER" == *"leap"* ]] || [[ "$DISTRO_ID" == *"regata"* ]]; then
    PY_PREFIX="python311"
else
    PY_PREFIX="python313"
fi

SUSE_DEPS="$SUSE_BASE ${PY_PREFIX} ${PY_PREFIX}-gobject ${PY_PREFIX}-reportlab ${PY_PREFIX}-pygtkspellcheck ${PY_PREFIX}-pyenchant ${PY_PREFIX}-Pillow ${PY_PREFIX}-requests ${PY_PREFIX}-pypdf ${PY_PREFIX}-PyLaTeX ${PY_PREFIX}-dropbox "

# Definição dos Arquivos
FILE_DEB="${APP_NAME}_${VERSION_FILE}_amd64.deb"
FILE_RPM="${APP_NAME}-${VERSION_FILE}-1.x86_64.rpm"

# URLs
BASE_URL="https://github.com/$GITHUB_USER/$APP_NAME/releases/download/$VERSION_TAG"
URL_DEB="$BASE_URL/$FILE_DEB"
URL_RPM="$BASE_URL/$FILE_RPM"

# Diretórios
TEMP_DIR="/tmp/$APP_NAME-install"
mkdir -p "$TEMP_DIR"
USER_DOWNLOADS=$(xdg-user-dir DOWNLOAD 2>/dev/null || echo "$HOME/Downloads")

# Logs de Debug
WGET_LOG="$TEMP_DIR/wget_debug.log"
INSTALL_LOG="$TEMP_DIR/install_debug.log"
BUILD_LOG="$TEMP_DIR/build_appimage.log"
FLAG_DONE="$TEMP_DIR/process_done"
FLAG_CLOSE="$TEMP_DIR/close_terminal"

# ==========================================
# PREPARAÇÃO E AUTO-INSTALAÇÃO DO ZENITY
# ==========================================
ensure_zenity() {
    if ! command -v zenity &> /dev/null; then
        echo "Aviso: Zenity não encontrado. Tentando instalar..."
        INSTALL_ZENITY_CMD=""

        if [[ "$DISTRO_ID" == *"arch"* ]] || [[ "$DISTRO_LIKE_ID" == *"arch"* ]] || [[ "$DISTRO_ID" == "cachyos" ]]; then
            INSTALL_ZENITY_CMD="sudo pacman -S --noconfirm zenity"
        elif [[ "$DISTRO_ID" == *"debian"* ]] || [[ "$DISTRO_LIKE_ID" == *"debian"* ]] || [[ "$DISTRO_ID" == *"ubuntu"* ]] || [[ "$DISTRO_LIKE_ID" == *"ubuntu"* ]]; then
            INSTALL_ZENITY_CMD="sudo apt-get update && sudo apt-get install -y zenity"
        elif [[ "$DISTRO_ID" == *"fedora"* ]] || [[ "$DISTRO_LIKE_ID" == *"fedora"* ]]; then
            INSTALL_ZENITY_CMD="sudo dnf install -y zenity"
        elif [[ "$DISTRO_ID" == *"suse"* ]] || [[ "$DISTRO_LIKE_ID" == *"suse"* ]] || [[ "$DISTRO_ID" == *"regata"* ]]; then
            INSTALL_ZENITY_CMD="sudo zypper --non-interactive install -y zenity"
        fi

        if [ -n "$INSTALL_ZENITY_CMD" ]; then
            eval "$INSTALL_ZENITY_CMD"
        else
            echo "Erro: Não foi possível instalar o Zenity automaticamente."
            exit 1
        fi
    fi
}
ensure_zenity

# ==========================================
# FUNÇÕES E CONTROLE
# ==========================================

cleanup() {
    touch "$FLAG_CLOSE"
    sleep 0.5
    # Só apaga o diretório temporário se Debug estiver desligado
    if [ "$DEBUG_MODE" != "1" ]; then
        rm -rf "$TEMP_DIR"
    else
        echo "DEBUG ATIVO: Arquivos mantidos em $TEMP_DIR"
    fi
    exit
}
trap cleanup SIGINT SIGTERM EXIT

show_error() {
    zenity --error --text="$1" --title="Erro Fatal" --width=400
    exit 1
}

# Mostra log em janela rolável
show_debug_log() {
    local LOG_FILE="$1"
    local TITLE="$2"
    if [ -f "$LOG_FILE" ]; then
        zenity --text-info --filename="$LOG_FILE" --title="$TITLE" --width=700 --height=500 --wrap
    else
        zenity --error --text="Arquivo de log não encontrado: $LOG_FILE"
    fi
}

detect_terminal() {
    TERM_CMD="x-terminal-emulator -e"
    if ! command -v x-terminal-emulator &> /dev/null; then
        if command -v ashyterm &> /dev/null; then TERM_CMD="ashyterm -e";
        elif command -v zashterminal &> /dev/null; then TERM_CMD="zashterminal -e";
        elif command -v konsole &> /dev/null; then TERM_CMD="konsole -e";
        elif command -v gnome-terminal &> /dev/null; then TERM_CMD="gnome-terminal --";
        elif command -v alacritty &> /dev/null; then TERM_CMD="alacritty -e";
        elif command -v kitty &> /dev/null; then TERM_CMD="kitty -e";
        elif command -v xterm &> /dev/null; then TERM_CMD="xterm -e";
        else TERM_CMD=""; fi
    fi
}
detect_terminal

run_external_process() {
    local SCRIPT_PATH="$1"
    local TITLE="$2"

    rm -f "$FLAG_DONE" "$FLAG_CLOSE"

    cat <<EOF >> "$SCRIPT_PATH"

EXIT_CODE=\$?
echo ""
if [ \$EXIT_CODE -eq 0 ]; then
    echo "SUCESSO! Finalizando..."
    echo "success" > "$FLAG_DONE"
else
    echo "ERRO! Verifique as mensagens acima."
    echo "error" > "$FLAG_DONE"
    echo "Pressione ENTER para fechar (Modo Debug)..."
    read
fi

while [ ! -f "$FLAG_CLOSE" ]; do sleep 0.5; done
exit \$EXIT_CODE
EOF

    chmod +x "$SCRIPT_PATH"
    $TERM_CMD "$SCRIPT_PATH" &

    (
        echo "0"; echo "# Inicializando..."
        sleep 1
        while [ ! -f "$FLAG_DONE" ]; do
            echo "# Processando... Acompanhe no terminal."; sleep 1
        done
        echo "100"
    ) | zenity --progress --title="$TITLE" --pulsate --auto-close --width=400

    if [ -f "$FLAG_DONE" ]; then
        STATUS=$(cat "$FLAG_DONE")
        if [ "$STATUS" == "success" ]; then
            touch "$FLAG_CLOSE"
            sleep 0.5
            # Se for instalação normal, mostra msg, se for AppImage tratamos depois
        else
            zenity --error --text="Ocorreu um erro no terminal." --width=400
            touch "$FLAG_CLOSE"
            exit 1
        fi
    else
        touch "$FLAG_CLOSE"
    fi
    sleep 0.5
}

# ==========================================
# NOVA FUNÇÃO: BUILDER APPIMAGE
# ==========================================
build_appimage_local() {
    cd "$TEMP_DIR" || exit 1
    rm -rf AppDir source.deb

    # 1. Download DEB
    echo "10"; echo "# Baixando DEB fonte..."
    if ! wget -O "source.deb" "$URL_DEB" -q; then
        echo "Erro ao baixar DEB" >> "$BUILD_LOG"; exit 1
    fi

    # 2. Extração
    echo "30"; echo "# Extraindo arquivos..."
    mkdir -p AppDir
    ar x source.deb
    if [ -f data.tar.xz ]; then tar xf data.tar.xz -C AppDir/
    elif [ -f data.tar.zst ]; then tar --use-compress-program=zstd -xf data.tar.zst -C AppDir/
    else tar xf data.tar.* -C AppDir/ 2>/dev/null; fi

    # 3. Metadados
    echo "50"; echo "# Configurando Metadados..."
    find AppDir -name "*.desktop" -exec cp {} AppDir/ \;
    ICON_SRC=$(find AppDir/usr/share/icons -name "*$APP_NAME.png" -o -name "*$APP_NAME.svg" | head -n 1)
    if [ -z "$ICON_SRC" ]; then ICON_SRC=$(find AppDir/usr/share/icons -name "*.png" | head -n 1); fi
    [ -n "$ICON_SRC" ] && cp "$ICON_SRC" AppDir/ || touch AppDir/icon.png

    # 4. PATCH: Caminho Relativo Python
    echo "60"; echo "# Aplicando Patch de Caminho..."
    LAUNCHER="AppDir/usr/bin/$APP_NAME"
    mkdir -p "$(dirname "$LAUNCHER")"

    cat <<EOF > "$LAUNCHER"
#!/bin/bash
SCRIPT_DIR="\$(dirname "\$(readlink -f "\${0}")")"
APP_ROOT="\$(dirname "\$(dirname "\$SCRIPT_DIR")")"
exec python3 "\$APP_ROOT/usr/share/$APP_NAME/main.py" "\$@"
EOF
    chmod +x "$LAUNCHER"

    # 5. AppRun
    echo "70"; echo "# Criando AppRun..."
    cat <<EOF > AppDir/AppRun
#!/bin/bash
HERE="\$(dirname "\$(readlink -f "\${0}")")"
export PATH="\${HERE}/usr/bin:\${HERE}/usr/sbin:\${PATH}"
export LD_LIBRARY_PATH="\${HERE}/usr/lib:\${HERE}/usr/lib/x86_64-linux-gnu:\${LD_LIBRARY_PATH}"
export XDG_DATA_DIRS="\${HERE}/usr/share:\${XDG_DATA_DIRS}"
export PYTHONPATH="\${HERE}/usr/lib/python3/dist-packages:\${PYTHONPATH}"
EXEC=\$(grep -e '^Exec=' "\${HERE}"/*.desktop | head -n 1 | cut -d "=" -f 2 | cut -d " " -f 1)
exec "\$EXEC" "\$@"
EOF
    chmod +x AppDir/AppRun

    # 6. Build
    echo "80"; echo "# Empacotando..."
    TOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    if [ ! -f appimagetool ]; then wget -O appimagetool "$TOOL_URL" -q && chmod +x appimagetool; fi
    ARCH=x86_64 ./appimagetool --no-appstream AppDir "$APP_NAME.AppImage" >> "$BUILD_LOG" 2>&1

    # 7. Finalização
    if [ -f "$APP_NAME.AppImage" ]; then
        mv "$APP_NAME.AppImage" "$USER_DOWNLOADS/$APP_NAME.AppImage"
        chmod +x "$USER_DOWNLOADS/$APP_NAME.AppImage"
        echo "100"
    else
        echo "Falha na geração do arquivo" >> "$BUILD_LOG"; exit 1
    fi
}

# ==========================================
# MENU DE ESCOLHA
# ==========================================

ACTION=$(zenity --list --title="Instalador $APP_NAME" \
    --text="Bem-vindo ao instalador do <b>$APP_NAME</b>.\nSistema: $PRETTY_NAME\n\nEscolha o que deseja fazer:" \
    --radiolist \
    --column="" --column="Método" --column="Descrição" \
    TRUE "Sistema" "Instalar nativamente no sistema (Recomendado)" \
    FALSE "AppImage" "Criar AppImage Portátil (Salvar em Downloads)" \
    --height=300 --width=550 --hide-header=FALSE)

if [ -z "$ACTION" ]; then exit 0; fi

# ==========================================
# FLUXO B: CONSTRUIR APPIMAGE
# ==========================================
if [ "$ACTION" == "AppImage" ]; then
    (build_appimage_local) | zenity --progress --title="Construindo AppImage..." --pulsate --auto-close --width=450

    RESULT="$USER_DOWNLOADS/$APP_NAME.AppImage"
    if [ -f "$RESULT" ]; then
        zenity --info --text="AppImage criado com sucesso!\n\nSalvo em:\n$RESULT" --width=400
    else
        zenity --error --text="Erro ao criar AppImage. Veja o log." --width=400
        show_debug_log "$BUILD_LOG" "Erro na Construção"
    fi
    exit 0
fi

# ==========================================
# FLUXO A: INSTALAÇÃO NATIVA (Original)
# ==========================================
# Daqui para baixo segue a lógica original do script para instalação no sistema

# 1. Arch (Agora direcionado para AUR)
if [[ "$DISTRO_ID" == *"arch"* ]] || [[ "$DISTRO_LIKE_ID" == *"arch"* ]] || [[ "$DISTRO_ID" == "cachyos" ]]; then
    PKG_TYPE="aur"
# 2. Debian/Ubuntu
elif [[ "$DISTRO_ID" == *"debian"* ]] || [[ "$DISTRO_LIKE_ID" == *"debian"* ]] || [[ "$DISTRO_ID" == *"ubuntu"* ]] || [[ "$DISTRO_LIKE_ID" == *"ubuntu"* ]]; then
    PKG_TYPE="deb"; DOWNLOAD_URL="$URL_DEB"; FILENAME="$FILE_DEB"; INSTALL_CMD="apt-get install -y"
# 3. RPM (Fedora / SUSE / Regata)
elif [[ "$DISTRO_ID" == *"fedora"* ]] || [[ "$DISTRO_LIKE_ID" == *"fedora"* ]] || [[ "$DISTRO_ID" == *"rhel"* ]] || [[ "$DISTRO_ID" == *"centos"* ]] || [[ "$DISTRO_ID" == *"suse"* ]] || [[ "$DISTRO_LIKE_ID" == *"suse"* ]] || [[ "$DISTRO_ID" == *"regata"* ]]; then
    PKG_TYPE="rpm"; DOWNLOAD_URL="$URL_RPM"; FILENAME="$FILE_RPM"
    INSTALL_CMD="dnf install -y"
    if [[ "$DISTRO_ID" == *"suse"* ]] || [[ "$DISTRO_LIKE_ID" == *"suse"* ]] || [[ "$DISTRO_ID" == *"regata"* ]]; then
        INSTALL_CMD="zypper --non-interactive install -y --allow-unsigned-rpm"
    fi
else
    PKG_TYPE="unknown"
    show_error "Distro não suportada para instalação nativa: $ID"
fi

# ==========================================
# INSTALAÇÃO VIA AUR (ARCH LINUX)
# ==========================================
if [ "$PKG_TYPE" == "aur" ]; then
    if [ -z "$TERM_CMD" ]; then show_error "Nenhum emulador de terminal compatível encontrado."; fi
    AUR_SCRIPT="$TEMP_DIR/install_aur.sh"
    cat <<EOF > "$AUR_SCRIPT"
#!/bin/bash
echo "=== INSTALAÇÃO VIA AUR: $APP_NAME ==="
check_install() {
    if pacman -Qi $APP_NAME &> /dev/null; then echo "Pacote instalado com sucesso!";
    else echo "Falha na instalação."; return 1; fi
}
if command -v yay &> /dev/null; then echo ">> Usando YAY..."; yay -S --noconfirm $APP_NAME; check_install
elif command -v paru &> /dev/null; then echo ">> Usando PARU..."; paru -S --noconfirm $APP_NAME; check_install
else
    echo ">> Instalação Manual..."; sudo pacman -S --needed --noconfirm base-devel git
    BUILD_DIR="$TEMP_DIR/build_aur"; mkdir -p "\$BUILD_DIR"; cd "\$BUILD_DIR" || return 1
    rm -rf "$APP_NAME"; git clone "https://aur.archlinux.org/$APP_NAME.git"
    cd "$APP_NAME"; makepkg -si --noconfirm; check_install
fi
EOF
    run_external_process "$AUR_SCRIPT" "Instalando do AUR..."
    exit 0
fi

# ==========================================
# DOWNLOAD COM DEBUG (DEB/RPM)
# ==========================================
FILE_PATH="$TEMP_DIR/$FILENAME"
rm -f "$WGET_LOG"
(wget -O "$FILE_PATH" "$DOWNLOAD_URL" 2>&1 | tee "$WGET_LOG" | sed -u 's/.* \([0-9]\+%\)\ \+\([0-9.]\+.\) \(.*\)/\1\n# Baixando \2\/s ETA \3/' | zenity --progress --title="Baixando $FILENAME..." --auto-close --width=400)

if [ ! -s "$FILE_PATH" ]; then
    zenity --error --text="Falha no download!" --width=400
    show_debug_log "$WGET_LOG" "Log de Erro do Download"
    exit 1
fi

# ==========================================
# INSTALAÇÃO (DEB/RPM)
# ==========================================
SUCCESS_FLAG="$TEMP_DIR/success"
rm -f "$INSTALL_LOG"

(
    echo "10"; echo "# Instalando..."
    if pkexec $INSTALL_CMD "$FILE_PATH" > "$INSTALL_LOG" 2>&1; then echo "100"; touch "$SUCCESS_FLAG"; else echo "100"; fi
) | zenity --progress --title="Instalando..." --pulsate --auto-close --no-cancel --width=400

# ==========================================
# VERIFICAÇÃO FINAL E FIX SUSE
# ==========================================
if [ -f "$SUCCESS_FLAG" ]; then
    zenity --info --text="Instalação concluída com sucesso!" --width=350
else
    IS_SUSE=0
    if [[ "$DISTRO_ID" == *"suse"* ]] || [[ "$DISTRO_LIKE_ID" == *"suse"* ]] || [[ "$DISTRO_ID" == *"regata"* ]]; then IS_SUSE=1; fi

    if [ $IS_SUSE -eq 1 ]; then
        zenity --question --title="Falha na Instalação Padrão" --text="A instalação padrão falhou.\n\nTentar Correção Automática?" --ok-label="Corrigir" --cancel-label="Ver Log"
        if [ $? -ne 0 ]; then show_debug_log "$INSTALL_LOG" "Log de Falha"; exit 1; fi

        FIX_SCRIPT="$TEMP_DIR/suse_fix.sh"
        echo -e "#!/bin/bash\nset -x\nsudo zypper refresh\nsudo zypper -vv --non-interactive install -y $SUSE_DEPS\nsudo rpm -Uvh -vv --nodeps --force '$FILE_PATH'" > "$FIX_SCRIPT"
        run_external_process "$FIX_SCRIPT" "Corrigindo Dependências..."
        exit 0
    fi

    zenity --error --text="Falha na instalação." --width=400
    show_debug_log "$INSTALL_LOG" "Log Completo da Instalação"
fi

exit 0
