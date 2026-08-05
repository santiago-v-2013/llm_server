import sys
import time
import subprocess
import urllib.request
import urllib.error
import json
import yaml
import shutil
from pathlib import Path

workspace_dir = Path(__file__).resolve().parents[1]
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))
from src.auth.key_manager import generate_key, revoke_key_by_name

config_dir = workspace_dir / "config"
backup_dir = workspace_dir / "config_backup"
YAML_FILES = ["api.yaml", "llm.yaml", "media.yaml", "vision.yaml"]

PIXEL_B64 = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAF0lEQVR4nGP8z0AaYCJR/aiGUQ1DSAMAQC4BH2bjRnMAAAAASUVORK5CYII="

class TestRunner:
    @staticmethod
    def backup_configs():
        if not backup_dir.exists():
            backup_dir.mkdir()
        for file in YAML_FILES:
            src = config_dir / file
            dst = backup_dir / file
            if src.exists():
                shutil.copy2(src, dst)

    @staticmethod
    def restore_configs():
        for file in YAML_FILES:
            src = backup_dir / file
            dst = config_dir / file
            if src.exists():
                shutil.copy2(src, dst)
        if backup_dir.exists():
            shutil.rmtree(backup_dir)

    @staticmethod
    def update_yaml(filename, updates):
        path = config_dir / filename
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            
        def recursive_update(d, u):
            for k, v in u.items():
                if isinstance(v, dict):
                    d[k] = recursive_update(d.get(k, {}), v)
                else:
                    d[k] = v
            return d
            
        data = recursive_update(data, updates)
        
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)

    @staticmethod
    def wait_for_server(url, timeout=600):
        import socket
        
        # Read api.yaml to determine which internal ports should be active
        api_path = config_dir / "api.yaml"
        with open(api_path, "r", encoding="utf-8") as f:
            api_data = yaml.safe_load(f) or {}
            
        engines = api_data.get("active_engines", {})
        
        # 5000 is Gunicorn (always checked)
        ports_to_check = [5000]
        
        if engines.get("llm") == "huggingface":
            ports_to_check.append(8000)
        if engines.get("media") == "diffusers":
            ports_to_check.append(5001)
        if engines.get("vision") in ["transformers", "huggingface"]:
            ports_to_check.append(5002)
            
        start_time = time.time()
        for port in ports_to_check:
            connected = False
            while time.time() - start_time < timeout:
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=1):
                        connected = True
                        break
                except OSError:
                    time.sleep(2)
            if not connected:
                return False
        return True

    @staticmethod
    def run_test(name, config_updates, endpoint, payload, expected_status=200):
        print(f"\n==================================================")
        print(f"🧪 Iniciando Test: {name}")
        print(f"==================================================")
        
        # Generar una clave temporal y hasheada para los tests
        revoke_key_by_name("test_runner")
        test_api_key = generate_key("test_runner")
        
        TestRunner.backup_configs()
        
        base_api = {"active_engines": {"llm": "none", "media": "none", "vision": "none"}}
        TestRunner.update_yaml("api.yaml", base_api)
        
        for filename, updates in config_updates.items():
            TestRunner.update_yaml(filename, updates)
            
        print("[*] Levantando orquestador y motores...")
        process = subprocess.Popen([sys.executable, str(workspace_dir / "scripts" / "orchestrator.py")])
        
        url = f"http://127.0.0.1:5000{endpoint}"
        if not TestRunner.wait_for_server(url):
            print(f"❌ Error: El servidor nunca levantó.")
            process.terminate()
            process.wait()
            TestRunner.restore_configs()
            sys.exit(1)
            
        print("[*] Servidor listo. Enviando petición...")
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json', 'X-API-KEY': test_api_key})
        
        try:
            with urllib.request.urlopen(req) as response:
                status = response.status
                res_body = json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            status = e.code
            res_body = json.loads(e.read().decode())
        except Exception as e:
            status = 0
            res_body = str(e)
            
        success = status == expected_status
        if success:
            print(f"✅ Éxito! (Status: {status})")
        else:
            print(f"❌ Fallo! (Esperado: {expected_status}, Recibido: {status})")
            print(f"   Respuesta: {res_body}")
            
        print("[*] Apagando servidor...")
        process.terminate()
        process.wait()
        time.sleep(2)
        
        TestRunner.restore_configs()
        
        if not success:
            sys.exit(1)
