from infra.database.postgres import get_conn, release_conn
from datetime import datetime

def init_metrics_table():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id SERIAL PRIMARY KEY,
                    user_name TEXT NOT NULL,
                    document_name TEXT NOT NULL,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            print("Table 'metrics' checked/created.")
    except Exception as e:
        print(f"Error initializing metrics table: {e}")
        conn.rollback()
    finally:
        release_conn(conn)

def record_metric(user_name: str, document_name: str):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO metrics (user_name, document_name) VALUES (%s, %s)",
                (user_name, document_name)
            )
            conn.commit()
            print(f"Metric recorded: {user_name} analyzed {document_name}")
    except Exception as e:
        print(f"Error recording metric: {e}")
        conn.rollback()
    finally:
        release_conn(conn)
