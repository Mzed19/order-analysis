import time
from app.services.analyze_contract_service import analyze_contract
from app.workers.task_queue import dequeue_task, update_task_status, update_task_result, update_task_progress
from app.services.metrics_service import init_metrics_table, record_metric

def run_worker() -> None:
    print("Contract analysis worker started...")
    while True:
        try:
            task = dequeue_task()
            if task:
                task_id = task["id"]
                contract_text = task["contract_text"]
                filename = task["filename"]
                print(f"Processing task {task_id}...")
                update_task_status(task_id, "processing")
                try:
                    def progress_callback(chunks_quantity=None, analyzed_chunks_quantity=None):
                        update_task_progress(task_id, chunks_quantity, analyzed_chunks_quantity)
                    
                    analyses = analyze_contract(contract_text, filename, progress_callback=progress_callback)
                    update_task_result(task_id, analyses, "completed")
                    
                    # Gravar métrica no PostgreSQL (com tratamento isolado para não falhar a análise em caso de erro no DB)
                    try:
                        user_name = task.get("user_name", "Usuário Desconhecido")
                        record_metric(user_name, filename or "Documento sem nome")
                    except Exception as me:
                        print(f"Warning: Failed to record metrics: {me}")
                    
                    print(f"Task {task_id} completed.")
                except Exception as e:
                    update_task_result(task_id, str(e), "failed")
                    print(f"Task {task_id} failed: {e}")
        except Exception as e:
            print(f"Worker loop error (will retry in 5s): {e}")
            time.sleep(5)

if __name__ == "__main__":
    init_metrics_table()
    run_worker()
