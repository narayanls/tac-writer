import sqlite3
from datetime import datetime
from pathlib import Path

class DatabaseMerger:
    def __init__(self, local_db_path):
        self.local_db_path = local_db_path

    def merge(self, backup_db_path):
        """
        Mescla dados do backup_db_path para o banco local.
        Retorna um resumo do que foi feito.
        """
        if not Path(backup_db_path).exists():
            raise FileNotFoundError("Arquivo de backup não encontrado")

        # Conectar aos dois bancos
        local_conn = sqlite3.connect(self.local_db_path)
        backup_conn = sqlite3.connect(backup_db_path)
        
        # Configurar para retornar dicionários
        local_conn.row_factory = sqlite3.Row
        backup_conn.row_factory = sqlite3.Row
        
        local_cursor = local_conn.cursor()
        backup_cursor = backup_conn.cursor()

        stats = {
            "projects_added": 0, 
            "projects_updated": 0, 
            "paragraphs_processed": 0
        }

        try:
            # 1. Obter todos os projetos do Backup
            backup_cursor.execute("SELECT * FROM projects")
            backup_projects = backup_cursor.fetchall()

            for b_proj in backup_projects:
                # Tenta achar o projeto localmente pelo ID (UUID)
                # No Tac Writer o ID é TEXT (UUID), então usamos ele como chave primária
                query = "SELECT * FROM projects WHERE id = ?"
                local_cursor.execute(query, (b_proj['id'],))
                local_proj = local_cursor.fetchone()

                if not local_proj:
                    # CENÁRIO 1: Projeto Novo (existe no backup, não no local)
                    cols = list(b_proj.keys())
                    placeholders = ','.join(['?'] * len(cols))
                    col_names = ','.join(cols)
                    values = [b_proj[c] for c in cols]
                    
                    local_cursor.execute(
                        f"INSERT INTO projects ({col_names}) VALUES ({placeholders})", 
                        values
                    )
                    stats["projects_added"] += 1
                else:
                    # CENÁRIO 2: Projeto Existe - Verificar qual é mais recente
                    # Usamos 'modified_at' conforme seu services.py
                    b_time = b_proj['modified_at']
                    l_time = local_proj['modified_at']
                    
                    if b_time > l_time:
                        # Atualiza o projeto local com os dados do backup
                        cols = list(b_proj.keys())
                        set_clause = ', '.join([f"{c} = ?" for c in cols])
                        values = [b_proj[c] for c in cols]
                        values.append(b_proj['id']) # Para o WHERE
                        
                        local_cursor.execute(
                            f"UPDATE projects SET {set_clause} WHERE id = ?", 
                            values
                        )
                        stats["projects_updated"] += 1
                        
                        # Se atualizamos o projeto, limpamos os parágrafos antigos para reescrever
                        # Isso evita duplicidade ou desordem, já que vamos inserir os do backup
                        local_cursor.execute("DELETE FROM paragraphs WHERE project_id = ?", (b_proj['id'],))

                # 2. Mesclar Parágrafos deste Projeto
                # Se o projeto foi adicionado ou atualizado, precisamos garantir que os parágrafos estejam lá
                
                # Primeiro, verificamos se precisamos processar parágrafos.
                # Se o projeto local era mais recente, não tocamos nos parágrafos (preserva o local).
                # Se o projeto do backup era mais recente ou novo, inserimos os parágrafos do backup.
                
                should_process_paragraphs = False
                if not local_proj: 
                    should_process_paragraphs = True # Projeto novo
                elif b_proj['modified_at'] > local_proj['modified_at']:
                    should_process_paragraphs = True # Backup mais novo

                if should_process_paragraphs:
                    # Pegamos os parágrafos do projeto NO BACKUP
                    backup_cursor.execute(
                        "SELECT * FROM paragraphs WHERE project_id = ? ORDER BY \"order\" ASC", 
                        (b_proj['id'],)
                    )
                    backup_paragraphs = backup_cursor.fetchall()

                    # Como deletamos os parágrafos no update (ou é projeto novo), fazemos INSERT
                    # Se não tivéssemos deletado, teríamos que checar um por um, o que é lento e complexo
                    # devido à mudança de ordem dos parágrafos.
                    
                    for b_para in backup_paragraphs:
                        # Verifica se o parágrafo já existe (caso não tenhamos feito o DELETE acima)
                        local_cursor.execute("SELECT 1 FROM paragraphs WHERE id = ?", (b_para['id'],))
                        exists = local_cursor.fetchone()
                        
                        cols = list(b_para.keys())
                        values = [b_para[c] for c in cols]
                        
                        if not exists:
                            placeholders = ','.join(['?'] * len(cols))
                            col_names = ','.join(cols)
                            local_cursor.execute(
                                f"INSERT INTO paragraphs ({col_names}) VALUES ({placeholders})", 
                                values
                            )
                        else:
                            # Se já existe (ex: merge parcial), atualizamos
                            set_clause = ', '.join([f"{c} = ?" for c in cols])
                            values.append(b_para['id'])
                            local_cursor.execute(
                                f"UPDATE paragraphs SET {set_clause} WHERE id = ?", 
                                values
                            )
                            
                        stats["paragraphs_processed"] += 1

            local_conn.commit()
            return stats

        except Exception as e:
            local_conn.rollback()
            raise e
        finally:
            local_conn.close()
            backup_conn.close()
