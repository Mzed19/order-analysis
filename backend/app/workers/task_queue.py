import json
import os
import uuid
from datetime import datetime
from typing import Any

import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_TASK_TTL = int(os.getenv("REDIS_TASK_TTL", "86400"))

client = redis.Redis.from_url(
    REDIS_URL, 
    decode_responses=True,
    socket_timeout=60,
    socket_connect_timeout=10,
    health_check_interval=30
)

QUEUE_NAME = "contract_analysis_queue"
TASK_PREFIX = "analysis_task:"


def _make_task_key(task_id: str) -> str:
    return f"{TASK_PREFIX}{task_id}"


def enqueue_task(contract_text: str, filename: str | None, user_id: str, user_name: str) -> str:
    task_id = str(uuid.uuid4())
    task_data = {
        "id": task_id,
        "user_id": user_id,
        "user_name": user_name,
        "status": "queued",
        "result": None,
        "chunks_quantity": None,
        "analyzed_chunks_quantity": None,
        "contract_text": contract_text,
        "filename": filename,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    client.lpush(QUEUE_NAME, json.dumps(task_data))
    client.setex(_make_task_key(task_id), REDIS_TASK_TTL, json.dumps(task_data))
    return task_id

def task_exists(task_id: str) -> bool:
    return client.exists(_make_task_key(task_id)) > 0

def dequeue_task(timeout: int = 5) -> dict[str, Any] | None:
    # BRPOP é bloqueante e mais eficiente para múltiplos workers
    result = client.brpop(QUEUE_NAME, timeout=timeout)
    if result:
        _, task_json = result
        return json.loads(task_json)
    return None

def update_task_result(task_id: str, result: list[str], status: str) -> None:
    task_data_json = client.get(_make_task_key(task_id))
    if task_data_json:
        task_data = json.loads(task_data_json)
        task_data["result"] = result
        task_data["status"] = status
        client.setex(_make_task_key(task_id), REDIS_TASK_TTL, json.dumps(task_data))

def update_task_status(task_id: str, status: str) -> None:
    task_data_json = client.get(_make_task_key(task_id))
    if task_data_json:
        task_data = json.loads(task_data_json)
        task_data["status"] = status
        client.setex(_make_task_key(task_id), REDIS_TASK_TTL, json.dumps(task_data))

def update_task_progress(task_id: str, chunks_quantity: int | None = None, analyzed_chunks_quantity: int | None = None) -> None:
    task_data_json = client.get(_make_task_key(task_id))
    if task_data_json:
        task_data = json.loads(task_data_json)
        if chunks_quantity is not None:
            task_data["chunks_quantity"] = chunks_quantity
        if analyzed_chunks_quantity is not None:
            task_data["analyzed_chunks_quantity"] = analyzed_chunks_quantity
        client.setex(_make_task_key(task_id), REDIS_TASK_TTL, json.dumps(task_data))

def get_task(task_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    result_json = client.get(_make_task_key(task_id))
    if result_json:
        task_data = json.loads(result_json)
        # Se um user_id for fornecido, validar a posse
        if user_id and task_data.get("user_id") != user_id:
            return None
        return task_data
    return None

def list_tasks(user_id: str | None = None) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for key in client.scan_iter(f"{TASK_PREFIX}*"):
        task_json = client.get(key)
        if not task_json:
            continue
        try:
            task_data = json.loads(task_json)
            # Filtrar por usuário se o user_id for fornecido
            if user_id and task_data.get("user_id") != user_id:
                continue
            tasks.append(task_data)
        except json.JSONDecodeError:
            continue
    tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return tasks

def delete_task(task_id: str, user_id: str) -> bool:
    task_key = _make_task_key(task_id)
    task_json = client.get(task_key)
    if not task_json:
        return False
    
    task_data = json.loads(task_json)
    if task_data.get("user_id") != user_id:
        return False
    
    client.delete(task_key)
    return True