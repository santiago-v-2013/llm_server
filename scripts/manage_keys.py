import argparse
import sys
from pathlib import Path

# Fix sys.path for direct execution
workspace_dir = Path(__file__).resolve().parents[1]
if str(workspace_dir) not in sys.path:
    sys.path.insert(0, str(workspace_dir))

from src.auth.key_manager import generate_key, list_keys, revoke_key_by_name

def main():
    parser = argparse.ArgumentParser(description="Gestor de API Keys (Autenticación multi-usuario)")
    subparsers = parser.add_subparsers(dest="action", required=True)
    
    create_p = subparsers.add_parser("create", help="Genera una nueva API Key encriptada para un usuario")
    create_p.add_argument("name", help="Nombre del usuario o aplicación")
    
    subparsers.add_parser("list", help="Muestra los usuarios que tienen llaves activas")
    
    revoke_p = subparsers.add_parser("revoke", help="Revoca (elimina) todas las llaves de un usuario")
    revoke_p.add_argument("name", help="Nombre del usuario a revocar")
    
    args = parser.parse_args()
    
    if args.action == "create":
        new_key = generate_key(args.name)
        print(f"✅ Llave creada con éxito para el usuario '{args.name}'")
        print(f"🔑 API_KEY: {new_key}")
        print("⚠️  IMPORTANTE: Guarda esta llave AHORA. Por seguridad matemática (SHA-256), en nuestra base de datos solo se almacena la firma encriptada (hash). ¡No podrás volver a verla!")
        
    elif args.action == "list":
        keys = list_keys()
        if not keys:
            print("No hay llaves activas.")
        else:
            print(f"{'USUARIO':<20} | {'FECHA DE CREACIÓN'}")
            print("-" * 45)
            for name, date in keys:
                print(f"{name:<20} | {date}")
                
    elif args.action == "revoke":
        revoke_key_by_name(args.name)
        print(f"🗑️  Se han revocado permanentemente las llaves del usuario '{args.name}'.")

if __name__ == "__main__":
    main()
