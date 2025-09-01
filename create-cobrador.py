# create_admin.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

# COPIA Y PEGA LA MISMA CONFIGURACIÓN DE TU APP.PY
app = Flask(__name__)
DB_USER = "u718598814_panconqueso"
DB_PASS = "Miloyfrutas!1"
DB_HOST = "srv1264.hstgr.io"
DB_NAME = "u718598814_creditossas1"

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    rol = db.Column(db.String(50), nullable=False, default='cobrador')

# --- SCRIPT DE CREACIÓN ---
def crear_usuario():
    with app.app_context():
        print("--- Creando nuevo usuario ---")
        username = input("Ingresa el nombre de usuario: ")
        password = input("Ingresa la contraseña: ")
        rol = input("Ingresa el rol ('admin' o 'cobrador'): ").lower()

        if rol not in ['admin', 'cobrador']:
            print("Error: Rol inválido. Debe ser 'admin' o 'cobrador'.")
            return

        usuario_existente = Usuario.query.filter_by(username=username).first()
        if usuario_existente:
            print(f"Error: El usuario '{username}' ya existe.")
            return

        password_hasheado = bcrypt.generate_password_hash(password).decode('utf-8')
        nuevo_usuario = Usuario(username=username, password_hash=password_hasheado, rol=rol)
        
        db.session.add(nuevo_usuario)
        db.session.commit()
        print(f"¡Éxito! Usuario '{username}' con rol '{rol}' creado correctamente.")

if __name__ == '__main__':
    crear_usuario()

