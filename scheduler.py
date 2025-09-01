import pywhatkit
from datetime import datetime, date, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from app import app, db, Cuota, Cliente, Configuracion # Importamos desde nuestra app

def enviar_recordatorios():
    print(f"[{datetime.now()}] --- Ejecutando tarea de recordatorios ---")
    with app.app_context():
        # Buscamos cuotas que vencieron AYER y siguen pendientes
        fecha_ayer = date.today() - timedelta(days=1)
        cuotas_atrasadas = Cuota.query.filter_by(estado='pendiente', fecha_vencimiento=fecha_ayer).all()

        if not cuotas_atrasadas:
            print("No se encontraron cuotas atrasadas para notificar.")
            return

        template_obj = Configuracion.query.filter_by(clave='whatsapp_template').first()
        if not template_obj or not template_obj.valor:
            print("No hay plantilla de WhatsApp configurada. Abortando.")
            return

        plantilla = template_obj.valor
        print(f"Se encontraron {len(cuotas_atrasadas)} cuotas para notificar.")

        for cuota in cuotas_atrasadas:
            cliente = cuota.prestamo.cliente
            if cliente.telefono:
                try:
                    # Rellenamos la plantilla con los datos
                    mensaje = plantilla.replace('[cliente]', cliente.nombre_completo)
                    mensaje = mensaje.replace('[monto_cuota]', str(int(cuota.monto_cuota)))
                    mensaje = mensaje.replace('[fecha_vencimiento]', cuota.fecha_vencimiento.strftime('%d/%m/%Y'))

                    # ¡Enviamos el mensaje!
                    # Nota: El teléfono debe tener el código del país, ej: +573001234567
                    pywhatkit.sendwhatmsg_instantly(f"+{cliente.telefono}", mensaje, wait_time=15)

                    print(f"Mensaje enviado a {cliente.nombre_completo} ({cliente.telefono})")

                    # Opcional: Marcar la cuota como 'atrasada' para no notificar de nuevo
                    cuota.estado = 'atrasada'
                    db.session.commit()
                except Exception as e:
                    print(f"Error enviando mensaje a {cliente.nombre_completo}: {e}")
            else:
                print(f"Cliente {cliente.nombre_completo} no tiene teléfono registrado.")

# Programamos la tarea para que se ejecute todos los días a las 9:00 AM
scheduler = BlockingScheduler(timezone="America/Bogota")
scheduler.add_job(enviar_recordatorios, 'cron', hour=9, minute=0)

print("Scheduler iniciado. Presiona Ctrl+C para detener.")
try:
    scheduler.start()
except (KeyboardInterrupt, SystemExit):
    pass