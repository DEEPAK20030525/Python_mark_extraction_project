from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
import sqlite3
import os
import pandas as pd

app = Flask(__name__)
app.secret_key = 'your_secret_key'
conn = sqlite3.connect('database.db', check_same_thread=False)

# Function to create database tables
def create_tables():
    # Existing table creations
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.execute('''CREATE TABLE IF NOT EXISTS admin_login(username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL)''')
    conn.commit()
    
    conn.execute('''CREATE TABLE IF NOT EXISTS student_marks(username TEXT NOT NULL,
            roll_number INTEGER PRIMARY KEY NOT NULL,
            department TEXT,
            iae_1 INTEGER,
            iae_2 INTEGER,
            iae_3 INTEGER
            )
            ''')
    conn.commit()
    
    # New table for change logs
    conn.execute('''
        CREATE TABLE IF NOT EXISTS change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_number INTEGER,
            username TEXT,
            change_type TEXT,
            change_details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()


# Function to check if a user exists
def user_exists(username):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    return user is not None

# Route for login page
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        roll_number = request.form['roll_number']
        password = request.form['password']
        cursor = conn.cursor()
        
        # Check if the roll number exists in the student_marks table
        cursor.execute("SELECT * FROM student_marks WHERE roll_number = ?", (roll_number,))
        student = cursor.fetchone()
        
        if student and str(student[1]) == password:
            session['roll_number'] = roll_number
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid roll number or password', 'error')

    return render_template('index.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin_login WHERE username = ? AND password = ?", (username, password))
        user = cursor.fetchone()
        if user:
            session['username'] = username
            return redirect(url_for('admin'))
        else:
            flash('Incorrect username or password', 'error')
    return render_template('admin_login.html')
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'error')
        else:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                file.save(file_path)
                df = pd.read_excel(file_path)
                cursor = conn.cursor()
                for index, row in df.iterrows():
                    if 'roll_number' not in row:
                        continue
                    cursor.execute("SELECT * FROM student_marks WHERE roll_number = ?", (row['roll_number'],))
                    existing_data = cursor.fetchone()
                    if existing_data:
                        cursor.execute("""
                            UPDATE student_marks
                            SET username = ?, department = ?, iae_1 = ?, iae_2 = ?, iae_3 = ?
                            WHERE roll_number = ?
                        """, (row['username'], row['department'], row['iae_1'], row['iae_2'], row['iae_3'], row['roll_number']))
                    else:
                        cursor.execute("INSERT INTO student_marks (username, roll_number, department, iae_1, iae_2, iae_3) VALUES (?, ?, ?, ?, ?, ?)",
                                       (row['username'], row['roll_number'], row['department'], row['iae_1'], row['iae_2'], row['iae_3']))
                    conn.commit()
                
                # Log the upload action
                username = session.get('username', 'unknown')
                change_details = f"Uploaded Excel file: {filename}"
                cursor.execute("INSERT INTO change_log (username, change_type, change_details) VALUES (?, ?, ?)",
                               (username, 'upload', change_details))
                conn.commit()
                
                flash('File uploaded successfully and data stored in the database.', 'success')
            except Exception as e:
                flash(f'An error occurred: {e}', 'error')
    return render_template('admin.html')



@app.route('/dashboard')
def dashboard():
    if 'roll_number' in session:
        roll_number = session['roll_number']
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM student_marks WHERE roll_number = ?", (roll_number,))
        data = cursor.fetchone()
        if data:
            return render_template('dashboard.html', roll_number=roll_number, data=data)
        else:
            flash('No data found for this user', 'error')
            return redirect(url_for('index'))
    else:
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('roll_number', None)
    flash('You have been logged out', 'success')
    return redirect(url_for('index'))

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Function to create the 'uploads' directory if it doesn't exist
def create_upload_directory():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        try:
            os.makedirs(app.config['UPLOAD_FOLDER'])
            os.chmod(app.config['UPLOAD_FOLDER'], 0o755)
        except OSError as e:
            print(f"Error creating upload directory: {e}")



@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        existing_user = cursor.fetchone()
        if existing_user:
            flash('Username already exists', 'error')
        else:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            flash('User added successfully', 'success')
            return redirect(url_for('index'))

    return render_template('add_user.html')




@app.route('/student_details')
def student_details():
    roll_number = request.args.get('roll_number', '')
    username = request.args.get('username', '')
    department = request.args.get('department', '')

    query = "SELECT * FROM student_marks WHERE 1=1"
    params = []

    if roll_number:
        query += " AND roll_number LIKE ?"
        params.append(f"%{roll_number}%")
    if username:
        query += " AND username LIKE ?"
        params.append(f"%{username}%")
    if department:
        query += " AND department LIKE ?"
        params.append(f"%{department}%")

    cursor = conn.cursor()
    cursor.execute(query, params)
    students = cursor.fetchall()
    
    return render_template('student_details.html', students=students)




@app.route('/view_student/<int:roll_number>')
def view_student(roll_number):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM student_marks WHERE roll_number = ?", (roll_number,))
    student = cursor.fetchone()
    return render_template('view_student.html', student=student)





@app.route('/update_student/<int:roll_number>', methods=['GET', 'POST'])
def update_student(roll_number):
    cursor = conn.cursor()
    if request.method == 'POST':
        username = request.form['username']
        department = request.form['department']
        iae_1 = request.form['iae_1']
        iae_2 = request.form['iae_2']
        iae_3 = request.form['iae_3']
        
        cursor.execute("SELECT * FROM student_marks WHERE roll_number = ?", (roll_number,))
        old_student = cursor.fetchone()
        
        cursor.execute("""
            UPDATE student_marks
            SET username = ?, department = ?, iae_1 = ?, iae_2 = ?, iae_3 = ?
            WHERE roll_number = ?
        """, (username, department, iae_1, iae_2, iae_3, roll_number))
        conn.commit()
        
        change_details = f"Updated student from {old_student} to {(username, department, iae_1, iae_2, iae_3)}"
        cursor.execute("INSERT INTO change_log (roll_number, username, change_type, change_details) VALUES (?, ?, ?, ?)",
                       (roll_number, session.get('username', 'unknown'), 'update', change_details))
        conn.commit()
        
        flash('Student updated successfully', 'success')
        return redirect(url_for('student_details'))
    
    cursor.execute("SELECT * FROM student_marks WHERE roll_number = ?", (roll_number,))
    student = cursor.fetchone()
    return render_template('update_student.html', student=student)

@app.route('/delete_student/<int:roll_number>')
def delete_student(roll_number):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM student_marks WHERE roll_number = ?", (roll_number,))
    student = cursor.fetchone()
    
    cursor.execute("DELETE FROM student_marks WHERE roll_number = ?", (roll_number,))
    conn.commit()
    
    change_details = f"Deleted student {student}"
    cursor.execute("INSERT INTO change_log (roll_number, username, change_type, change_details) VALUES (?, ?, ?, ?)",
                   (roll_number, session.get('username', 'unknown'), 'delete', change_details))
    conn.commit()
    
    flash('Student deleted successfully', 'success')
    return redirect(url_for('student_details'))


@app.route('/report', methods=['GET', 'POST'])
def report():
    cursor = conn.cursor()
    query = "SELECT * FROM change_log WHERE 1=1"
    params = []

    # Check if the form is submitted
    if request.method == 'POST':
        roll_number = request.form.get('roll_number', '')
        username = request.form.get('username', '')
        change_type = request.form.get('change_type', '')

        # Add filters to the query based on the submitted form data
        if roll_number:
            query += " AND roll_number = ?"
            params.append(roll_number)
        if username:
            query += " AND username LIKE ?"
            params.append(f"%{username}%")
        if change_type:
            query += " AND change_type = ?"
            params.append(change_type)

    cursor.execute(query, params)
    changes = cursor.fetchall()
    return render_template('report.html', changes=changes)




if __name__ == '__main__':
    create_tables()
    create_upload_directory()
    app.run(debug=True)
