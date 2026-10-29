"""
TAC - Sincronização com o Dropbox, isolada da interface.

Este módulo não importa GTK. A lógica ficava dentro de um método do
CloudSyncDialog, presa a um botão, o que impedia reaproveitá-la para a
sincronização automática. Aqui ela é uma função comum, e tanto o diálogo
quanto o fechamento do app chamam a mesma coisa.

sync_now() nunca levanta exceção: devolve sempre um dicionário com 'ok',
'message' e 'error'. Quem chama decide se mostra na tela ou só registra
no terminal.
"""

import os
import sqlite3
from pathlib import Path

try:
    import dropbox
    from dropbox.files import WriteMode
    from dropbox.exceptions import ApiError
    DROPBOX_AVAILABLE = True
except ImportError:
    DROPBOX_AVAILABLE = False

from utils.i18n import _
from core.config import Config

DROPBOX_APP_KEY = Config.DROPBOX_APP_KEY
REMOTE_DB_PATH = "/tac_writer.db"


# ----------------------------------------------------------------------
# Consultas de estado
# ----------------------------------------------------------------------

def is_linked(config) -> bool:
    """A conta do Dropbox está vinculada?"""
    token = (
        config.get_dropbox_refresh_token()
        if hasattr(config, 'get_dropbox_refresh_token')
        else config.get('dropbox_refresh_token')
    )
    return DROPBOX_AVAILABLE and bool(token)


def auto_sync_enabled(config) -> bool:
    """A sincronização automática está ligada? Padrão: ligada."""
    return bool(config.get('dropbox_auto_sync', True))


def db_mtime(db_path) -> float:
    """
    Data de modificação do banco, considerando os arquivos do WAL.

    Em modo WAL os commits vão para o arquivo -wal e o .db principal só
    muda no checkpoint. Olhar apenas o .db faria has_local_changes()
    responder "nada mudou" logo depois de o usuário escrever, e o
    fechamento pularia o envio em silêncio.
    """
    base = str(db_path)
    tempos = []
    for sufixo in ("", "-wal", "-shm"):
        try:
            tempos.append(os.path.getmtime(base + sufixo))
        except OSError:
            continue
    return max(tempos) if tempos else 0.0


def has_local_changes(config) -> bool:
    """
    Houve alteração no banco desde o último envio?

    Compara a data de modificação do arquivo com a que foi registrada ao
    final da última sincronização. Evita subir o banco inteiro no
    fechamento quando nada mudou.
    """
    atual = db_mtime(config.database_path)
    if atual == 0.0:
        return False

    ultimo = config.get('dropbox_last_sync_mtime')
    if ultimo is None:
        return True

    # Margem de um segundo para diferenças de precisão entre sistemas.
    try:
        return abs(atual - float(ultimo)) > 1.0
    except (TypeError, ValueError):
        return True


# ----------------------------------------------------------------------
# Sincronização
# ----------------------------------------------------------------------

def _snapshot(db_path: Path, snapshot_path: Path) -> None:
    """
    Cópia consistente do banco.

    Ler o .db direto deixaria de fora os commits que ainda estão no
    arquivo -wal, e o arquivo enviado poderia até não conter as tabelas.
    """
    source = sqlite3.connect(str(db_path))
    destination = sqlite3.connect(str(snapshot_path))
    try:
        with destination:
            source.backup(destination)
    finally:
        destination.close()
        source.close()


def sync_now(config, project_manager, progress=None) -> dict:
    """
    Executa o ciclo completo: baixar, mesclar, imagens, enviar.

    progress: função opcional que recebe uma string de status.
    """
    def aviso(texto):
        if progress:
            progress(texto)

    resultado = {'ok': False, 'message': '', 'error': None, 'stats': None}

    if not DROPBOX_AVAILABLE:
        resultado['message'] = _("Biblioteca do Dropbox não instalada.")
        return resultado

    refresh_token = (
        config.get_dropbox_refresh_token()
        if hasattr(config, 'get_dropbox_refresh_token')
        else config.get('dropbox_refresh_token')
    )
    if not refresh_token:
        resultado['message'] = _("Conta do Dropbox não vinculada.")
        return resultado

    local_db_path = config.database_path
    temp_db_path = local_db_path.with_suffix('.temp_sync.db')
    snapshot_path = local_db_path.with_suffix('.snapshot.db')

    try:
        dbx = dropbox.Dropbox(
            oauth2_refresh_token=refresh_token,
            app_key=DROPBOX_APP_KEY
        )

        # 1. Baixar o arquivo remoto, se existir.
        aviso(_("Baixando da nuvem..."))
        remote_exists = False
        try:
            dbx.files_download_to_file(str(temp_db_path), REMOTE_DB_PATH)
            remote_exists = True
        except ApiError as e:
            if e.error.is_path() and e.error.get_path().is_not_found():
                remote_exists = False
            else:
                raise

        # 2. Mesclar.
        if remote_exists:
            aviso(_("Mesclando alterações..."))
            stats = project_manager.merge_database(str(temp_db_path))
            resultado['stats'] = stats

            if temp_db_path.exists():
                os.remove(temp_db_path)

            novos = stats.get('paragraphs_added', 0)
            atualizados = stats.get('paragraphs_updated', 0)
            excluidos = (stats.get('paragraphs_deleted', 0)
                         + stats.get('projects_deleted', 0))
            projetos = stats.get('projects_added', 0)

            if novos or atualizados or excluidos or projetos:
                partes = []
                if projetos:
                    partes.append(_("{} projeto(s) novo(s)").format(projetos))
                if novos:
                    partes.append(_("{} parágrafo(s) novo(s)").format(novos))
                if atualizados:
                    partes.append(_("{} atualizado(s)").format(atualizados))
                if excluidos:
                    partes.append(_("{} excluído(s)").format(excluidos))
                resultado['message'] = _("Sincronizado: {}.").format(", ".join(partes))
            else:
                resultado['message'] = _("Sincronização concluída (sem alterações remotas).")
        else:
            resultado['message'] = _("Primeiro envio para a nuvem realizado.")

        # 3. Imagens. Uma falha aqui não deve derrubar a sincronização do
        #    texto, que é o que importa mais.
        try:
            from core.cloud_files import sync_images
            aviso(_("Sincronizando imagens..."))
            baixadas, enviadas = sync_images(dbx, config.data_dir / 'images')
            if baixadas or enviadas:
                resultado['message'] += _(" Imagens: {} baixada(s), {} enviada(s).").format(
                    baixadas, enviadas
                )
        except Exception as img_error:
            print(f"[sync] aviso: sincronização de imagens falhou: {img_error}")

        # 4. Enviar o banco local.
        aviso(_("Enviando para a nuvem..."))
        _snapshot(local_db_path, snapshot_path)

        with open(snapshot_path, "rb") as f:
            dbx.files_upload(f.read(), REMOTE_DB_PATH, mode=WriteMode('overwrite'))

        # Registra a data do arquivo para que o próximo fechamento saiba
        # se houve alteração desde agora. Precisa usar o mesmo critério
        # de db_mtime(), senão a comparação nunca fecha.
        try:
            config.set('dropbox_last_sync_mtime', db_mtime(local_db_path))
            config.save()
        except OSError:
            pass

        resultado['ok'] = True
        return resultado

    except Exception as e:
        print(f"[sync] erro: {type(e).__name__}: {e}")
        resultado['error'] = e

        if DROPBOX_AVAILABLE and isinstance(e, dropbox.exceptions.InternalServerError):
            resultado['message'] = _("O Dropbox está instável no momento. "
                                     "Aguarde alguns minutos e tente novamente.")
        elif DROPBOX_AVAILABLE and isinstance(e, dropbox.exceptions.AuthError):
            resultado['message'] = _("A conexão com o Dropbox expirou. "
                                     "Vincule a conta novamente.")
        else:
            resultado['message'] = str(e)

        return resultado

    finally:
        for leftover in (temp_db_path, snapshot_path):
            try:
                if leftover.exists():
                    os.remove(leftover)
            except OSError:
                pass
