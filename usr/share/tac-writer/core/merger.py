import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

class DatabaseMerger:
    def __init__(self, local_db_path):
        self.local_db_path = local_db_path

    def merge_from_backup(self, backup_db_path):
        """
        Mescla dados do backup_db_path para o banco local.
        Retorna um resumo do que foi feito.
        """
        if not Path(backup_db_path).exists():
            return {"error": "Arquivo de backup não encontrado"}

        # Conectar aos dois bancos
        local_conn = sqlite3.connect(self.local_db_path)
        backup_conn = sqlite3.connect(backup_db_path)
        
        # Configurar para retornar dicionários (facilita o acesso)
        local_conn.row_factory = sqlite3.Row
        backup_conn.row_factory = sqlite3.Row
        
        local_cursor = local_conn.cursor()
        backup_cursor = backup_conn.cursor()

        stats = {"projects_added": 0, "projects_updated": 0, "paragraphs_added": 0, "paragraphs_updated": 0}

        try:
            # 1. Obter todos os projetos do Backup
            backup_cursor.execute("SELECT * FROM projects")
            backup_projects = backup_cursor.fetchall()

            for b_proj in backup_projects:
                # Tenta achar o projeto localmente pelo UUID (ou título se não tiver UUID ainda)
                # O ideal é ter uma coluna 'uuid'. Se não tiver, usaremos o título como chave (perigoso se renomear)
                
                # Verifique se sua tabela tem coluna UUID. Se não, adapte para usar title.
                # Vou assumir que você tem 'id' e 'title'. O ideal é adicionar UUID.
                
                # Lógica Híbrida: Tenta achar por ID (se for UUID) ou Título
                query = "SELECT * FROM projects WHERE title = ?"
                local_cursor.execute(query, (b_proj['title'],))
                local_proj = local_cursor.fetchone()

                local_project_id = None

                if not local_proj:
                    # CENÁRIO 1: Projeto Novo (existe no backup, não no local)
                    # Inserir projeto
                    cols = list(b_proj.keys())
                    cols.remove('id') # Não copiamos o ID autoincrement, deixamos o local gerar um novo
                    placeholders = ','.join(['?'] * len(cols))
                    col_names = ','.join(cols)
                    values = [b_proj[c] for c in cols]
                    
                    local_cursor.execute(f"INSERT INTO projects ({col_names}) VALUES ({placeholders})", values)
                    local_project_id = local_cursor.lastrowid
                    stats["projects_added"] += 1
                else:
                    # CENÁRIO 2: Projeto Existe
                    local_project_id = local_proj['id']
                    
                    # Verificar quem é mais recente (assumindo coluna updated_at)
                    # Se não tiver updated_at, assumimos que o backup é a verdade se o usuário pediu importação
                    b_time = b_proj.get('updated_at', '')
                    l_time = local_proj.get('updated_at', '')
                    
                    if b_time > l_time:
                        # Atualizar metadados do projeto local
                        # (Update query aqui...)
                        stats["projects_updated"] += 1

                # 2. Mesclar Parágrafos deste Projeto
                # Pegamos os parágrafos do projeto NO BACKUP
                backup_cursor.execute("SELECT * FROM paragraphs WHERE project_id = ?", (b_proj['id'],))
                backup_paragraphs = backup_cursor.fetchall()

                for b_para in backup_paragraphs:
                    # Tenta achar esse parágrafo no projeto LOCAL
                    # Aqui precisamos de uma chave única. Se não tiver UUID no parágrafo, 
                    # tentamos casar pela 'ordem' (position) ou conteúdo.
                    # Supondo que tenha uma coluna 'position' ou 'order_index'
                    
                    local_cursor.execute(
                        "SELECT * FROM paragraphs WHERE project_id = ? AND position = ?", 
                        (local_project_id, b_para['position'])
                    )
                    local_para = local_cursor.fetchone()

                    if not local_para:
                        # Parágrafo novo no backup
                        cols = list(b_para.keys())
                        cols.remove('id')
                        cols.remove('project_id') # Usar o novo ID local
                        
                        placeholders = ','.join(['?'] * (len(cols) + 1)) # +1 para o project_id
                        col_names = ','.join(cols) + ", project_id"
                        
                        values = [b_para[c] for c in cols]
                        values.append(local_project_id)
                        
                        local_cursor.execute(f"INSERT INTO paragraphs ({col_names}) VALUES ({placeholders})", values)
                        stats["paragraphs_added"] += 1
                    else:
                        # Parágrafo existe, verificar conteúdo/data
                        b_content = b_para.get('content', '')
                        l_content = local_para.get('content', '')
                        
                        # Se conteúdo diferente e backup mais novo (ou apenas diferente se não tiver data)
                        if b_content != l_content:
                            # Aqui você pode decidir: sobrescrever ou criar uma cópia?
                            # Vamos sobrescrever assumindo que o backup traz a versão desejada
                            local_cursor.execute(
                                "UPDATE paragraphs SET content = ?, updated_at = ? WHERE id = ?",
                                (b_content, datetime.now().isoformat(), local_para['id'])
                            )
                            stats["paragraphs_updated"] += 1

            local_conn.commit()
            return stats

        except Exception as e:
            local_conn.rollback()
            raise e
        finally:
            local_conn.close()
            backup_conn.close()
