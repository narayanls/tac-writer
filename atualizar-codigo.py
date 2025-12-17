import os

# Dicionário gerado pelo passo anterior
ICON_MAP = {
    'accessories-text-editor': 'tac-accessories-text-editor',
    'alarm': 'tac-alarm',
    'dialog-warning': 'tac-dialog-warning',
    'document-edit': 'tac-document-edit',
    'document-new': 'tac-document-new',
    'document-revert': 'tac-document-revert',
    'document-save': 'tac-document-save',
    'edit-delete': 'tac-edit-delete',
    'edit': 'tac-edit',
    'emblem-ok': 'tac-emblem-ok',
    'go-down': 'tac-go-down',
    'go-up': 'tac-go-up',
    'help-browser': 'tac-help-browser',
    'list-add': 'tac-list-add',
    'open-menu': 'tac-open-menu',
    'preferences-system': 'tac-preferences-system',
    'text-x-generic': 'tac-text-x-generic',
    'tools-check-spelling': 'tac-tools-check-spelling',
    'user-trash': 'tac-user-trash',
    'window-minimize': 'tac-window-minimize'
}

def main():
    # Define onde procurar os arquivos de código
    base_dir = os.path.join("usr", "share", "tac-writer")
    
    # Extensões de arquivos que podem conter referências a ícones
    extensions = (".py", ".ui", ".xml")
    
    print(f"Iniciando varredura em: {base_dir}...")
    
    total_files_changed = 0
    total_replacements = 0

    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith(extensions):
                filepath = os.path.join(root, file)
                
                # Ignora os scripts de manutenção
                if file in ["renomear_icones.py", "atualizar_codigo.py"]:
                    continue

                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    new_content = content
                    file_changed = False
                    
                    # Para cada ícone no mapa, tenta substituir no arquivo
                    for old_name, new_name in ICON_MAP.items():
                        # O código geralmente referencia com o sufixo -symbolic
                        # Ex: "help-browser-symbolic" -> "tac-help-browser-symbolic"
                        
                        old_str = f"{old_name}-symbolic"
                        new_str = f"{new_name}-symbolic"
                        
                        if old_str in new_content:
                            count = new_content.count(old_str)
                            new_content = new_content.replace(old_str, new_str)
                            
                            print(f"  [ALTERADO] {file}: {old_str} -> {new_str} ({count}x)")
                            file_changed = True
                            total_replacements += count

                    if file_changed:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        total_files_changed += 1
                        
                except Exception as e:
                    print(f"Erro ao ler {filepath}: {e}")

    print("\n" + "="*40)
    print(f"Concluído!")
    print(f"Arquivos alterados: {total_files_changed}")
    print(f"Total de substituições: {total_replacements}")
    print("="*40)

if __name__ == "__main__":
    main()
