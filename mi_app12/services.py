from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from .models import Pedido, LineaPedido, Producto

# ==========================================
# RA3: Validación de cantidades y unidades
# ==========================================
def validar_cantidad_unitaria(valor_str):
    """
    Valida que el valor introducido sea un entero positivo o cero.
    Retorna una tupla: (es_valido: bool, valor_entero: int)
    """
    try:
        cantidad = int(valor_str)
        if cantidad < 0:
            return False, 0
        return True, cantidad
    except (ValueError, TypeError):
        return False, 0


# ==========================================
# RA4: Gestión del Estado / Carrito en Sesión
# ==========================================
def obtener_carrito(session):
    """Recupera el carrito de la sesión actual o lo inicializa si no existe."""
    if 'carrito' not in session:
        session['carrito'] = {}
    return session['carrito']

def agregar_al_carrito(session, producto_id, cantidad):
    """Añade o acumula productos en el carrito almacenado en sesión."""
    if cantidad <= 0:
        return False, "La cantidad debe ser mayor que cero."

    carrito = obtener_carrito(session)
    str_id = str(producto_id)

    if str_id in carrito:
        carrito[str_id]['cantidad'] += cantidad
    else:
        carrito[str_id] = {
            'producto_id': int(producto_id),
            'cantidad': cantidad
        }
    
    session.modified = True
    return True, "Producto añadido correctamente."

def actualizar_cantidad_carrito(session, producto_id, nueva_cantidad):
    """Actualiza la cantidad de un ítem en el carrito o lo elimina si es 0."""
    try:
        cant_int = int(nueva_cantidad)
    except (ValueError, TypeError):
        return False, "Cantidad no válida."

    carrito = obtener_carrito(session)
    str_id = str(producto_id)

    if str_id in carrito:
        if cant_int <= 0:
            del carrito[str_id]
        else:
            carrito[str_id]['cantidad'] = cant_int
        session.modified = True
        return True, "Carrito actualizado."
    return False, "El producto no está en el carrito."

def incrementar_cantidad_carrito(session, producto_id):
    """Incrementa en 1 la cantidad de un producto en el carrito."""
    carrito = obtener_carrito(session)
    str_id = str(producto_id)
    if str_id in carrito:
        carrito[str_id]['cantidad'] += 1
        session.modified = True
        return True, "Cantidad incrementada."
    return False, "El producto no está en el carrito."

def decrementar_cantidad_carrito(session, producto_id):
    """Decrementa en 1 la cantidad de un producto o lo elimina si llega a 0."""
    carrito = obtener_carrito(session)
    str_id = str(producto_id)
    if str_id in carrito:
        carrito[str_id]['cantidad'] -= 1
        if carrito[str_id]['cantidad'] <= 0:
            del carrito[str_id]
        session.modified = True
        return True, "Cantidad actualizada."
    return False, "El producto no está en el carrito."

def eliminar_del_carrito(session, producto_id):
    """Elimina un producto del carrito de la sesión."""
    carrito = obtener_carrito(session)
    str_id = str(producto_id)
    if str_id in carrito:
        del carrito[str_id]
        session.modified = True
        return True, "Producto eliminado."
    return False, "El producto no existía."

def calcular_resumen_carrito(session):
    """Calcula los subtotales y carga los objetos Producto reales desde la BD."""
    carrito = obtener_carrito(session)
    items_detalle = []
    total_unidades = 0
    
    for str_id, datos in carrito.items():
        try:
            producto = Producto.objects.get(pk=datos['producto_id'])
            cantidad = datos['cantidad']
            items_detalle.append({
                'producto': producto,
                'cantidad': cantidad,
            })
            total_unidades += cantidad
        except Producto.DoesNotExist:
            continue

    return {
        'items': items_detalle,
        'total_unidades': total_unidades
    }


# ==========================================
# RA5: Persistencia en BBDD y Envío de Correo
# ==========================================
def confirmar_pedido_service(session, restaurante):
    """
    Pasa el carrito de la sesión a la base de datos creando un Pedido y sus líneas,
    valida y descuenta el stock disponible, vacía la sesión y dispara las notificaciones.
    """
    carrito = session.get('carrito', {})
    if not carrito:
        return False, "El carrito está vacío."

    try:
        with transaction.atomic():
            # 1. Crear cabecera del pedido
            nuevo_pedido = Pedido.objects.create(
                restaurante=restaurante,
                enviado=False
            )

            # 2. Iterar, validar stock, descontarlo y crear las líneas de pedido
            for str_id, datos in carrito.items():
                producto = Producto.objects.get(pk=datos['producto_id'])
                cantidad_pedida = datos['cantidad']

                # --- MEJORA OPERATIVA: Control estricto de Stock ---
                if producto.stock < cantidad_pedida:
                    raise ValueError(f"Stock insuficiente para '{producto.nombre}'. Disponible: {producto.stock}, Solicitado: {cantidad_pedida}")
                
                # Restar unidades y persistir cambios en el producto
                producto.stock -= cantidad_pedida
                producto.save()
                # ---------------------------------------------------

                LineaPedido.objects.create(
                    pedido=nuevo_pedido,
                    producto=producto,
                    unidades=cantidad_pedida
                )

            # 3. Vaciar carrito de la sesión
            session['carrito'] = {}
            session.modified = True

            # 4. Enviar correos de notificación
            enviar_correos_confirmacion(nuevo_pedido, restaurante)

        return True, f"Pedido #{nuevo_pedido.id} confirmado con éxito y stock actualizado."

    except Exception as e:
        return False, f"Error al procesar el pedido: {str(e)}"

def enviar_correos_confirmacion(pedido, restaurante):
    """Envía los correos de confirmación requeridos al restaurante y a pedidos."""
    asunto = f"Confirmación de Pedido #{pedido.id}"
    
    mensaje_restaurante = (
        f"Estimado/a {restaurante.nombre},\n\n"
        f"Su pedido con ID #{pedido.id} ha sido registrado correctamente."
    )
    
    mensaje_departamento = (
        f"Nuevo pedido recibido del restaurante: {restaurante.nombre} ({restaurante.email}).\n"
        f"ID de Pedido: {pedido.id}"
    )

    # Correo al restaurante
    send_mail(
        subject=asunto,
        message=mensaje_restaurante,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[restaurante.email],
        fail_silently=True,
    )

    # Correo al Departamento de Pedidos
    send_mail(
        subject=f"[DEP. PEDIDOS] Pedido #{pedido.id}",
        message=mensaje_departamento,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=['pedidos@restaurantes.com'],
        fail_silently=True,
    )