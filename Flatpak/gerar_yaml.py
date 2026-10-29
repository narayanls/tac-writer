#!/usr/bin/env python3
"""
Gera o arquivo python3-requirements.yaml com wheels pré-compilados
para todas as dependências que exigem binários nativos.

Uso: python3 gerar_yaml.py

Nota: Assume Python 3.13 (GNOME SDK 49/50) e arquitetura x86_64.
Para GNOME SDK 47 (Python 3.12), altere PYTHON_TAG para "cp312-cp312".
Para aarch64, ajuste os valores de *_PLATFORM abaixo.
"""
import json
import urllib.request
import sys

# === Configuração de plataforma ===
# GNOME SDK 49/50 = Python 3.13 | GNOME SDK 47 = Python 3.12
PYTHON_TAG = "cp313-cp313"
ARCH = "x86_64"

# Plataformas preferidas em ordem de prioridade (mais específica primeiro)
PLATFORM_PREFERENCES = [
    f"manylinux_2_28_{ARCH}",
    f"manylinux_2_17_{ARCH}",
    f"manylinux2014_{ARCH}",
]

# === Wheels nativos a buscar dinamicamente ===
# (nome_pypi, versão, plataformas_aceitas)
# Para wheels com tag "abi3" (ex: cryptography), usamos tag especial
NATIVE_WHEELS = [
    ("pillow",              "12.1.0",  PLATFORM_PREFERENCES),
    ("charset-normalizer",  "3.4.4",   PLATFORM_PREFERENCES),
    ("cffi",                "1.17.1",  PLATFORM_PREFERENCES),
    ("contourpy",           "1.3.2",   PLATFORM_PREFERENCES),
    ("fonttools",           "4.62.1",  PLATFORM_PREFERENCES),
    ("kiwisolver",          "1.5.0",   PLATFORM_PREFERENCES),
    ("numpy",               "2.2.6",   PLATFORM_PREFERENCES),
    ("matplotlib",          "3.10.9",  PLATFORM_PREFERENCES),
]

# cryptography usa abi3, não cpXYZ
NATIVE_WHEELS_ABI3 = [
    ("cryptography",        "44.0.3",  f"manylinux_2_28_{ARCH}"),
]


def get_wheel_info(pkg_name, version, pytag, platform_list):
    """Busca URL e SHA256 de um wheel específico no PyPI."""
    api_url = f"https://pypi.org/pypi/{pkg_name}/{version}/json"
    try:
        with urllib.request.urlopen(api_url) as response:
            data = json.loads(response.read())
    except Exception as e:
        print(f"ERRO: Não foi possível acessar PyPI para {pkg_name}: {e}", file=sys.stderr)
        sys.exit(1)

    # Tenta cada plataforma em ordem de preferência
    if isinstance(platform_list, str):
        platform_list = [platform_list]

    for platform in platform_list:
        for file_info in data["urls"]:
            fn = file_info["filename"]
            if fn.endswith(".whl") and pytag in fn and platform in fn:
                return file_info["url"], file_info["digests"]["sha256"]

    print(f"ERRO: Wheel não encontrado para {pkg_name} {version} "
          f"(python={pytag}, platforms={platform_list})", file=sys.stderr)
    print("Wheels disponíveis:", file=sys.stderr)
    for fi in data["urls"]:
        if fi["filename"].endswith(".whl"):
            print(f"  {fi['filename']}", file=sys.stderr)
    sys.exit(1)


def get_wheel_info_abi3(pkg_name, version, platform_substr):
    """Busca wheel com tag abi3 (compatível com qualquer CPython >= 3.x)."""
    api_url = f"https://pypi.org/pypi/{pkg_name}/{version}/json"
    try:
        with urllib.request.urlopen(api_url) as response:
            data = json.loads(response.read())
    except Exception as e:
        print(f"ERRO: Não foi possível acessar PyPI para {pkg_name}: {e}", file=sys.stderr)
        sys.exit(1)

    for file_info in data["urls"]:
        fn = file_info["filename"]
        if fn.endswith(".whl") and "abi3" in fn and platform_substr in fn:
            return file_info["url"], file_info["digests"]["sha256"]

    print(f"ERRO: Wheel abi3 não encontrado para {pkg_name} {version} "
          f"(platform={platform_substr})", file=sys.stderr)
    sys.exit(1)


def fmt_source(url, sha256, anchor=None):
    """Formata uma entrada YAML de source."""
    anchor_str = f" &{anchor}\n" if anchor else "\n"
    return (
        f"      -{anchor_str}"
        f"        type: file\n"
        f"        url: {url}\n"
        f"        sha256: {sha256}"
    )


def main():
    print(f"Configuração: {PYTHON_TAG}, arch={ARCH}")
    print("Consultando PyPI para obter URLs dos wheels...\n")

    wheels = {}

    # Busca wheels nativos (cpXYZ)
    for pkg_name, version, platforms in NATIVE_WHEELS:
        url, sha = get_wheel_info(pkg_name, version, PYTHON_TAG, platforms)
        key = pkg_name.replace("-", "_").lower()
        wheels[key] = (url, sha)
        print(f"  ✓ {pkg_name}: {url.split('/')[-1]}")

    # Busca wheels abi3
    for pkg_name, version, platform in NATIVE_WHEELS_ABI3:
        url, sha = get_wheel_info_abi3(pkg_name, version, platform)
        key = pkg_name.replace("-", "_").lower()
        wheels[key] = (url, sha)
        print(f"  ✓ {pkg_name} (abi3): {url.split('/')[-1]}")

    # Monta o YAML
    yaml_content = f"""\
# Gerado automaticamente por gerar_yaml.py
# Python: {PYTHON_TAG} | Arch: {ARCH}
# Para regenerar: python3 gerar_yaml.py
build-commands: []
buildsystem: simple
modules:
  - name: python3-reportlab
    buildsystem: simple
    build-commands:
      - pip3 install --verbose --exists-action=i --no-index --find-links="file://${{PWD}}"
        --prefix=${{FLATPAK_DEST}} "reportlab" --no-build-isolation
    sources:
      - &id_charset
        type: file
        url: {wheels['charset_normalizer'][0]}
        sha256: {wheels['charset_normalizer'][1]}
      - &id_pillow
        type: file
        url: {wheels['pillow'][0]}
        sha256: {wheels['pillow'][1]}
      - type: file
        url: https://files.pythonhosted.org/packages/17/77/546e50edfaba6a0e58e8ec5fdc4446510227cec9e8f40172b60941d5a633/reportlab-4.4.9-py3-none-any.whl
        sha256: 68e2d103ae8041a37714e8896ec9b79a1c1e911d68c3bd2ea17546568cf17bfd
  - name: python3-pygtkspellcheck
    buildsystem: simple
    build-commands:
      - pip3 install --verbose --exists-action=i --no-index --find-links="file://${{PWD}}"
        --prefix=${{FLATPAK_DEST}} "pygtkspellcheck" --no-build-isolation
    sources:
      - &id_pycairo
        type: file
        url: https://files.pythonhosted.org/packages/22/d9/1728840a22a4ef8a8f479b9156aa2943cd98c3907accd3849fb0d5f82bfd/pycairo-1.29.0.tar.gz
        sha256: f3f7fde97325cae80224c09f12564ef58d0d0f655da0e3b040f5807bd5bd3142
      - &id_pyenchant
        type: file
        url: https://files.pythonhosted.org/packages/38/b0/35926bad6885fb7bc24aa7e1b45e6d86540c6c57ee4abc4fed1ef58d4ec0/pyenchant-3.3.0-py3-none-any.whl
        sha256: 3da00b1d01314d85aac733bb997415d7a3e875666dc81735ddcf320aa36b7a70
      - &id_pygobject
        type: file
        url: https://files.pythonhosted.org/packages/d3/a5/68f883df1d8442e3b267cb92105a4b2f0de819bd64ac9981c2d680d3f49f/pygobject-3.54.5.tar.gz
        sha256: b6656f6348f5245606cf15ea48c384c7f05156c75ead206c1b246c80a22fb585
      - type: file
        url: https://files.pythonhosted.org/packages/85/d4/610e9b4be60bac8f5a155a9553a982c3462a6b3eb117e9903f59e9389fac/pygtkspellcheck-5.0.3-py3-none-any.whl
        sha256: 5bd6fb3bdfcb3ce13825535ba6f1dc5d2e07a3e5d87d3034d8478d8bc884902c
  - name: python3-pyenchant
    buildsystem: simple
    build-commands:
      - pip3 install --verbose --exists-action=i --no-index --find-links="file://${{PWD}}"
        --prefix=${{FLATPAK_DEST}} "pyenchant" --no-build-isolation
    sources:
      - *id_pyenchant
  - name: python3-Pillow
    buildsystem: simple
    build-commands:
      - pip3 install --verbose --exists-action=i --no-index --find-links="file://${{PWD}}"
        --prefix=${{FLATPAK_DEST}} "Pillow" --no-build-isolation
    sources:
      - *id_pillow
  - name: python3-requests
    buildsystem: simple
    build-commands:
      - pip3 install --verbose --exists-action=i --no-index --find-links="file://${{PWD}}"
        --prefix=${{FLATPAK_DEST}} "requests" --no-build-isolation
    sources:
      - &id_certifi
        type: file
        url: https://files.pythonhosted.org/packages/e6/ad/3cc14f097111b4de0040c83a525973216457bbeeb63739ef1ed275c1c021/certifi-2026.1.4-py3-none-any.whl
        sha256: 9943707519e4add1115f44c2bc244f782c0249876bf51b6599fee1ffbedd685c
      - *id_charset
      - &id_idna
        type: file
        url: https://files.pythonhosted.org/packages/0e/61/66938bbb5fc52dbdf84594873d5b51fb1f7c7794e9c0f5bd885f30bc507b/idna-3.11-py3-none-any.whl
        sha256: 771a87f49d9defaf64091e6e6fe9c18d4833f140bd19464795bc32d966ca37ea
      - &id_requests
        type: file
        url: https://files.pythonhosted.org/packages/1e/db/4254e3eabe8020b458f1a747140d32277ec7a271daf1d235b70dc0b4e6e3/requests-2.32.5-py3-none-any.whl
        sha256: 2462f94637a34fd532264295e186976db0f5d453d1cdd31473c85a6a161affb6
      - &id_urllib3
        type: file
        url: https://files.pythonhosted.org/packages/39/08/aaaad47bc4e9dc8c725e68f9d04865dbcb2052843ff09c97b08904852d84/urllib3-2.6.3-py3-none-any.whl
        sha256: bf272323e553dfb2e87d9bfd225ca7b0f467b919d7bbd355436d3fd37cb0acd4
  - name: python3-pypdf
    buildsystem: simple
    build-commands:
      - pip3 install --verbose --exists-action=i --no-index --find-links="file://${{PWD}}"
        --prefix=${{FLATPAK_DEST}} "pypdf" --no-build-isolation
    sources:
      - type: file
        url: https://files.pythonhosted.org/packages/7d/be/549aaf1dfa4ab4aed29b09703d2fb02c4366fc1f05e880948c296c5764b9/pypdf-6.6.2-py3-none-any.whl
        sha256: 44c0c9811cfb3b83b28f1c3d054531d5b8b81abaedee0d8cb403650d023832ba
  - name: python3-pylatex
    buildsystem: simple
    build-commands:
      - pip3 install --verbose --exists-action=i --no-index --find-links="file://${{PWD}}"
        --prefix=${{FLATPAK_DEST}} "pylatex" --no-build-isolation
    sources:
      - type: file
        url: https://files.pythonhosted.org/packages/6d/a8/10cf6b955b5fa19438790d9949867e04c785ae845e631c5ef6db444401d1/PyLaTeX-1.4.2.tar.gz
        sha256: bb7b21bec57ecdba3f6f44c856ebebdf6549fd6e80661bd44fd5094236729242
      - type: file
        url: https://files.pythonhosted.org/packages/33/55/af02708f230eb77084a299d7b08175cff006dea4f2721074b92cdb0296c0/ordered_set-4.1.0-py3-none-any.whl
        sha256: 046e1132c71fcf3330438a539928932caf51ddbc582496833e23de611de14562
  - name: python3-PyGObject
    buildsystem: simple
    build-commands:
      - pip3 install --verbose --exists-action=i --no-index --find-links="file://${{PWD}}"
        --prefix=${{FLATPAK_DEST}} "PyGObject" --no-build-isolation
    sources:
      - *id_pycairo
      - *id_pygobject
  - name: python3-dropbox
    buildsystem: simple
    build-commands:
      - pip3 install --verbose --exists-action=i --no-index --find-links="file://${{PWD}}"
        --prefix=${{FLATPAK_DEST}} "dropbox" --no-build-isolation
    sources:
      - *id_certifi
      - *id_charset
      - type: file
        url: https://files.pythonhosted.org/packages/2d/de/95d8204d9a20fbdb353c5f8e4229b0fcb90f22b96f8246ff1f47c8a45fd5/dropbox-12.0.2-py3-none-any.whl
        sha256: c5b7e9c2668adb6b12dcecd84342565dc50f7d35ab6a748d155cb79040979d1c
      - *id_idna
      - type: file
        url: https://files.pythonhosted.org/packages/a3/58/35da89ee790598a0700ea49b2a66594140f44dec458c07e8e3d4979137fc/ply-3.11-py2.py3-none-any.whl
        sha256: 096f9b8350b65ebd2fd1346b12452efe5b9607f7482813ffca50c22722a807ce
      - *id_requests
      - &id_six
        type: file
        url: https://files.pythonhosted.org/packages/b7/ce/149a00dd41f10bc29e5921b496af8b574d8413afcd5e30dfa0ed46c2cc5e/six-1.17.0-py2.py3-none-any.whl
        sha256: 4721f391ed90541fddacab5acf947aa0d3dc7d27b2e1e8eda2be8970586c3274
      - type: file
        url: https://files.pythonhosted.org/packages/5c/92/d0c83f63d3518e5f0b8a311937c31347349ec9a47b209ddc17f7566f58fc/stone-3.3.1-py3-none-any.whl
        sha256: e15866fad249c11a963cce3bdbed37758f2e88c8ff4898616bc0caeb1e216047
      - *id_urllib3
  - name: python3-pycparser
    buildsystem: simple
    build-commands:
      - pip3 install --verbose --exists-action=i --no-index --find-links="file://${{PWD}}"
        --prefix=${{FLATPAK_DEST}} "pycparser" --no-build-isolation
    sources:
      - &id_pycparser
        type: file
        url: https://files.pythonhosted.org/packages/0c/c3/44f3fbbfa403ea2a7c779186dc20772604442dde72947e7d01069cbe98e3/pycparser-3.0-py3-none-any.whl
        sha256: b727414169a36b7d524c1c3e31839a521725078d7b2ff038656844266160a992
  - name: python3-cffi
    buildsystem: simple
    build-commands:
      - pip3 install --verbose --exists-action=i --no-index --find-links="file://${{PWD}}"
        --prefix=${{FLATPAK_DEST}} "cffi" --no-build-isolation
    sources:
      - *id_pycparser
      - &id_cffi
        type: file
        url: {wheels['cffi'][0]}
        sha256: {wheels['cffi'][1]}
  - name: python3-cryptography
    buildsystem: simple
    build-commands:
      - pip3 install --verbose --exists-action=i --no-index --find-links="file://${{PWD}}"
        --prefix=${{FLATPAK_DEST}} "cryptography" --no-build-isolation
    sources:
      - *id_pycparser
      - *id_cffi
      - type: file
        url: {wheels['cryptography'][0]}
        sha256: {wheels['cryptography'][1]}
  - name: python3-matplotlib
    buildsystem: simple
    build-commands:
      - pip3 install --verbose --exists-action=i --no-index --find-links="file://${{PWD}}"
        --prefix=${{FLATPAK_DEST}} "matplotlib" --no-build-isolation
    sources:
      - type: file
        url: {wheels['contourpy'][0]}
        sha256: {wheels['contourpy'][1]}
      - type: file
        url: https://files.pythonhosted.org/packages/e7/05/c19819d5e3d95294a6f5947fb9b9629efb316b96de511b418c53d245aae6/cycler-0.12.1-py3-none-any.whl
        sha256: 85cef7cff222d8644161529808465972e51340599459b8ac3ccbac5a854e0d30
      - type: file
        url: {wheels['fonttools'][0]}
        sha256: {wheels['fonttools'][1]}
      - type: file
        url: {wheels['kiwisolver'][0]}
        sha256: {wheels['kiwisolver'][1]}
      - type: file
        url: {wheels['numpy'][0]}
        sha256: {wheels['numpy'][1]}
      - type: file
        url: https://files.pythonhosted.org/packages/df/b2/87e62e8c3e2f4b32e5fe99e0b86d576da1312593b39f47d8ceef365e95ed/packaging-26.2-py3-none-any.whl
        sha256: 5fc45236b9446107ff2415ce77c807cee2862cb6fac22b8a73826d0693b0980e
      - *id_pillow
      - type: file
        url: https://files.pythonhosted.org/packages/10/bd/c038d7cc38edc1aa5bf91ab8068b63d4308c66c4c8bb3cbba7dfbc049f9c/pyparsing-3.3.2-py3-none-any.whl
        sha256: 850ba148bd908d7e2411587e247a1e4f0327839c40e2e5e6d05a007ecc69911d
      - type: file
        url: https://files.pythonhosted.org/packages/ec/57/56b9bcc3c9c6a792fcbaf139543cee77261f3651ca9da0c93f5c1221264b/python_dateutil-2.9.0.post0-py2.py3-none-any.whl
        sha256: a8b2bc7bffae282281c8140a97d3aa9c14da0b136dfe83f850eea9a5f7470427
      - *id_six
      - type: file
        url: {wheels['matplotlib'][0]}
        sha256: {wheels['matplotlib'][1]}
name: python3-requirements
"""

    output_file = "python3-requirements.yaml"
    with open(output_file, "w") as f:
        f.write(yaml_content)

    print(f"\n✓ Arquivo '{output_file}' gerado com sucesso!")
    print(f"  Python tag: {PYTHON_TAG}")
    print(f"  Arquitetura: {ARCH}")
    print("\nAgora execute novamente:")
    print("  flatpak-builder --repo=repo --force-clean build-dir io.github.narayanls.tacwriter.yml")


if __name__ == "__main__":
    main()
