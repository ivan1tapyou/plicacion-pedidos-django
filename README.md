# 🛒 Aplicación Web de Gestión de Pedidos (Django & SQLite)

Sistema web desarrollado con **Django** para la gestión integral de pedidos de restaurantes, abarcando desde la autenticación y selección de productos mediante carrito en sesión, hasta la persistencia transaccional en bases de datos SQLite y la automatización de notificaciones.

---

## 📋 Índice de Contenidos
1. [Parte 1: Configuración Inicial, Proyecto y Modelos de Base de Datos](#parte-1-configuración-inicial-proyecto-y-modelos-de-base-datos)
   - Configuración del Entorno Virtual e Instalación
   - Creación del Proyecto y la Aplicación
   - Configuración General (`settings.py`)
   - Definición del Modelo de Datos (`models.py`)
   - Migraciones y Base de Datos SQLite

---

1. Arquitectura General e InstalaciónConfiguración del Entorno y Proyecto# 1. Crear y activar el entorno virtual
python -m venv venv
# Windows: venv\Scripts\activate | Linux/macOS: source venv/bin/activate

# 2. Instalar Django
pip install django

# 3. Crear proyecto y aplicación
django-admin startproject mi_proyecto12 .
python manage.py startapp mi_app12


#  Registro en settings.py
INSTALLED_APPS = [
    # Aplicaciones estándar de Django...
    'mi_app12',
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }


   

## 📑 Índice de Contenidos
1. [Parte 1: Autenticación, Gestión de Sesiones y Seguridad](#parte-1-autenticación-gestión-de-sesiones-y-seguridad)
2. [Parte 2: Catálogo de Productos, Cookies y Gestión de Categorías](#parte-2-catálogo-de-productos-cookies-y-gestión-de-categorías)
3. [Parte 3: Carrito de Compras y Modificación de Cantidades](#parte-3-carrito-de-compras-y-modificación-de-cantidades)
4. [Parte 4: Confirmación Atómica, Historial y Simulador de Correo](#parte-4-confirmación-atómica-historial-y-simulador-de-correo)

---

## Parte 1: Autenticación, Gestión de Sesiones y Seguridad

En esta primera fase se construyó la barrera de seguridad perimetral y el acceso de usuarios vinculados a cada restaurante.

### 1.1 Decorador de Protección (`verificar_sesion`)
```python
def verificar_sesion(view_func):
    """Protege las pantallas para que solo accedan usuarios con sesión activa."""
    def wrapper(request, *args, **kwargs):
        if 'usuario_id' not in request.session:
            return redirect('login_restaurante')
        return view_func(request, *args, **kwargs)
    return wrapper

Explicación paso a paso:

Intercepta cualquier petición dirigida a las vistas decoradas con @verificar_sesion.

Comprueba si la clave 'usuario_id' existe dentro del diccionario request.session.

Si el usuario no está autenticado, corta la ejecución y redirige inmediatamente a login_restaurante.

Si la sesión es válida, permite ejecutar la vista original con normalidad.

# 1.2 Inicio y Cierre de Sesión (login_restaurante y logout_restaurante)

Python
def login_restaurante(request):
    error = None
    if request.method == 'POST':
        correo = request.POST.get('correo')
        password = request.POST.get('password')
        
        try:
            usuario = UsuarioRestaurante.objects.get(correo=correo, password=password)
            request.session.flush()
            request.session.create()
            
            request.session['usuario_id'] = usuario.id
            request.session['usuario_correo'] = usuario.correo
            
            if hasattr(usuario, 'restaurante') and usuario.restaurante:
                request.session['restaurante_id'] = usuario.restaurante.id
                request.session['restaurante_nombre'] = usuario.restaurante.nombre
            else:
                request.session['restaurante_id'] = 1
                request.session['restaurante_nombre'] = "Restaurante Principal"
                
            return redirect('listar_categorias')
        except UsuarioRestaurante.DoesNotExist:
            error = 'Credenciales incorrectas o usuario no autorizado.'
            
    return render(request, 'mi_app12/login.html', {'error': error})

def logout_restaurante(request):
    """Cierra la sesión destruyendo los datos guardados."""
    request.session.flush()
    return redirect('login_restaurante')

Explicación paso a paso:

Cuando recibe una petición POST, extrae correo y password del formulario.

Busca la coincidencia exacta en el modelo UsuarioRestaurante.

Si existe, limpia cualquier rastro anterior mediante request.session.flush() y genera una nueva clave de sesión limpia (create()).

Almacena en sesión el ID del usuario y el restaurante_id asociado, clave fundamental para aislar los datos de cada cliente.

logout_restaurante destruye por completo la sesión activa y devuelve al usuario al formulario de acceso.

Parte 2: Catálogo de Productos, Cookies y Gestión de Categorías
En esta segunda etapa se desarrolló la navegación por el catálogo y el almacenamiento ligero en el cliente mediante cookies.

2.1 Listado de Categorías (listar_categorias)
Python
@verificar_sesion
def listar_categorias(request):
    categorias = Categoria.objects.all()
    ultima_categoria = request.COOKIES.get('ultima_categoria')
    
    return render(request, 'mi_app12/categorias.html', {
        'categorias': categorias,
        'ultima_categoria': ultima_categoria,
        'restaurante_nombre': request.session.get('restaurante_nombre')
    })
Explicación paso a paso:

Recupera todas las categorías registradas en la base de datos (Categoria.objects.all()).

Lee la cookie 'ultima_categoria' enviada por el navegador del cliente para mostrar un acceso directo o recordatorio de su última visita.

Renderiza categorias.html pasando el listado, la cookie y el nombre del restaurante activo.

2.2 Productos por Categoría y Alta en el Carrito (productos_categoria)
Python
@verificar_sesion
def productos_categoria(request, categoria_id):
    categoria = get_object_or_404(Categoria, id=categoria_id)
    productos = Producto.objects.filter(categoria=categoria)
    mensaje_alerta = None

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
        'restaurante_nombre': request.session.get('restaurante_nombre')
    })
    
    response.set_cookie('ultima_categoria', categoria.nombre, max_age=3600)
    return response
Explicación paso a paso:

Obtiene la categoría por su id (o devuelve error 404 si no existe) y filtra sus productos.

Si el usuario envía el formulario (POST), recorre dinámicamente todos los campos que empiezan por cantidad_.

Valida que sean enteros mayores a 0 y los suma o crea dentro del diccionario request.session['carrito'], marcando request.session.modified = True para forzar el guardado en Django.

Antes de devolver la respuesta HTML, guarda en el navegador la cookie ultima_categoria con una validez de 1 hora (max_age=3600).

Parte 3: Carrito de Compras y Modificación de Cantidades
La tercera parte implementa la gestión completa del carrito temporal alojado en la sesión antes de confirmar el pedido.

3.1 Visualización y Cálculo de Totales (ver_carrito)
Python
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
Explicación paso a paso:

Extrae el diccionario carrito de la sesión.

Por cada artículo guardado, consulta el objeto Producto real en la base de datos para asegurar que se utiliza el precio actualizado.

Calcula el subtotal por línea y va acumulando el total_general del pedido.

3.2 Control de Unidades y Limpieza (incrementar, decrementar, eliminar, vaciar)
Python
@verificar_sesion
def incrementar_producto(request, producto_id):
    incrementar_cantidad_carrito(request.session, producto_id)
    return redirect('ver_carrito')

@verificar_sesion
def decrementar_producto(request, producto_id):
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
Explicación paso a paso:

incrementar_producto / decrementar_producto: Delegan en la capa de servicios (services.py) la suma o resta de 1 unidad en la sesión (eliminando el ítem automáticamente si llega a 0) y recargan el carrito.

eliminar_del_carrito: Borra una clave concreta del diccionario del carrito y actualiza la sesión.

vaciar_carrito: Elimina la clave 'carrito' completa de la sesión dejando la cesta limpia.

Parte 4: Confirmación Atómica, Historial y Simulador de Correo
En la cuarta parte se cerró el ciclo transaccional del pedido, el aislamiento de historiales y la simulación de envío de correo electrónico.

4.1 Confirmación del Pedido (confirmar_pedido)
Python
@verificar_sesion
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
Explicación paso a paso:

Verifica que la petición provenga de un envío de formulario POST y recupera el Restaurante activo desde la sesión.

Invoca confirmar_pedido_service, que valida que el carrito no esté vacío, crea el Pedido y sus LineaPedido de forma atómica (@transaction.atomic) y vacía el carrito.

Si la operación tiene éxito, localiza el ID del pedido recién creado y redirige automáticamente a la vista del simulador de correo (correo_emitido).

4.2 Simulador de Envío de Correo (correo_emitido_view)
Python
@verificar_sesion
def correo_emitido_view(request, pedido_id):
    restaurante_id = request.session.get('restaurante_id')
    pedido = get_object_or_404(Pedido, pk=pedido_id, restaurante_id=restaurante_id)
    
    contexto = {
        'pedido': pedido,
        'remitente': 'no-reply@miempresa.com',
        'destinatario': request.session.get('restaurante_nombre'),
        'restaurante_nombre': request.session.get('restaurante_nombre')
    }
    return render(request, 'mi_app12/correo_emitido.html', contexto)
Explicación paso a paso:

Recupera el pedido verificando que pertenezca al restaurante en sesión (restaurante_id=restaurante_id).

Prepara el contexto con los datos requeridos para la evidencia visual: remitente del sistema, restaurante destinatario y número de pedido asociado.

Renderiza la plantilla correo_emitido.html heredando el diseño base de la aplicación.

4.3 Historial y Detalle con Aislamiento Multi-Tenant (listar_mis_pedidos y detalle_pedido)
Python
@verificar_sesion
def listar_mis_pedidos(request):
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
    restaurante_id = request.session.get('restaurante_id')
    
    pedido = get_object_or_404(Pedido, pk=pedido_id, restaurante_id=restaurante_id)
    lineas = pedido.lineas.all()

    return render(request, 'mi_app12/detalle_pedido.html', {
        'pedido': pedido,
        'lineas': lineas,
        'restaurante_nombre': request.session.get('restaurante_nombre')
    })
Explicación paso a paso:

listar_mis_pedidos: Filtra exclusivamente los pedidos del restaurante autenticado ordenados del más reciente al más antiguo, permitiendo filtrar opcionalmente por el parámetro GET ?enviado=true o false.

detalle_pedido: Ejecuta get_object_or_404 combinando pk=pedido_id y restaurante_id=restaurante_id. De este modo, si un usuario intenta manipular la URL para ver el pedido de otro restaurante (ataque IDOR), Django bloquea el acceso devolviendo un