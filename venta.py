# app.py
import os
from flask import Flask, jsonify, request
from flask_cors import CORS # Para permitir peticiones desde el frontend si es necesario
import mysql.connector
from mysql.connector import Error
from datetime import datetime

app = Flask(__name__)
CORS(app) # Habilita CORS para todas las rutas

# --- Configuración de la Base de Datos ---
# Es recomendable usar variables de entorno para esta información sensible.
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_USER = os.environ.get('DB_USER', 'root') # Cambia por tu usuario de MySQL
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'tu_contraseña') # Cambia por tu contraseña de MySQL
DB_NAME = os.environ.get('DB_NAME', 'pandatat')

def create_db_connection():
    """Crea y retorna una conexión a la base de datos MySQL."""
    connection = None
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            passwd=DB_PASSWORD,
            database=DB_NAME
        )
        print(f"Conexión a la base de datos MySQL '{DB_NAME}' exitosa")
    except Error as e:
        print(f"Error al conectar a MySQL: {e}")
    return connection

def execute_query(query, params=None, fetch_one=False, is_ddl=False):
    """
    Ejecuta una consulta SQL.
    :param query: La consulta SQL a ejecutar.
    :param params: Parámetros para la consulta SQL (opcional).
    :param fetch_one: True si se espera un solo resultado, False para múltiples.
    :param is_ddl: True si es una sentencia DDL (CREATE, ALTER, etc.) o DML (INSERT, UPDATE, DELETE).
    :return: Resultado de la consulta o None si hay error.
    """
    conn = create_db_connection()
    if conn is None:
        return None
    
    cursor = conn.cursor(dictionary=True) # dictionary=True para obtener resultados como diccionarios
    result = None
    try:
        cursor.execute(query, params)
        if is_ddl: # Para INSERT, UPDATE, DELETE, CREATE
            conn.commit()
            result = cursor.lastrowid if "INSERT" in query.upper() else cursor.rowcount
            print(f"Query DDL/DML ejecutada. Filas afectadas/ID: {result}")
        elif fetch_one:
            result = cursor.fetchone()
        else:
            result = cursor.fetchall()
    except Error as e:
        print(f"Error al ejecutar la consulta: {e}")
        if is_ddl:
            conn.rollback() # Revertir cambios en caso de error para DDL/DML
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
            # print("Conexión a MySQL cerrada")
    return result

def get_estado_id_by_name(nombre_estado):
    """Obtiene el id_estado a partir de su nombre."""
    query = "SELECT id_estado FROM Estado_pedidos WHERE nombre_estado = %s"
    result = execute_query(query, (nombre_estado,), fetch_one=True)
    return result['id_estado'] if result else None

@app.route('/pedidos', methods=['GET'])
def get_pedidos_by_estado():
    """
    Endpoint para obtener pedidos filtrados por estado.
    El estado se pasa como parámetro en la URL, por ejemplo: /pedidos?estado=Enviado
    """
    estado_nombre_query = request.args.get('estado')

    if not estado_nombre_query:
        return jsonify({"error": "Parámetro 'estado' es requerido"}), 400

    # Mapeo de nombres de estado amigables a los nombres en la BD (si es necesario)
    # En este caso, asumimos que los nombres coinciden con los de la tabla Estado_pedidos
    # "Enviados", "Cancelados", "Pagados", "Reenviados"
    
    # Validar que el estado solicitado sea uno de los permitidos
    estados_permitidos = ["Enviados", "Cancelados", "Pagados", "Reenviados"] # Puedes obtenerlos de la BD si prefieres
    if estado_nombre_query not in estados_permitidos:
         return jsonify({"error": f"Estado '{estado_nombre_query}' no es válido. Estados permitidos: {', '.join(estados_permitidos)}"}), 400

    id_estado_filter = get_estado_id_by_name(estado_nombre_query)

    if id_estado_filter is None:
        return jsonify({"error": f"No se encontró el estado '{estado_nombre_query}' en la base de datos."}), 404

    query = """
        SELECT 
            p.id_pedido, 
            p.id_usuario,
            u.nombre_usuario,
            u.apellido_usuario,
            u.correo_electronico,
            p.fecha_pedido, 
            p.direccion_envio, 
            p.id_estado,
            ep.nombre_estado,
            p.total_pedido, 
            p.notas_pedido,
            p.fecha_actualizacion
        FROM Pedidos p
        JOIN Usuarios u ON p.id_usuario = u.id_usuario
        JOIN Estado_pedidos ep ON p.id_estado = ep.id_estado
        WHERE p.id_estado = %s
        ORDER BY p.fecha_pedido DESC;
    """
    
    pedidos = execute_query(query, (id_estado_filter,))

    if pedidos is None: # Error en la consulta
        return jsonify({"error": "Error al obtener los pedidos de la base de datos"}), 500
    
    # Convertir objetos datetime a string para que sean serializables en JSON
    for pedido in pedidos:
        if isinstance(pedido.get('fecha_pedido'), datetime):
            pedido['fecha_pedido'] = pedido['fecha_pedido'].isoformat()
        if isinstance(pedido.get('fecha_actualizacion'), datetime):
            pedido['fecha_actualizacion'] = pedido['fecha_actualizacion'].isoformat()

    return jsonify(pedidos), 200

@app.route('/estados_pedido', methods=['GET'])
def get_all_estados_pedido():
    """Endpoint para obtener todos los estados de pedido disponibles."""
    query = "SELECT id_estado, nombre_estado, descripcion_estado FROM Estado_pedidos ORDER BY nombre_estado;"
    estados = execute_query(query)
    if estados is None:
        return jsonify({"error": "Error al obtener los estados de pedido"}), 500
    return jsonify(estados), 200

# --- Rutas de ejemplo para poblar la tabla Estado_pedidos (opcional) ---
@app.route('/setup_estados', methods=['POST'])
def setup_estados():
    """
    Endpoint para insertar los estados básicos si no existen.
    Esto es útil para la configuración inicial.
    """
    estados_a_insertar = [
        {"nombre": "Pendiente", "descripcion": "Pedido recibido, pendiente de procesamiento."},
        {"nombre": "En Proceso", "descripcion": "El pedido está siendo preparado."},
        {"nombre": "Enviado", "descripcion": "El pedido ha sido enviado al cliente."}, # Usado en tu requerimiento
        {"nombre": "Entregado", "descripcion": "El pedido ha sido entregado al cliente."},
        {"nombre": "Cancelado", "descripcion": "El pedido ha sido cancelado."}, # Usado en tu requerimiento
        {"nombre": "Pagado", "descripcion": "El pedido ha sido pagado por el cliente."}, # Usado en tu requerimiento
        {"nombre": "Reenviado", "descripcion": "El pedido ha sido reenviado."}, # Usado en tu requerimiento
        {"nombre": "Devuelto", "descripcion": "El pedido ha sido devuelto."}
    ]
    
    resultados_insercion = []
    conn = create_db_connection()
    if conn is None:
        return jsonify({"error": "No se pudo conectar a la base de datos"}), 500
    
    cursor = conn.cursor()
    
    for estado in estados_a_insertar:
        try:
            # Verificar si el estado ya existe
            cursor.execute("SELECT id_estado FROM Estado_pedidos WHERE nombre_estado = %s", (estado["nombre"],))
            if cursor.fetchone():
                resultados_insercion.append(f"Estado '{estado['nombre']}' ya existe.")
                continue

            # Insertar el nuevo estado
            query = "INSERT INTO Estado_pedidos (nombre_estado, descripcion_estado) VALUES (%s, %s)"
            cursor.execute(query, (estado["nombre"], estado["descripcion"]))
            conn.commit()
            resultados_insercion.append(f"Estado '{estado['nombre']}' insertado con ID: {cursor.lastrowid}")
        except Error as e:
            conn.rollback()
            resultados_insercion.append(f"Error al insertar estado '{estado['nombre']}': {e}")
    
    if conn.is_connected():
        cursor.close()
        conn.close()
        
    return jsonify({"message": "Proceso de configuración de estados completado.", "details": resultados_insercion}), 201


if __name__ == '__main__':
    # Asegúrate de que la tabla Estado_pedidos tenga los estados necesarios.
    # Puedes llamar a /setup_estados una vez para crearlos si no existen.
    # Ejemplo: curl -X POST http://localhost:5000/setup_estados
    
    # Para probar, asegúrate de tener datos en tus tablas Roles, Usuarios, Estado_pedidos y Pedidos.
    # Por ejemplo, para que /pedidos?estado=Enviado funcione, debe existir un estado con nombre_estado = 'Enviado'
    # y pedidos asociados a ese estado.
    
    print("Para probar el endpoint de pedidos:")
    print("GET http://localhost:5000/pedidos?estado=Enviado")
    print("GET http://localhost:5000/pedidos?estado=Cancelado")
    print("GET http://localhost:5000/pedidos?estado=Pagado")
    print("GET http://localhost:5000/pedidos?estado=Reenviado")
    print("\nPara ver todos los estados disponibles:")
    print("GET http://localhost:5000/estados_pedido")
    print("\nPara configurar los estados iniciales (si no existen):")
    print("POST http://localhost:5000/setup_estados (usar curl o Postman)")
    
    app.run(debug=True, port=5000) # debug=True es para desarrollo

