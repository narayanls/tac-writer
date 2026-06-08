"""
post_build.py — Executar APÓS o PyInstaller gerar o bundle.

O libenchant 2.x no Windows usa g_win32_get_package_installation_directory_of_module()
para descobrir onde estão os plugins. Essa função retorna o diretório PAI da DLL,
que no bundle onedir é TacWriter/ (pai de _internal/). Portanto o libenchant procura:
    TacWriter/lib/enchant-2/          ← plugins (.dll)
    TacWriter/share/hunspell/         ← dicionários (.aff/.dic)

O PyInstaller empacota tudo dentro de _internal/, e não permite destinos "../".
Este script copia os arquivos para os lugares onde o libenchant realmente os procura.

Uso:
    python post_build.py
    python post_build.py --dist-dir caminho/para/dist/TacWriter
"""

import argparse
import shutil
import sys
from pathlib import Path

# ── Configuração ──────────────────────────────────────────────────────────────

DEFAULT_DIST = Path("dist/TacWriter")

COPY_TASKS = [
    {
        "src":  "_internal/lib/enchant-2",
        "dst":  "lib/enchant-2",
        "desc": "Enchant plugin DLLs",
        "glob": "*.dll",
    },
    {
        "src":  "_internal/share/hunspell",
        "dst":  "share/hunspell",
        "desc": "Hunspell dictionaries",
        "glob": "*",
    },
]

# ── Funções ───────────────────────────────────────────────────────────────────

def copy_task(bundle_root: Path, task: dict) -> int:
    src_dir = bundle_root / task["src"]
    dst_dir = bundle_root / task["dst"]

    if not src_dir.exists():
        print(f"  [AVISO] Origem não encontrada, pulando: {src_dir}")
        return 0

    dst_dir.mkdir(parents=True, exist_ok=True)
    copied = 0

    for src_file in src_dir.glob(task["glob"]):
        if not src_file.is_file():
            continue
        dst_file = dst_dir / src_file.name
        shutil.copy2(src_file, dst_file)
        copied += 1

    return copied


def run(bundle_root: Path) -> None:
    if not bundle_root.exists():
        sys.exit(f"ERRO: Diretório do bundle não encontrado: {bundle_root}\n"
                 "Execute o PyInstaller antes de rodar este script.")

    print(f"\n[post_build] Bundle root: {bundle_root.resolve()}\n")

    total = 0
    for task in COPY_TASKS:
        print(f"  → {task['desc']}")
        print(f"     src: {task['src']}")
        print(f"     dst: {task['dst']}")
        n = copy_task(bundle_root, task)
        print(f"     {n} arquivo(s) copiado(s)\n")
        total += n

    print(f"[post_build] Concluído — {total} arquivo(s) copiado(s) no total.")
    print("\nEstrutura esperada após o post_build:")
    print("  TacWriter/")
    print("  ├── lib/")
    print("  │   └── enchant-2/          ← enchant_hunspell.dll, libhunspell-*.dll …")
    print("  ├── share/")
    print("  │   └── hunspell/           ← en_US.aff, en_US.dic, pt_BR.aff …")
    print("  └── _internal/              ← tudo que o PyInstaller gerou (inalterado)")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Post-build: copia plugins do Enchant para fora de _internal/")
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=DEFAULT_DIST,
        help=f"Caminho para o diretório TacWriter gerado pelo PyInstaller (padrão: {DEFAULT_DIST})",
    )
    args = parser.parse_args()
    run(args.dist_dir)
