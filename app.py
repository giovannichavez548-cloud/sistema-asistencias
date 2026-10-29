from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import sqlite3
import qrcode
import io
import base64
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'clave_secreta_proyecto_limpio'

GRUPOS_VALIDOS = ['101', '102', '103', '104', '105', '301', '302', '303', '304', '305', '501', '502', '503', '504', '505']

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alumnos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            matricula TEXT UNIQUE NOT NULL,
            grupo TEXT NOT NULL,
            numero_lista INTEGER NOT NULL,
            correo TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS docentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            asignatura TEXT NOT NULL,
            correo TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS asistencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alumno_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            FOREIGN KEY (alumno_id) REFERENCES alumnos (id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

# --- ALUMNOS ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form.get('correo')
        password = request.form.get('password')
        conn = get_db_connection()
        cursor = conn.cursor()
        alumno = cursor.execute('SELECT * FROM alumnos WHERE correo = ? AND password = ?', (correo, password)).fetchone()
        conn.close()
        if alumno:
            session['alumno_id'] = alumno['id']
            return redirect(url_for('panel'))
        else:
            flash('Correo o contraseña incorrectos.')
    return render_template('login_alumno.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        matricula = request.form.get('matricula')
        grupo = request.form.get('grupo')
        numero_lista = request.form.get('numero_lista')
        correo = request.form.get('correo')
        password = request.form.get('password')

        if grupo not in GRUPOS_VALIDOS:
            flash('Grupo no válido.')
            return render_template('registro_alumno.html', grupos=GRUPOS_VALIDOS)

        conn = get_db_connection()
        cursor = conn.cursor()

        existente_general = cursor.execute('SELECT * FROM alumnos WHERE correo = ? OR matricula = ?', (correo, matricula)).fetchone()
        if existente_general:
            conn.close()
            flash('El correo o el número de control ya están registrados.')
            return render_template('registro_alumno.html', grupos=GRUPOS_VALIDOS)

        existente_lista = cursor.execute('SELECT * FROM alumnos WHERE grupo = ? AND numero_lista = ?', (grupo, numero_lista)).fetchone()
        if existente_lista:
            conn.close()
            flash(f'El número de lista {numero_lista} ya está ocupado en el grupo {grupo}.')
            return render_template('registro_alumno.html', grupos=GRUPOS_VALIDOS)

        try:
            cursor.execute('INSERT INTO alumnos (nombre, matricula, grupo, numero_lista, correo, password) VALUES (?, ?, ?, ?, ?, ?)',
                           (nombre, matricula, grupo, numero_lista, correo, password))
            conn.commit()
            conn.close()
            flash('Cuenta creada con éxito. Inicia sesión.')
            return redirect(url_for('login'))
        except Exception as e:
            conn.close()
            flash('Error al registrar la cuenta.')
            
    return render_template('registro_alumno.html', grupos=GRUPOS_VALIDOS)

@app.route('/panel')
def panel():
    if 'alumno_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    alumno = cursor.execute('SELECT * FROM alumnos WHERE id = ?', (session['alumno_id'],)).fetchone()
    conn.close()

    qr_img = qrcode.make(alumno['matricula'])
    buf = io.BytesIO()
    qr_img.save(buf, format='PNG')
    qr_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    return render_template('panel_alumno.html', alumno=alumno, qr_code=qr_base64)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- DOCENTES ---
@app.route('/docente/login', methods=['GET', 'POST'])
def docente_login():
    if request.method == 'POST':
        correo = request.form.get('correo')
        password = request.form.get('password')
        conn = get_db_connection()
        cursor = conn.cursor()
        docente = cursor.execute('SELECT * FROM docentes WHERE correo = ? AND password = ?', (correo, password)).fetchone()
        conn.close()
        if docente:
            session['docente_id'] = docente['id']
            session['docente_nombre'] = docente['nombre']
            session['docente_materia'] = docente['asignatura']
            return redirect(url_for('docente_panel'))
        else:
            flash('Correo o contraseña incorrectos.')
    return render_template('login_docente.html')

@app.route('/docente/registro', methods=['GET', 'POST'])
def docente_registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        asignatura = request.form.get('asignatura')
        correo = request.form.get('correo')
        password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor()
        existente = cursor.execute('SELECT * FROM docentes WHERE correo = ?', (correo,)).fetchone()
        if existente:
            conn.close()
            flash('El correo ya está registrado.')
            return render_template('registro_docente.html')

        try:
            cursor.execute('INSERT INTO docentes (nombre, asignatura, correo, password) VALUES (?, ?, ?, ?)',
                           (nombre, asignatura, correo, password))
            conn.commit()
            conn.close()
            flash('Cuenta creada con éxito. Inicia sesión.')
            return redirect(url_for('docente_login'))
        except Exception as e:
            conn.close()
            flash('Error al registrar la cuenta.')
    return render_template('registro_docente.html')

@app.route('/docente/panel', methods=['GET', 'POST'])
def docente_panel():
    if 'docente_id' not in session:
        return redirect(url_for('docente_login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    grupo_seleccionado = request.form.get('grupo') or request.args.get('grupo') or '305'
    busqueda_lista = request.form.get('busqueda_lista') or request.args.get('busqueda_lista') or ''
    
    query = '''
        SELECT a.nombre, a.matricula, a.grupo, a.numero_lista, 
               MAX(s.fecha) as ultima_fecha, 
               MAX(s.hora) as ultima_hora,
               COUNT(s.id) as total_asistencias
        FROM alumnos a
        LEFT JOIN asistencias s ON a.id = s.alumno_id
        WHERE a.grupo = ?
    '''
    params = [grupo_seleccionado]

    if busqueda_lista:
        query += ' AND a.numero_lista = ?'
        params.append(busqueda_lista)

    query += ' GROUP BY a.id ORDER BY a.numero_lista ASC'
    
    alumnos_lista = cursor.execute(query, params).fetchall()
    conn.close()
    
    return render_template('docente.html', grupos=GRUPOS_VALIDOS, alumnos=alumnos_lista, grupo_actual=grupo_seleccionado, asignatura=session.get('docente_materia'), busqueda_lista=busqueda_lista)

@app.route('/docente/logout')
def docente_logout():
    session.clear()
    return redirect(url_for('index'))

# --- ADMINISTRADOR / ESCÁNER ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        correo = request.form.get('correo')
        password = request.form.get('password')
        if correo == 'administrador_@gmail.com' and password == '1234567':
            session['admin_logged'] = True
            return redirect(url_for('admin_escaner'))
        else:
            flash('Credenciales incorrectas.')
    return render_template('login_admin.html')

@app.route('/admin/escaner')
def admin_escaner():
    if not session.get('admin_logged'):
        return redirect(url_for('admin_login'))
    return render_template('escaner.html')

@app.route('/api/registrar-asistencia', methods=['POST'])
def registrar_asistencia():
    if not session.get('admin_logged'):
        return jsonify({'success': False, 'message': 'No autorizado'}), 401
    data = request.get_json()
    qr_data = data.get('qr_data')
    if not qr_data:
        return jsonify({'success': False, 'message': 'QR inválido'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    alumno = cursor.execute('SELECT * FROM alumnos WHERE matricula = ?', (qr_data,)).fetchone()
    if not alumno:
        conn.close()
        return jsonify({'success': False, 'message': f'Alumno no encontrado ({qr_data})'}), 404

    ahora = datetime.now()
    fecha = ahora.strftime('%Y-%m-%d')
    hora = ahora.strftime('%H:%M:%S')

    try:
        cursor.execute('INSERT INTO asistencias (alumno_id, fecha, hora) VALUES (?, ?, ?)', (alumno['id'], fecha, hora))
        conn.commit()
        conn.close()
        return jsonify({
            'success': True,
            'alumno': {'nombre': alumno['nombre'], 'hora': hora}
        })
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)