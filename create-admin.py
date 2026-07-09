# create_admin.py
import os
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

# Carga la configuración desde .env (mismas variables que app.py)
load_dotenv()
app = Flask(__name__)
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')
DB_HOST = os.environ.get('DB_HOST')
DB_NAME = os.environ.get('DB_NAME')

if not all([DB_USER, DB_PASS, DB_HOST, DB_NAME]):
    raise ValueError("Faltan variables de entorno para la base de datos. Configura el archivo .env")

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    rol = db.Column(db.String(50), nullable=False, default='cobrador')

# --- SCRIPT DE CREACIÓN ---
def crear_usuario_admin():
    with app.app_context():
        print("--- Creando usuario administrador ---")
        
        # Pide los datos por consola
        username = input("Ingresa el nombre de usuario para el admin: ")
        password = input("Ingresa la contraseña para el admin: ")
        
        # Verifica si el usuario ya existe
        usuario_existente = Usuario.query.filter_by(username=username).first()
        if usuario_existente:
            print(f"Error: El usuario '{username}' ya existe.")
            return

        # Hashea la contraseña
        password_hasheado = bcrypt.generate_password_hash(password).decode('utf-8')
        
        # Crea el nuevo usuario con el rol de 'admin'
        nuevo_admin = Usuario(username=username, password_hash=password_hasheado, rol='admin')
        
        db.session.add(nuevo_admin)
        db.session.commit()
        
        print(f"¡Éxito! Usuario administrador '{username}' creado correctamente.")

if __name__ == '__main__':
    crear_usuario_admin()

