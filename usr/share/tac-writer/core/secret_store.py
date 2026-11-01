"""
TAC Secret Store
Armazena credenciais (chave da API de IA, token do Dropbox) fora do config.json.

Os segredos ficam em <config_dir>/secrets.json, com permissão 0600 em
Linux (somente o próprio usuário lê/escreve). No Windows o arquivo fica em
%APPDATA%\\tac, que já é uma pasta privada do usuário.

Sem dependências externas: usa apenas a biblioteca padrão, para funcionar
igual em Arch, Ubuntu, Fedora, Flatpak e Windows.

O arquivo é relido a cada consulta (é minúsculo), para que várias instâncias
de Config abertas ao mesmo tempo sempre enxerguem o valor mais recente.
"""

import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional

SECRETS_FILENAME = 'secrets.json'


def _secrets_path(config_dir: Path) -> Path:
    return Path(config_dir) / SECRETS_FILENAME


def _read_all(config_dir: Path) -> Dict[str, str]:
    path = _secrets_path(config_dir)
    if not path.exists():
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        print(f"Error loading secrets: {e}")
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if v}


def _write_all(config_dir: Path, data: Dict[str, str]) -> None:
    """
    Grava de forma atômica e já com permissão 0600.

    O arquivo temporário é criado com os.open(..., 0o600), então em nenhum
    momento o conteúdo fica legível para outros usuários. Depois, os.replace
    troca o arquivo de uma vez (funciona em Linux e Windows).
    """
    path = _secrets_path(config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + '.tmp')

    fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp_path), str(path))
    except Exception:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise

    # Garante 0600 mesmo se o arquivo já existia com permissão mais aberta
    try:
        os.chmod(str(path), 0o600)
    except OSError:
        pass


def get_secret(config_dir: Path, key: str) -> str:
    """Retorna o segredo, ou string vazia se não existir."""
    return _read_all(config_dir).get(key, '')


def set_secret(config_dir: Path, key: str, value: Optional[str]) -> bool:
    """
    Grava o segredo. Valor vazio ou None remove a chave.
    Retorna True se o secrets.json ficou com o valor pedido.
    """
    value = str(value).strip() if value else ''
    data = _read_all(config_dir)

    if value:
        if data.get(key) == value:
            return True
        data[key] = value
    else:
        if key not in data:
            return True
        data.pop(key, None)

    try:
        _write_all(config_dir, data)
        return True
    except OSError as e:
        print(f"Error saving secrets: {e}")
        return False


def migrate_from_config(config_dir: Path, config_dict: dict, keys: Iterable[str]) -> List[str]:
    """
    Move segredos em texto puro do dicionário de configuração para o
    secrets.json e os remove do dicionário.

    Retorna a lista de chaves removidas do dicionário (o chamador deve então
    regravar o config.json para que ele fique limpo). Se a gravação no
    secrets.json falhar, a chave é mantida no config para não perder a
    credencial do usuário.
    """
    removed = []
    for key in keys:
        if key not in config_dict:
            continue
        value = config_dict.get(key)
        if value and not set_secret(config_dir, key, str(value)):
            continue
        config_dict.pop(key, None)
        removed.append(key)
    return removed
