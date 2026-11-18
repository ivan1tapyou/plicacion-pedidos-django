from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q  # <-- Importante para consultas complejas con OR
from .models import Categoria, Producto, UsuarioRestaurante, Restaurante, Pedido
from .services import confirmar_pedido_service, incrementar_cantidad_carrito, decrementar_cantidad_carrito
import csv
from django.http import HttpResponse
# --- 1. DECORADORES DE SEGURIDAD Y CONTROL DE ROLES ---
def verificar_sesion(view_func):
    """Protege las pantallas para que solo accedan usuarios con sesión activa."""
    def wrapper(request, *args, **kwargs):
        if 'usuario_id' not in request.session:
            return redirect('login_restaurante')
        return view_func(request, *args, **kwargs)
    return wrapper

def solo_admin(view_func):
    """Permite el acceso exclusivamente a usuarios con rol 'admin'."""
    def wrapper(request, *args, **kwargs):
        if request.session.get('usuario_rol') != 'admin':
            return redirect('listar_categorias')
        return view_func(request, *args, **kwargs)
    return wrapper

def solo_stock(view_func):
    """Permite el acceso exclusivamente a usuarios con rol 'stock'."""
    def wrapper(request, *args, **kwargs):
        if request.session.get('usuario_rol') != 'stock':
            return redirect('listar_categorias')
        return view_func(request, *args, **kwargs)
    return wrapper

def bloquear_admin_hacer_pedidos(view_func):
    """Impide que un usuario con rol 'admin' pueda confirmar o realizar pedidos."""
    def wrapper(request, *args, **kwargs):
        if request.session.get('usuario_rol') == 'admin':
            return redirect('listar_categorias')
        return view_func(request, *args, **kwargs)
    return wrapper


# --- 2. AUTENTICACIÓN CON GESTIÓN DE ROLES ---
def login_restaurante(request):
    error = None
    if request.method == 'POST':
        correo = request.POST.get('correo')
        password = request.POST.get('password')
        
        try:
            # Buscamos el usuario en la tabla UsuarioRestaurante de SQLite
            usuario = UsuarioRestaurante.objects.get(correo=correo, password=password)
            
            # Limpiamos y renovamos la clave de sesión para evitar conflictos
            request.session.flush()
            request.session.create()
            
            # Guardamos los datos esenciales y el rol en la sesión
            request.session['usuario_id'] = usuario.id
            request.session['usuario_correo'] = usuario.correo
            request.session['usuario_rol'] = usuario.rol  # <--- Almacenamos el rol del usuario
            
            # Comprobamos si el modelo tiene relación con restaurante o asignamos por defecto
            if hasattr(usuario, 'restaurante') and usuario.restaurante:
                request.session['restaurante_id'] = usuario.restaurante.id
                request.session['restaurante_nombre'] = usuario.restaurante.nombre
            else:
                request.session['restaurante_id'] = 1
                request.session['restaurante_nombre'] = "Panel de Administración"
                
            # Redirección inteligente basada en el rol del usuario
            if usuario.rol == 'stock':
                return redirect('vista_almacen')
            elif usuario.rol == 'admin':
                return redirect('panel_administracion')
            else:
                return redirect('listar_categorias')
            
        except UsuarioRestaurante.DoesNotExist:
            error = 'Credenciales incorrectas o usuario no autorizado.'
            
    return render(request, 'mi_app12/login.html', {'error': error})

def logout_restaurante(request):
    """Cierra la sesión destruyendo los datos guardados."""
    request.session.flush()
    return redirect('login_restaurante')

# --- 3. VISTA DE CATEGORÍAS (Protegida) ---
@verificar_sesion
def listar_categorias(request):
    categorias = Categoria.objects.all()
    ultima_categoria = request.COOKIES.get('ultima_categoria')
    
    return render(request, 'mi_app12/categorias.html', {
        'categorias': categorias,
        'ultima_categoria': ultima_categoria,
        'restaurante_nombre': request.session.get('restaurante_nombre'),
        'usuario_rol': request.session.get('usuario_rol')
    })

# --- 4. VISTA DE PRODUCTOS, PROCESAMIENTO DE CANTIDADES Y FILTRADO ---
@verificar_sesion
def productos_categoria(request, categoria_id):
    categoria = get_object_or_404(Categoria, id=categoria_id)
    
    # Obtenemos los productos iniciales filtrados por categoría
    productos = Producto.objects.filter(categoria=categoria)
    mensaje_alerta = None

    # --- MEJORA OPERATIVA: Búsqueda dinámica por nombre o peso ---
    query = request.GET.get('q', '').strip()
    if query:
        productos = productos.filter(
            Q(nombre__icontains=query) | Q(peso__icontains=query)
        )
    # -------------------------------------------------------------

    if request.method == 'POST':
        if 'carrito' not in request.session:
            request.session['carrito'] = {}
        
        carrito = request.session['carrito']
        hay_cantidades_validas = False

        for key, value in request.POST.items():
            if key.startswith('cantidad_'):
                try:
                    producto_id_str = key.split('_')[1]
                    cantidad = int(value)
                    
                    if cantidad > 0:
                        hay_cantidades_validas = True
                        if producto_id_str in carrito:
                            carrito[producto_id_str]['cantidad'] += cantidad
                        else:
                            carrito[producto_id_str] = {
                                'producto_id': int(producto_id_str),
                                'cantidad': cantidad
                            }
                except (ValueError, TypeError):
                    continue

        if hay_cantidades_validas:
            request.session['carrito'] = carrito
            request.session.modified = True
            return redirect('ver_carrito')
        else:
            mensaje_alerta = "Por favor, introduce al menos una cantidad válida mayor que cero."

    response = render(request, 'mi_app12/productos_categoria.html', {
        'categoria': categoria,
        'productos': productos,
        'mensaje_alerta': mensaje_alerta,
        'query': query,  # Enviamos la query para mantenerla en el input de la plantilla
        'restaurante_nombre': request.session.get('restaurante_nombre')
    })
    
    response.set_cookie('ultima_categoria', categoria.nombre, max_age=3600)
    return response

# --- 5. GESTIÓN DEL CARRITO (Protegida) ---
@verificar_sesion
def ver_carrito(request):
    carrito = request.session.get('carrito', {})
    items_carrito = []
    total_general = 0

    for producto_id, datos in carrito.items():
        try:
            unidades = datos.get('cantidad', 0)
            producto = Producto.objects.get(id=datos.get('producto_id'))
            precio = getattr(producto, 'precio', 0) or 0
            subtotal = precio * unidades
            total_general += subtotal
            
            items_carrito.append({
                'producto': producto,
                'unidades': unidades,
                'subtotal': subtotal
            })
        except (Producto.DoesNotExist, AttributeError, KeyError):
            continue

    return render(request, 'mi_app12/carrito.html', {
        'items': items_carrito,
        'total_general': total_general,
        'restaurante_nombre': request.session.get('restaurante_nombre')
    })

@verificar_sesion
def incrementar_producto(request, producto_id):
    """Incrementa en 1 unidad un producto del carrito."""
    incrementar_cantidad_carrito(request.session, producto_id)
    return redirect('ver_carrito')

@verificar_sesion
def decrementar_producto(request, producto_id):
    """Decrementa en 1 unidad un producto del carrito (o lo borra si llega a 0)."""
    decrementar_cantidad_carrito(request.session, producto_id)
    return redirect('ver_carrito')

@verificar_sesion
def eliminar_del_carrito(request, producto_id):
    carrito = request.session.get('carrito', {})
    str_id = str(producto_id)
    if str_id in carrito:
        del carrito[str_id]
        request.session['carrito'] = carrito
        request.session.modified = True
    return redirect('ver_carrito')

@verificar_sesion
def vaciar_carrito(request):
    if 'carrito' in request.session:
        del request.session['carrito']
    return redirect('ver_carrito')

# --- 6. VISTA DE CONFIRMACIÓN DE PEDIDO (Bloqueada para administradores) ---
@verificar_sesion
@bloquear_admin_hacer_pedidos
def confirmar_pedido(request):
    if request.method == 'POST':
        restaurante_id = request.session.get('restaurante_id')
        
        try:
            restaurante = Restaurante.objects.get(pk=restaurante_id)
        except Restaurante.DoesNotExist:
            return redirect('listar_categorias')

        exito, mensaje = confirmar_pedido_service(request.session, restaurante)

        if exito:
            ultimo_pedido = Pedido.objects.filter(restaurante=restaurante).order_by('-id').first()
            if ultimo_pedido:
                return redirect('correo_emitido', pedido_id=ultimo_pedido.id)
            else:
                return redirect('listar_mis_pedidos')
        else:
            return redirect('ver_carrito')

    return redirect('ver_carrito')

@verificar_sesion
def correo_emitido_view(request, pedido_id):
    """
    Simulador de envío de correo: Muestra los datos del emisor, 
    destinatario, el pedido y las líneas de productos solicitados.
    """
    restaurante_id = request.session.get('restaurante_id')
    pedido = get_object_or_404(Pedido, pk=pedido_id, restaurante_id=restaurante_id)
    
    lineas_pedido = pedido.lineas.all() if hasattr(pedido, 'lineas') else pedido.lineapedido_set.all()
    
    contexto = {
        'pedido': pedido,
        'lineas': lineas_pedido,
        'remitente': 'no-reply@miempresa.com',
        'destinatario': request.session.get('restaurante_nombre'),
        'restaurante_nombre': request.session.get('restaurante_nombre')
    }
    return render(request, 'mi_app12/correo_emitido.html', contexto)

# --- 7. VISTAS: MIS PEDIDOS Y DETALLE (RA6) ---
@verificar_sesion
def listar_mis_pedidos(request):
    """Lista exclusivamente los pedidos del restaurante autenticado con filtros opcionales."""
    restaurante_id = request.session.get('restaurante_id')
    restaurante = get_object_or_404(Restaurante, pk=restaurante_id)
    
    pedidos = Pedido.objects.filter(restaurante=restaurante).order_by('-fecha')

    estado_filtro = request.GET.get('enviado')
    if estado_filtro is not None:
        if estado_filtro.lower() == 'true':
            pedidos = pedidos.filter(enviado=True)
        elif estado_filtro.lower() == 'false':
            pedidos = pedidos.filter(enviado=False)

    return render(request, 'mi_app12/mis_pedidos.html', {
        'pedidos': pedidos,
        'restaurante_nombre': restaurante.nombre,
        'estado_filtro': estado_filtro
    })

@verificar_sesion
def detalle_pedido(request, pedido_id):
    """
    Muestra el detalle y las líneas de un pedido propio.
    Garantiza aislamiento de datos: si el pedido no pertenece al restaurante activo, da error 404.
    """
    restaurante_id = request.session.get('restaurante_id')
    
    pedido = get_object_or_404(Pedido, pk=pedido_id, restaurante_id=restaurante_id)
    lineas = pedido.lineas.all()

    return render(request, 'mi_app12/detalle_pedido.html', {
        'pedido': pedido,
        'lineas': lineas,
        'restaurante_nombre': request.session.get('restaurante_nombre')
    })

# --- 8. VISTA DE ADMINISTRACIÓN PARA DAR DE ALTA USUARIOS ---
@verificar_sesion
@solo_admin
def panel_administracion(request):
    """Vista exclusiva de administración para registrar nuevos usuarios con roles."""
    mensaje = None
    error = None
    
    if request.method == 'POST':
        correo = request.POST.get('correo')
        password = request.POST.get('password')
        rol = request.POST.get('rol')
        restaurante_id = request.POST.get('restaurante_id')
        
        try:
            restaurante_obj = Restaurante.objects.get(pk=restaurante_id) if restaurante_id else None
            
            UsuarioRestaurante.objects.create(
                correo=correo,
                password=password,
                rol=rol,
                restaurante=restaurante_obj
            )
            mensaje = f"Usuario '{correo}' creado con éxito con rol [{rol}]."
        except Exception as e:
            error = f"Error al crear el usuario: {str(e)}"
            
    restaurantes = Restaurante.objects.all()
    usuarios = UsuarioRestaurante.objects.all()
    
    return render(request, 'mi_app12/admin_panel.html', {
        'mensaje': mensaje,
        'error': error,
        'restaurantes': restaurantes,
        'usuarios': usuarios,
        'restaurante_nombre': request.session.get('restaurante_nombre')
    })

# --- 9. VISTA EXCLUSIVA DE ALMACÉN (Personal de Stock) ---
@verificar_sesion
@solo_stock
@verificar_sesion
@solo_stock
def exportar_pedidos_csv(request):
    """Genera y descarga un informe en formato CSV con todos los pedidos del sistema."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="informe_pedidos_almacen.csv"'

    writer = csv.writer(response)
    # Cabeceras del informe CSV
    writer.writerow(['ID Pedido', 'Restaurante', 'Fecha', 'Estado', 'Total (€)'])

    # Filas de datos extraídas de la base de datos
    for pedido in Pedido.objects.all().order_by('-fecha'):
        writer.writerow([
            pedido.id,
            pedido.restaurante.nombre,
            pedido.fecha.strftime('%d/%m/%Y %H:%M'),
            pedido.get_estado_display(),
            pedido.total_pedido
        ])

    return response


def vista_almacen(request):
    """Vista exclusiva para el personal de almacén/stock con control de stock crítico."""
    mensaje = None
    error = None

    # 1. Definimos la consulta arriba del todo para evitar errores de ámbito
    productos_criticos = list(Producto.objects.filter(stock__lte=5))

    if request.method == 'POST':
        pedido_id = request.POST.get('pedido_id')
        nuevo_estado = request.POST.get('nuevo_estado')
        
        try:
            pedido = Pedido.objects.get(pk=pedido_id)
            pedido.estado = nuevo_estado
            if nuevo_estado == 'enviado':
                pedido.enviado = True
            else:
                pedido.enviado = False
            pedido.save()
            mensaje = f"El pedido #{pedido.id} se ha actualizado correctamente."
        except Pedido.DoesNotExist:
            error = "El pedido seleccionado no existe."

    pedidos = Pedido.objects.all().order_by('-fecha')

    return render(request, 'mi_app12/almacen.html', {
        'pedidos': pedidos,
        'productos_criticos': productos_criticos,
        'mensaje': mensaje,
        'error': error,
        'usuario_correo': request.session.get('usuario_correo'),
        'restaurante_nombre': request.session.get('restaurante_nombre')

    })
def historico_pedidos(request):
    usuario_rol = request.session.get('usuario_rol')
    usuario_id = request.session.get('usuario_id') # o el campo con el que identifiques al usuario logueado
    
    if usuario_rol == 'admin':
      
        pedidos = Pedido.objects.all().order_by('-fecha')
    else:
      
        pedidos = Pedido.objects.filter(restaurante_id=usuario_id).order_by('-fecha')
        
    return render(request, 'mi_app12/historico_pedidos.html', {
        'pedidos': pedidos,
        'usuario_rol': usuario_rol,
        'restaurante_nombre': request.session.get('restaurante_nombre')
    })
    