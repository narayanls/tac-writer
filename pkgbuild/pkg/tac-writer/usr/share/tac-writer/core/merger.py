import sqlite3
from datetime import datetime
from pathlib import Path

class DatabaseMerger:
    def __init__(self, local_db_path):
        self.local_db_path = local_db_path

    def merge(self, backup_db_path):
        """
        Merge data backup_db_path for data local.
        Returns resume of what it's done.
        """
        if not Path(backup_db_path).exists():
            raise FileNotFoundError("Arquivo de backup não encontrado")

        # Connect to both banks
        local_conn = sqlite3.connect(self.local_db_path)
        backup_conn = sqlite3.connect(backup_db_path)
        
        # Configure to return dictionaries
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
            # Get all projects from Backup
            backup_cursor.execute("SELECT * FROM projects")
            backup_projects = backup_cursor.fetchall()

            for b_proj in backup_projects:
                # Try to find the project locally by ID
                query = "SELECT * FROM projects WHERE id = ?"
                local_cursor.execute(query, (b_proj['id'],))
                local_proj = local_cursor.fetchone()

                if not local_proj:
                    # SCENARIO 1: New Project
                    cols = list(b_proj.keys())
                    placeholders = ','.join(['?'] * len(cols))
                    # Add " in columms name (ex: "name", "metadata")
                    col_names = ','.join([f'"{c}"' for c in cols])
                    values = [b_proj[c] for c in cols]
                    
                    local_cursor.execute(
                        f"INSERT INTO projects ({col_names}) VALUES ({placeholders})", 
                        values
                    )
                    stats["projects_added"] += 1
                else:
                    # SCENARIO 2: Project Exists - Check date
                    b_time = b_proj['modified_at']
                    l_time = local_proj['modified_at']
                    
                    if b_time > l_time:
                        # Update the local project
                        cols = list(b_proj.keys())
                        # Add " in SET clause (ex: "name" = ?)
                        set_clause = ', '.join([f'"{c}" = ?' for c in cols])
                        values = [b_proj[c] for c in cols]
                        values.append(b_proj['id']) # Para o WHERE
                        
                        local_cursor.execute(
                            f"UPDATE projects SET {set_clause} WHERE id = ?", 
                            values
                        )
                        stats["projects_updated"] += 1
                        
                        # Cleans up old paragraphs for rewriting
                        local_cursor.execute("DELETE FROM paragraphs WHERE project_id = ?", (b_proj['id'],))

                # 2. Merge Paragraphs
                should_process_paragraphs = False
                if not local_proj: 
                    should_process_paragraphs = True
                elif b_proj['modified_at'] > local_proj['modified_at']:
                    should_process_paragraphs = True

                if should_process_paragraphs:
                    backup_cursor.execute(
                        'SELECT * FROM paragraphs WHERE project_id = ? ORDER BY "order" ASC', 
                        (b_proj['id'],)
                    )
                    backup_paragraphs = backup_cursor.fetchall()

                    for b_para in backup_paragraphs:
                        # Check existence
                        local_cursor.execute("SELECT 1 FROM paragraphs WHERE id = ?", (b_para['id'],))
                        exists = local_cursor.fetchone()
                        
                        cols = list(b_para.keys())
                        values = [b_para[c] for c in cols]
                        
                        if not exists:
                            placeholders = ','.join(['?'] * len(cols))
                            col_names = ','.join([f'"{c}"' for c in cols])
                            
                            local_cursor.execute(
                                f"INSERT INTO paragraphs ({col_names}) VALUES ({placeholders})", 
                                values
                            )
                        else:
                            # Update existing paragraph
                            set_clause = ', '.join([f'"{c}" = ?' for c in cols])
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
