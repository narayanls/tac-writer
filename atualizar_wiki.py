import os

# Configuração dos links
OLD_URL = "https://github.com/big-comm/comm-tac-writer/wiki"
NEW_URL = "https://github.com/narayanls/tac-writer/wiki"

# Extensões de arquivos que serão verificados
EXTENSIONS = ('.py', '.md', '.txt', '.ui', '.desktop', '.json', '.xml', 'PKGBUILD')

def main():
    base_dir = os.getcwd()
    files_changed = 0
    
    print(f"Iniciando varredura em: {base_dir}")
    print(f"Procurando: {OLD_URL}")
    print(f"Trocando por: {NEW_URL}")
    print("-" * 50)

    for root, dirs, files in os.walk(base_dir):
        # Ignorar pastas de sistema/git/cache
        if '.git' in dirs: dirs.remove('.git')
        if '__pycache__' in dirs: dirs.remove('__pycache__')
        
        for file in files:
            # Verifica se é um arquivo de texto relevante
            if file.endswith(EXTENSIONS) or file == 'PKGBUILD':
                # Não processar o próprio script
                if file == "atualizar_wiki.py":
                    continue

                filepath = os.path.join(root, file)

                try:
                    # Tenta ler o arquivo
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Se encontrar o link antigo, substitui
                    if OLD_URL in content:
                        count = content.count(OLD_URL)
                        new_content = content.replace(OLD_URL, NEW_URL)

                        # Salva o arquivo alterado
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(new_content)

                        print(f"[ATUALIZADO] {filepath} ({count} ocorrências)")
                        files_changed += 1

                except UnicodeDecodeError:
                    # Ignora arquivos binários que por acaso tenham extensão de texto
                    pass
                except Exception as e:
                    print(f"[ERRO] Não foi possível ler {filepath}: {e}")

    print("-" * 50)
    print(f"Concluído! Total de arquivos alterados: {files_changed}")

if __name__ == "__main__":
    main()
