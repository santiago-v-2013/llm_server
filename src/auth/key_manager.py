import sqlite3
import hashlib
import secrets
import datetime
from pathlib import Path

workspace_dir = Path(__file__).resolve().parents[2]
DB_PATH = workspace_dir / "config" / "auth.db"

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS api_keys (
            key_hash TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    return conn

def hash_key(raw_key: str) -> str:
    """Hashea la clave con SHA-256 para almacenamiento unidireccional seguro"""
    return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

def generate_key(name: str) -> str:
    """Genera una llave aleatoria criptográficamente segura, la hashea, la almacena y devuelve la llave plana una única vez."""
    raw_token = secrets.token_urlsafe(32)
    api_key = f"sk-{raw_token}"
    
    key_hash = hash_key(api_key)
    created_at = datetime.datetime.utcnow().isoformat()
    
    with _get_conn() as conn:
        conn.execute("INSERT INTO api_keys (key_hash, name, created_at) VALUES (?, ?, ?)",
                    (key_hash, name, created_at))
    return api_key

def validate_key(raw_key: str) -> bool:
    """Verifica si la llave proporcionada coincide con algún hash almacenado."""
    if not raw_key:
        return False
        
    key_hash = hash_key(raw_key)
    with _get_conn() as conn:
        cursor = conn.execute("SELECT 1 FROM api_keys WHERE key_hash = ?", (key_hash,))
        return cursor.fetchone() is not None

def list_keys():
    """Devuelve la lista de usuarios y fechas de creación (sin exponer hashes)"""
    with _get_conn() as conn:
        cursor = conn.execute("SELECT name, created_at FROM api_keys")
        return cursor.fetchall()

def revoke_key_by_name(name: str):
    """Elimina las claves asociadas a un nombre"""
    with _get_conn() as conn:
        conn.execute("DELETE FROM api_keys WHERE name = ?", (name,))
