"""
添加 cancelled 字段到 subtitle_tasks 和 burn_subtitle_tasks 表
"""
import sqlite3
import sys
from pathlib import Path

def add_cancelled_field():
    """添加 cancelled 字段"""
    # 找到数据库文件
    db_path = Path.home() / "AppData" / "Roaming" / "VidFlow" / "data" / "vidflow.db"

    if not db_path.exists():
        print(f"数据库文件不存在: {db_path}")
        return False

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # 检查 subtitle_tasks 表是否存在 cancelled 字段
        cursor.execute("PRAGMA table_info(subtitle_tasks)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'cancelled' not in columns:
            print("正在添加 cancelled 字段到 subtitle_tasks 表...")
            cursor.execute("""
                ALTER TABLE subtitle_tasks
                ADD COLUMN cancelled INTEGER DEFAULT 0 NOT NULL
            """)
            print("✓ subtitle_tasks 表已添加 cancelled 字段")
        else:
            print("✓ subtitle_tasks 表已有 cancelled 字段")

        # 检查 burn_subtitle_tasks 表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='burn_subtitle_tasks'
        """)

        if cursor.fetchone():
            # 检查是否有 cancelled 字段
            cursor.execute("PRAGMA table_info(burn_subtitle_tasks)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'cancelled' not in columns:
                print("正在添加 cancelled 字段到 burn_subtitle_tasks 表...")
                cursor.execute("""
                    ALTER TABLE burn_subtitle_tasks
                    ADD COLUMN cancelled INTEGER DEFAULT 0 NOT NULL
                """)
                print("✓ burn_subtitle_tasks 表已添加 cancelled 字段")
            else:
                print("✓ burn_subtitle_tasks 表已有 cancelled 字段")
        else:
            print("⚠ burn_subtitle_tasks 表不存在，跳过")

        conn.commit()
        print("\n数据库迁移完成!")
        return True

    except Exception as e:
        print(f"错误: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = add_cancelled_field()
    sys.exit(0 if success else 1)
