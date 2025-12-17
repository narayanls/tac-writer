import os

# Caminho baseado na sua estrutura 'tree'
icons_dir = os.path.join("usr", "share", "tac-writer", "icons")

# Arquivos que NÃO devem ser renomeados
ignore_list = ["index.theme", "tac-writer.svg"]

# Dicionário para guardar o "De -> Para" (útil para o próximo passo)
changes = {}

def main():
    if not os.path.exists(icons_dir):
        print(f"Erro: Diretório não encontrado: {icons_dir}")
        print("Certifique-se de rodar este script na raiz do projeto.")
        return

    print(f"Processando ícones em: {icons_dir}...\n")

    files = os.listdir(icons_dir)
    count = 0

    for filename in files:
        # Pula arquivos ignorados ou que não são SVG
        if filename in ignore_list or not filename.endswith(".svg"):
            continue

        # Evita renomear se já tiver o prefixo (caso rode o script 2 vezes)
        if filename.startswith("tac-") and filename != "tac-writer.svg":
            print(f"Ignorando (já renomeado): {filename}")
            continue

        # Define o novo nome
        new_name = f"tac-{filename}"
        
        old_path = os.path.join(icons_dir, filename)
        new_path = os.path.join(icons_dir, new_name)

        try:
            os.rename(old_path, new_path)
            
            # Guarda o mapeamento para ajudar a alterar o código depois
            # Removemos a extensão e o sufixo -symbolic para facilitar a busca no código
            key_name = filename.replace("-symbolic.svg", "")
            val_name = new_name.replace("-symbolic.svg", "")
            changes[key_name] = val_name
            
            print(f"Renomeado: {filename} -> {new_name}")
            count += 1
        except OSError as e:
            print(f"Erro ao renomear {filename}: {e}")

    print(f"\nConcluído! {count} arquivos renomeados.")
    print("-" * 40)
    print("COPIE O DICIONÁRIO ABAIXO (Vamos usar para atualizar o código):")
    print("-" * 40)
    print(changes)

if __name__ == "__main__":
    main()
