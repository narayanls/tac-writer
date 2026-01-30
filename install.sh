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
VERSION_TAG="v1.2.6-3"     # Tag da Release no Github
VERSION_FILE="1.2.6-3"     # Versão no nome do arquivo
DEBUG_MODE="1"             # 1 = Ativa logs detalhados e não apaga temp imediatamente

# --- LÓGICA DE DEPENDÊNCIAS SUSE (Leap/Regata vs Tumbleweed) ---
SUSE_BASE="typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 libadwaita-1-0 gettext-runtime liberation-fonts myspell-pt_BR myspell-en_US myspell-es"

if [[ "$PRETTY_NAME_LOWER" == *"leap"* ]] || [[ "$DISTRO_ID" == *"regata"* ]]; then
    # Leap e Regata: prefixo python3
    PY_PREFIX="python311"
else
    # Tumbleweed: prefixo versionado (ex: python313)
    PY_PREFIX="python313"
fi

SUSE_DEPS="$SUSE_BASE ${PY_PREFIX} ${PY_PREFIX}-gobject ${PY_PREFIX}-reportlab ${PY_PREFIX}-pygtkspellcheck ${PY_PREFIX}-pyenchant ${PY_PREFIX}-Pillow ${PY_PREFIX}-requests ${PY_PREFIX}-pypdf ${PY_PREFIX}-PyLaTeX ${PY_PREFIX}-dropbox "

# Definição dos Arquivos
FILE_DEB="${APP_NAME}_${VERSION_FILE}_amd64.deb" 
FILE_RPM="${APP_NAME}-${VERSION_FILE}-1.x86_64.rpm"
FILE_ARCH="${APP_NAME}-${VERSION_FILE}-any.pkg.tar.zst"

# URLs
BASE_URL="https://github.com/$GITHUB_USER/$APP_NAME/releases/download/$VERSION_TAG"
URL_DEB="$BASE_URL/$FILE_DEB"
URL_RPM="$BASE_URL/$FILE_RPM"

# Diretório temporário
TEMP_DIR="/tmp/$APP_NAME-install"
mkdir -p "$TEMP_DIR"

# Logs de Debug
WGET_LOG="$TEMP_DIR/wget_debug.log"
INSTALL_LOG="$TEMP_DIR/install_debug.log"
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

# Mostra log em janela rolável (Essencial para Debug)
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
    
    # Injeta lógica de controle e espera
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
            zenity --info --text="Processo concluído com sucesso!" --title="Sucesso" --width=350
        else
            zenity --error --text="Ocorreu um erro no terminal. O script terminal pode estar pausado aguardando Enter." --width=400
            touch "$FLAG_CLOSE"
        fi
    else
        touch "$FLAG_CLOSE"
    fi
    sleep 0.5
    exit 0
}

# ==========================================
# LÓGICA DE DETECÇÃO
# ==========================================
PKG_TYPE="unknown"

# 1. Arch
if [[ "$DISTRO_ID" == *"arch"* ]] || [[ "$DISTRO_LIKE_ID" == *"arch"* ]] || [[ "$DISTRO_ID" == "cachyos" ]]; then 
    PKG_TYPE="arch"; DOWNLOAD_URL="$URL_ARCH"; FILENAME="$FILE_ARCH"; INSTALL_CMD="pacman -U --noconfirm"

# 2. Debian/Ubuntu
elif [[ "$DISTRO_ID" == *"debian"* ]] || [[ "$DISTRO_LIKE_ID" == *"debian"* ]] || [[ "$DISTRO_ID" == *"ubuntu"* ]] || [[ "$DISTRO_LIKE_ID" == *"ubuntu"* ]]; then 
    PKG_TYPE="deb"; DOWNLOAD_URL="$URL_DEB"; FILENAME="$FILE_DEB"; INSTALL_CMD="apt-get install -y"

# 3. RPM (Fedora / SUSE / Regata)
elif [[ "$DISTRO_ID" == *"fedora"* ]] || [[ "$DISTRO_LIKE_ID" == *"fedora"* ]] || [[ "$DISTRO_ID" == *"rhel"* ]] || [[ "$DISTRO_ID" == *"centos"* ]] || [[ "$DISTRO_ID" == *"suse"* ]] || [[ "$DISTRO_LIKE_ID" == *"suse"* ]] || [[ "$DISTRO_ID" == *"regata"* ]]; then 
    PKG_TYPE="rpm"; DOWNLOAD_URL="$URL_RPM"; FILENAME="$FILE_RPM"
    INSTALL_CMD="dnf install -y"
    
    # Ajuste SUSE/Regata
    if [[ "$DISTRO_ID" == *"suse"* ]] || [[ "$DISTRO_LIKE_ID" == *"suse"* ]] || [[ "$DISTRO_ID" == *"regata"* ]]; then 
        INSTALL_CMD="zypper --non-interactive install -y --allow-unsigned-rpm"
    fi
fi

if [ "$PKG_TYPE" == "unknown" ]; then show_error "Distro não suportada: $ID"; fi

# ==========================================
# DOWNLOAD COM DEBUG
# ==========================================

zenity --question --title="Instalador $APP_NAME" \
    --text="Instalador <b>$APP_NAME v$VERSION_FILE</b>.\nSistema: <b>${PRETTY_NAME}</b>\nPacote: <b>$PKG_TYPE</b>\n\nDeseja instalar?" \
    --ok-label="Instalar" --cancel-label="Cancelar" --width=400 || exit 0

FILE_PATH="$TEMP_DIR/$FILENAME"

# -- DEBUG: Salva log do Wget --
rm -f "$WGET_LOG"
(wget -O "$FILE_PATH" "$DOWNLOAD_URL" 2>&1 | tee "$WGET_LOG" | sed -u 's/.* \([0-9]\+%\)\ \+\([0-9.]\+.\) \(.*\)/\1\n# Baixando \2\/s ETA \3/' | zenity --progress --title="Baixando $FILENAME..." --auto-close --width=400)

# Verifica se baixou e se o tamanho é maior que 0
if [ ! -s "$FILE_PATH" ]; then
    echo "FALHA NO DOWNLOAD. URL TENTADA: $DOWNLOAD_URL" >> "$WGET_LOG"
    zenity --error --text="Falha no download!\n\nVerifique o Log a seguir para ver o erro (DNS, 404, etc)." --width=400
    show_debug_log "$WGET_LOG" "Log de Erro do Download (Wget)"
    exit 1
fi

# ==========================================
# INSTALAÇÃO
# ==========================================

SUCCESS_FLAG="$TEMP_DIR/success"
rm -f "$INSTALL_LOG"

(
    echo "10"; echo "# Instalando..."
    # Executa instalador e salva TUDO no log
    if pkexec $INSTALL_CMD "$FILE_PATH" > "$INSTALL_LOG" 2>&1; then 
        echo "100"; touch "$SUCCESS_FLAG"
    else 
        echo "100"
    fi
) | zenity --progress --title="Instalando..." --pulsate --auto-close --no-cancel --width=400

# ==========================================
# VERIFICAÇÃO FINAL E FIX SUSE
# ==========================================

if [ -f "$SUCCESS_FLAG" ]; then
    zenity --info --text="Instalação concluída com sucesso!" --width=350
else
    # Verifica SUSE/Regata
    IS_SUSE=0
    if [[ "$DISTRO_ID" == *"suse"* ]] || [[ "$DISTRO_LIKE_ID" == *"suse"* ]] || [[ "$DISTRO_ID" == *"regata"* ]]; then IS_SUSE=1; fi
    
    if [ $IS_SUSE -eq 1 ]; then
        zenity --question --title="Falha na Instalação Padrão" \
            --text="A instalação padrão falhou.\n\nDeseja ver o log de erro ou tentar a correção automática (Instalar Dependências + Force RPM)?" \
            --ok-label="Tentar Correção" --cancel-label="Ver Log de Erro" --width=500
        
        RESP=$?
        
        # Se clicou em "Ver Log" (botão cancel)
        if [ $RESP -ne 0 ]; then
            show_debug_log "$INSTALL_LOG" "Log de Falha na Instalação"
            exit 1
        fi
            
        if [ ! -z "$TERM_CMD" ]; then
            FIX_SCRIPT="$TEMP_DIR/suse_fix.sh"
            echo "#!/bin/bash" > "$FIX_SCRIPT"
            
            # ATIVA DEBUG NO SCRIPT GERADO
            echo "set -x" >> "$FIX_SCRIPT" 
            
            echo "echo '=== CORREÇÃO DE DEPENDÊNCIAS (Modo Debug) ==='" >> "$FIX_SCRIPT"
            echo "echo 'Arquivo: $FILE_PATH'" >> "$FIX_SCRIPT"
            echo "echo ''" >> "$FIX_SCRIPT"
            
            echo "echo '1. Atualizando repositórios...'" >> "$FIX_SCRIPT"
            echo "sudo zypper refresh" >> "$FIX_SCRIPT"
            
            echo "echo '2. Instalando Dependências...'" >> "$FIX_SCRIPT"
            # Adicionei -vv para verbose no zypper
            echo "sudo zypper -vv --non-interactive install -y $SUSE_DEPS" >> "$FIX_SCRIPT"
            echo "echo ''" >> "$FIX_SCRIPT"
            
            echo "echo '3. Instalando App (Force RPM)...'" >> "$FIX_SCRIPT"
            # Adicionei -vv para verbose no RPM
            echo "sudo rpm -Uvh -vv --nodeps --force '$FILE_PATH'" >> "$FIX_SCRIPT"
            
            run_external_process "$FIX_SCRIPT" "Corrigindo Dependências..."
            exit 0
        fi
    fi

    # Se falhou e não é SUSE, ou se falhou a correção
    zenity --error --text="Falha na instalação." --width=400
    show_debug_log "$INSTALL_LOG" "Log Completo da Instalação"
fi

exit 0
