import os
import logging
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime, date, timedelta
from sqlalchemy import func, or_
from flask_migrate import Migrate

load_dotenv()

# --- CONFIGURACIÓN INICIAL ---
app = Flask(__name__)

# --- Clave Secreta Fija (para que no te desloguee) ---
# Recuerda generar la tuya con: python -c 'import secrets; print(secrets.token_hex(16))'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'una_clave_por_defecto_para_desarrollo')

# --- Conexión a la Base de Datos de Hostinger ---
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')
DB_HOST = os.environ.get('DB_HOST')
DB_NAME = os.environ.get('DB_NAME')

# Construimos la cadena de conexión solo si todas las variables existen
if not all([DB_USER, DB_PASS, DB_HOST, DB_NAME]):
    raise ValueError("Faltan variables de entorno para la base de datos. Asegúrate de configurar el archivo .env")

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"


# --- INICIALIZACIÓN DE COMPONENTES ---
db = SQLAlchemy(app)
migrate = Migrate(app, db) # Objeto para las migraciones
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'
login_manager.login_message_category = 'warning'
logging.basicConfig(level=logging.INFO)

# --- MODELOS DE BASE DE DATOS ---
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    rol = db.Column(db.String(50), nullable=False, default='cobrador')
    
    prestamos_asignados = db.relationship('Prestamo', backref='cobrador', lazy=True)


class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cedula = db.Column(db.String(20), unique=True, nullable=False)
    nombre_completo = db.Column(db.String(120), nullable=False)
    direccion = db.Column(db.String(200), nullable=True)
    telefono = db.Column(db.String(20), nullable=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    prestamos = db.relationship('Prestamo', backref='cliente', lazy=True)

class Prestamo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monto_prestado = db.Column(db.Float, nullable=False)
    tasa_interes_mensual = db.Column(db.Float, nullable=False)
    plazo_meses = db.Column(db.Integer, nullable=False)
    monto_total_a_pagar = db.Column(db.Float, nullable=False)
    frecuencia = db.Column(db.String(20), default='diaria', nullable=False)
    fecha_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.String(20), default='activo')
    cobrar_sabado = db.Column(db.Boolean, default=True)
    cobrar_domingo = db.Column(db.Boolean, default=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    cuotas = db.relationship('Cuota', backref='prestamo', lazy=True, cascade="all, delete-orphan")

class Cuota(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monto_cuota = db.Column(db.Float, nullable=False)
    fecha_vencimiento = db.Column(db.Date, nullable=False)
    estado = db.Column(db.String(20), default='pendiente')
    fecha_de_pago = db.Column(db.DateTime, nullable=True)
    notas = db.Column(db.Text, nullable=True)
    prestamo_id = db.Column(db.Integer, db.ForeignKey('prestamo.id'), nullable=False)

class Configuracion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(50), unique=True, nullable=False)
    valor = db.Column(db.Text, nullable=True)


@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.rol == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('cobrador_dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = Usuario.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user)
            if user.rol == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('cobrador_dashboard'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión exitosamente.', 'success')
    return redirect(url_for('login'))

# --- RUTAS PÚBLICAS Y SIMULADOR ---

@app.route('/simulador')
def simulador():
    return render_template('simulador.html')

# --- RUTAS DE ADMINISTRADOR ---

# En app.py, reemplaza esta función completa
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.rol != 'admin':
        return redirect(url_for('cobrador_dashboard'))

    prestamos_activos = Prestamo.query.filter_by(estado='activo').all()
    today = date.today()
    limite_proximo_vencer = today + timedelta(days=3)

    total_prestado = 0
    total_recaudado = 0

    for prestamo in prestamos_activos:
        total_prestado += prestamo.monto_prestado
        pagado = sum(c.monto_cuota for c in prestamo.cuotas if c.estado in ['pagada', 'pagada_tarde'])
        total_recaudado += pagado
        progreso = (pagado / prestamo.monto_total_a_pagar) * 100 if prestamo.monto_total_a_pagar > 0 else 0
        prestamo.progreso = int(progreso)
        
        prestamo.estado_visual = 'al_dia'
        
        proxima_cuota_pendiente = None
        for cuota in sorted(prestamo.cuotas, key=lambda c: c.fecha_vencimiento):
            if cuota.estado == 'pendiente':
                proxima_cuota_pendiente = cuota
                break
        
        if proxima_cuota_pendiente:
            # LÓGICA DE ESTADO CORREGIDA
            if proxima_cuota_pendiente.fecha_vencimiento < today:
                prestamo.estado_visual = 'en_mora'
            # El estado "Próximo a Vencer" solo aplica si NO es diario
            elif prestamo.frecuencia != 'diaria' and proxima_cuota_pendiente.fecha_vencimiento <= limite_proximo_vencer:
                prestamo.estado_visual = 'proximo_vencer'

    cartera_pendiente = total_prestado - total_recaudado
    metricas = {
        "total_prestado": f"{total_prestado:,.0f}",
        "total_recaudado": f"{total_recaudado:,.0f}",
        "cartera_pendiente": f"{cartera_pendiente:,.0f}",
        "clientes_activos": len(prestamos_activos)
    }
    
    return render_template('admin.html', metricas=metricas, prestamos=prestamos_activos)
    

# dashboard inicial del cobrador o llamar al admin
@app.route('/dashboard')
@login_required
def cobrador_dashboard():
    if current_user.rol != 'cobrador':
        return redirect(url_for('admin_dashboard'))
    prestamos_asignados = Prestamo.query.filter_by(usuario_id=current_user.id, estado='activo').all()
    return render_template('cobrador.html', prestamos=prestamos_asignados)


# busqueda de cliente por cédula (API)
@app.route('/api/buscar_cliente/<cedula>')
@login_required
def buscar_cliente(cedula):
    cliente = Cliente.query.filter_by(cedula=cedula).first()
    if cliente:
        # Si encontramos el cliente, devolvemos sus datos en formato JSON
        return {
            "encontrado": True,
            "nombre_completo": cliente.nombre_completo,
            "telefono": cliente.telefono,
            "direccion": cliente.direccion
        }
    else:
        # Si no lo encontramos, devolvemos una respuesta indicándolo
        return {"encontrado": False}


@app.route('/prestamo/crear', methods=['GET', 'POST'])
@login_required
def crear_prestamo():
    if request.method == 'POST':
        # --- Parte 1: Recopilación de datos (sin cambios) ---
        cedula = request.form.get('cedula')
        nombre = request.form.get('nombre_completo')
        telefono = request.form.get('telefono')
        direccion = request.form.get('direccion')
        monto = float(request.form.get('monto'))
        plazo = int(request.form.get('plazo'))
        interes = float(request.form.get('interes'))
        frecuencia = request.form.get('frecuencia')
        cobrador_id = request.form.get('cobrador_id', current_user.id)
        cobrar_sabado = 'cobrarSabado' in request.form
        cobrar_domingo = 'cobrarDomingo' in request.form

        # --- Parte 2: Gestión del cliente y préstamo (sin cambios) ---
        cliente = Cliente.query.filter_by(cedula=cedula).first()
        if not cliente:
            cliente = Cliente(cedula=cedula, nombre_completo=nombre, telefono=telefono, direccion=direccion)
            db.session.add(cliente)
        
        total_a_pagar = monto * (1 + (interes / 100) * plazo)
        
        nuevo_prestamo = Prestamo(
            monto_prestado=monto, tasa_interes_mensual=interes, plazo_meses=plazo,
            monto_total_a_pagar=total_a_pagar, frecuencia=frecuencia,
            cobrar_sabado=cobrar_sabado, cobrar_domingo=cobrar_domingo,
            cliente=cliente, usuario_id=cobrador_id
        )

        # --- Parte 3: GENERACIÓN DE CUOTAS (LÓGICA CORREGIDA) ---
        numero_cuotas = 0
        if frecuencia == 'diaria': numero_cuotas = plazo * 26
        elif frecuencia == 'semanal': numero_cuotas = plazo * 4
        elif frecuencia == 'quincenal': numero_cuotas = plazo * 2
        elif frecuencia == 'mensual': numero_cuotas = plazo
        
        if numero_cuotas > 0:
            valor_cuota = round(total_a_pagar / numero_cuotas, 2)
            # CORRECCIÓN 1: La fecha inicial ahora es mañana
            fecha_actual = date.today() + timedelta(days=1)

            for _ in range(numero_cuotas):
                if frecuencia == 'diaria':
                    # Avanza hasta encontrar un día de pago válido
                    while True:
                        dia_semana = fecha_actual.weekday()
                        if (dia_semana == 6 and not cobrar_domingo) or (dia_semana == 5 and not cobrar_sabado):
                            fecha_actual += timedelta(days=1)
                        else:
                            break
                
                # CORRECCIÓN 2: Lógica iterativa para todas las frecuencias
                cuota_vencimiento = fecha_actual
                
                cuota = Cuota(monto_cuota=valor_cuota, fecha_vencimiento=cuota_vencimiento, prestamo=nuevo_prestamo)
                db.session.add(cuota)

                # Avanzamos la fecha para la SIGUIENTE cuota
                if frecuencia == 'diaria': fecha_actual += timedelta(days=1)
                elif frecuencia == 'semanal': fecha_actual += timedelta(weeks=1)
                elif frecuencia == 'quincenal': fecha_actual += timedelta(days=15)
                elif frecuencia == 'mensual': fecha_actual += timedelta(days=30) # Aproximación simple

        try:
            db.session.add(nuevo_prestamo)
            db.session.commit()
            flash('Préstamo creado exitosamente.', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el préstamo: {e}', 'danger')

    cobradores = Usuario.query.filter(or_(Usuario.rol == 'admin', Usuario.rol == 'cobrador')).all()
    return render_template('crear_prestamo.html', cobradores=cobradores)


# verificacion del cliente si existe en la base de datos
@app.route('/prestamo/verificar-cliente', methods=['POST'])
@login_required
def buscar_o_crear_cliente():
    cedula = request.form.get('cedula')
    cliente = Cliente.query.filter_by(cedula=cedula).first()

    if cliente:
        # Si el cliente existe, vamos directo a crear el préstamo para él
        return redirect(url_for('prestamo_para_cliente', cliente_id=cliente.id))
    else:
        # SI NO EXISTE: Mostramos un error y lo mandamos a la lista de clientes.
        flash(f"El cliente con cédula {cedula} no existe. Por favor, créalo primero desde esta sección.", 'warning')
        return redirect(url_for('gestion_clientes'))



@app.route('/prestamo/<int:prestamo_id>')
@login_required
def detalle_prestamo(prestamo_id):
    prestamo = Prestamo.query.get_or_404(prestamo_id)
    today = date.today()
    return render_template('detalle_prestamo.html', prestamo=prestamo, today=today)


@app.route('/prestamo/<int:prestamo_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_prestamo(prestamo_id):
    # Solo el admin puede editar
    if current_user.rol != 'admin':
        flash('No tienes permiso para editar préstamos.', 'danger')
        return redirect(url_for('index'))

    prestamo = Prestamo.query.get_or_404(prestamo_id)
    
    if request.method == 'POST':
        # Si el formulario se envió, actualizamos el cobrador
        nuevo_cobrador_id = request.form.get('cobrador_id')
        if nuevo_cobrador_id:
            prestamo.usuario_id = int(nuevo_cobrador_id)
            try:
                db.session.commit()
                flash('El cobrador del préstamo ha sido actualizado.', 'success')
                return redirect(url_for('detalle_prestamo', prestamo_id=prestamo.id))
            except Exception as e:
                db.session.rollback()
                flash(f'Error al actualizar el préstamo: {e}', 'danger')
        
    # Si es GET (la primera vez que se carga la página), mostramos el formulario
    cobradores = Usuario.query.filter(or_(Usuario.rol == 'admin', Usuario.rol == 'cobrador')).all()
    return render_template('editar_prestamo.html', prestamo=prestamo, cobradores=cobradores)


@app.route('/prestamo/<int:prestamo_id>/eliminar', methods=['POST'])
@login_required
def eliminar_prestamo(prestamo_id):
    if current_user.rol != 'admin':
        flash('No tienes permiso para realizar esta acción.', 'danger')
        return redirect(url_for('index'))

    prestamo_a_eliminar = Prestamo.query.get_or_404(prestamo_id)
    
    try:
        # Gracias a la configuración 'cascade' en el modelo,
        # al borrar el préstamo, se borran automáticamente todas sus cuotas.
        db.session.delete(prestamo_a_eliminar)
        db.session.commit()
        flash(f'El préstamo #{prestamo_id} y todas sus cuotas han sido eliminados.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el préstamo: {e}', 'danger')
        app.logger.error(f"Error al eliminar préstamo {prestamo_id}: {e}")
        
    return redirect(url_for('admin_dashboard'))


@app.route('/cuota/<int:cuota_id>/pagar', methods=['POST'])
@login_required
def pagar_cuota(cuota_id):
    """ Procesa el pago de una cuota específica. """
    # --- LA CORRECCIÓN ESTÁ EN LA LÍNEA SIGUIENTE ---
    cuota = Cuota.query.get_or_404(cuota_id)
    
    if cuota.estado == 'pagada':
        flash('Esta cuota ya ha sido pagada.', 'warning')
        return redirect(url_for('detalle_prestamo', prestamo_id=cuota.prestamo_id))

    cuota.estado = 'pagada'
    cuota.fecha_de_pago = datetime.utcnow()
    
    try:
        db.session.commit()
        flash(f'Pago de la cuota #{cuota.id} registrado exitosamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al registrar el pago: {e}', 'danger')
        app.logger.error(f"Error al pagar cuota {cuota_id}: {e}")

    return redirect(url_for('detalle_prestamo', prestamo_id=cuota.prestamo_id))


@app.route('/cuota/<int:cuota_id>/revertir', methods=['POST'])
@login_required
def revertir_pago_cuota(cuota_id):
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    cuota = Cuota.query.get_or_404(cuota_id)
    cuota.estado = 'pendiente'
    cuota.fecha_de_pago = None
    db.session.commit()
    flash(f'Pago de la cuota #{cuota.id} revertido.', 'success')
    return redirect(url_for('detalle_prestamo', prestamo_id=cuota.prestamo_id))



@app.route('/admin/cliente/<int:cliente_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_cliente(cliente_id):
    if current_user.rol != 'admin':
        return redirect(url_for('index'))

    cliente = Cliente.query.get_or_404(cliente_id)

    if request.method == 'POST':
        # Actualizamos los datos del cliente con la información del formulario
        cliente.cedula = request.form['cedula']
        cliente.nombre_completo = request.form['nombre_completo']
        cliente.telefono = request.form['telefono']
        cliente.direccion = request.form['direccion']
        try:
            db.session.commit()
            flash('Cliente actualizado correctamente.', 'success')
            return redirect(url_for('gestion_clientes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el cliente: {e}', 'danger')

    return render_template('editar_cliente.html', cliente=cliente)


@app.route('/admin/clientes')
@login_required
def gestion_clientes():
    if current_user.rol != 'admin':
        return redirect(url_for('index'))

    # Consultamos todos los clientes ordenados por nombre
    todos_los_clientes = Cliente.query.order_by(Cliente.nombre_completo).all()

    return render_template('clientes.html', clientes=todos_los_clientes)


# En app.py
@app.route('/admin/cliente/crear', methods=['GET', 'POST'])
@login_required
def crear_cliente():
    if current_user.rol != 'admin':
        return redirect(url_for('index'))

    if request.method == 'POST':
        cedula = request.form['cedula']
        cliente_existente = Cliente.query.filter_by(cedula=cedula).first()
        if cliente_existente:
            flash('Ya existe un cliente con esa cédula.', 'danger')
        else:
            nuevo_cliente = Cliente(
                cedula=cedula,
                nombre_completo=request.form['nombre_completo'],
                telefono=request.form['telefono'],
                direccion=request.form['direccion']
            )
            db.session.add(nuevo_cliente)
            db.session.commit()
            flash('Cliente creado exitosamente.', 'success')
            # Siempre regresa a la lista de clientes
            return redirect(url_for('gestion_clientes'))

    # Ya no necesita la variable 'cedula_previa'
    return render_template('crear_cliente.html')


# En app.py

@app.route('/prestamo/cliente/<int:cliente_id>', methods=['GET', 'POST'])
@login_required
def prestamo_para_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    cobradores = []
    if current_user.rol == 'admin':
        cobradores = Usuario.query.filter(or_(Usuario.rol == 'admin', Usuario.rol == 'cobrador')).all()

    if request.method == 'POST':
        # --- Recopilación de datos del formulario ---
        monto = float(request.form.get('monto'))
        plazo = int(request.form.get('plazo'))
        interes = float(request.form.get('interes'))
        frecuencia = request.form.get('frecuencia')
        cobrador_id = request.form.get('cobrador_id', current_user.id)
        cobrar_sabado = 'cobrarSabado' in request.form
        cobrar_domingo = 'cobrarDomingo' in request.form
        
        total_a_pagar = monto * (1 + (interes / 100) * plazo)

        # --- LÍNEA CORREGIDA ---
        # Ahora todos los argumentos están nombrados correctamente
        nuevo_prestamo = Prestamo(
            monto_prestado=monto,
            tasa_interes_mensual=interes,
            plazo_meses=plazo,
            monto_total_a_pagar=total_a_pagar,
            frecuencia=frecuencia,
            cobrar_sabado=cobrar_sabado,
            cobrar_domingo=cobrar_domingo,
            cliente=cliente,
            usuario_id=cobrador_id
        )
        
        # --- (Aquí va la lógica de generación de cuotas que ya funciona) ---
        # ...
        
        try:
            db.session.add(nuevo_prestamo)
            db.session.commit()
            flash('Préstamo creado exitosamente.', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el préstamo: {e}', 'danger')

    # Para el método GET
    return render_template('prestamo_final.html', cliente=cliente, cobradores=cobradores)


@app.route('/admin/cliente/<int:cliente_id>/eliminar', methods=['POST'])
@login_required
def eliminar_cliente(cliente_id):
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    cliente_a_eliminar = Cliente.query.get_or_404(cliente_id)
    
    # Lógica de seguridad: no permitir borrar si tiene préstamos
    if cliente_a_eliminar.prestamos:
        flash('No se puede eliminar un cliente que tiene préstamos asociados.', 'danger')
        return redirect(url_for('gestion_clientes'))
    
    try:
        db.session.delete(cliente_a_eliminar)
        db.session.commit()
        flash('Cliente eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el cliente: {e}', 'danger')
        
    return redirect(url_for('gestion_clientes'))


@app.route('/admin/usuarios')
@login_required
def gestion_usuarios():
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    # Consultamos todos los usuarios para listarlos
    usuarios = Usuario.query.all()
    
    return render_template('usuarios.html', usuarios=usuarios)


@app.route('/admin/usuario/crear', methods=['GET', 'POST'])
@login_required
def crear_usuario():
    if current_user.rol != 'admin':
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        rol = request.form['rol']

        usuario_existente = Usuario.query.filter_by(username=username).first()
        if usuario_existente:
            flash('El nombre de usuario ya existe.', 'danger')
        else:
            password_hasheado = bcrypt.generate_password_hash(password).decode('utf-8')
            nuevo_usuario = Usuario(username=username, password_hash=password_hasheado, rol=rol)
            db.session.add(nuevo_usuario)
            db.session.commit()
            flash('Usuario creado exitosamente.', 'success')
            return redirect(url_for('gestion_usuarios'))

    return render_template('crear_usuario.html')


@app.route('/admin/usuario/<int:usuario_id>/editar', methods=['GET', 'POST'])
@login_required
def editar_usuario(usuario_id):
    if current_user.rol != 'admin':
        return redirect(url_for('index'))
    
    usuario_a_editar = Usuario.query.get_or_404(usuario_id)

    if request.method == 'POST':
        # Actualizar datos
        usuario_a_editar.username = request.form['username']
        usuario_a_editar.rol = request.form['rol']
        
        # Opcional: Cambiar contraseña si se proporciona una nueva
        nueva_password = request.form.get('password')
        if nueva_password:
            usuario_a_editar.password_hash = bcrypt.generate_password_hash(nueva_password).decode('utf-8')
        
        db.session.commit()
        flash('Usuario actualizado correctamente.', 'success')
        return redirect(url_for('gestion_usuarios'))

    return render_template('editar_usuario.html', usuario=usuario_a_editar)


@app.route('/admin/usuario/<int:usuario_id>/eliminar', methods=['POST'])
@login_required
def eliminar_usuario(usuario_id):
    if current_user.rol != 'admin':
        return redirect(url_for('index'))

    # --- REGLA DE SEGURIDAD 1: NO TE PUEDES ELIMINAR A TI MISMO ---
    if usuario_id == current_user.id:
        flash('No puedes eliminar tu propio usuario administrador.', 'danger')
        return redirect(url_for('gestion_usuarios'))

    usuario_a_eliminar = Usuario.query.get_or_404(usuario_id)

    # --- REGLA DE SEGURIDAD 2: NO ELIMINAR SI TIENE PRÉSTAMOS ASIGNADOS ---
    if usuario_a_eliminar.prestamos_asignados:
        flash('No se puede eliminar este usuario porque tiene préstamos asignados. Reasígnalos a otro cobrador primero.', 'danger')
        return redirect(url_for('gestion_usuarios'))
    
    db.session.delete(usuario_a_eliminar)
    db.session.commit()
    flash('Usuario eliminado correctamente.', 'success')
    return redirect(url_for('gestion_usuarios'))


@app.route('/configuracion', methods=['GET', 'POST'])
@login_required
def configuracion():
    if current_user.rol != 'admin':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('index'))
    
    # Buscamos la plantilla en la base de datos
    template_obj = Configuracion.query.filter_by(clave='whatsapp_template').first()

    if request.method == 'POST':
        # Si el admin guarda el formulario
        nuevo_template = request.form.get('whatsapp_template')
        if template_obj:
            # Si ya existía, la actualizamos
            template_obj.valor = nuevo_template
        else:
            # Si no existía, la creamos
            template_obj = Configuracion(clave='whatsapp_template', valor=nuevo_template)
            db.session.add(template_obj)
        db.session.commit()
        flash('Plantilla de WhatsApp guardada correctamente.', 'success')
        return redirect(url_for('configuracion'))

    # Si se carga la página, mostramos la plantilla actual o una por defecto
    template_actual = template_obj.valor if template_obj else "Hola [cliente], te recordamos que tu cuota de $[monto_cuota] que vencía el [fecha_vencimiento] se encuentra pendiente. ¡Gracias!"
    return render_template('configuracion.html', template_actual=template_actual)

    

@app.route('/consulta')
def consulta_cliente():
    """ Muestra el formulario para que el cliente ingrese su cédula. """
    return render_template('consulta_cliente.html')

@app.route('/estado', methods=['POST'])
def ver_estado_prestamo():
    """ Busca el préstamo del cliente y muestra su estado. """
    cedula = request.form.get('cedula')
    if not cedula:
        flash('Debes ingresar un número de cédula.', 'warning')
        return redirect(url_for('consulta_cliente'))

    cliente = Cliente.query.filter_by(cedula=cedula).first()
    
    # Buscamos un préstamo activo para este cliente
    prestamo_activo = None
    if cliente:
        prestamo_activo = Prestamo.query.filter_by(cliente_id=cliente.id, estado='activo').first()

    if not prestamo_activo:
        flash('No se encontró un crédito activo para la cédula ingresada.', 'danger')
        return redirect(url_for('consulta_cliente'))

    today = date.today()
    return render_template('estado_prestamo.html', prestamo=prestamo_activo, today=today)


# --- EJECUCIÓN DE LA APLICACIÓN ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5500, debug=True)