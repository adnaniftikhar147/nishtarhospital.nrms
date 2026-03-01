import os
import random
from flask import Flask, jsonify, request, render_template, redirect, url_for, session, flash
from datetime import datetime, date, timedelta
from werkzeug.utils import secure_filename
from models import db, Employee, ServiceHistory, User, Department
import traceback

base_dir = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, 
            template_folder=os.path.join(base_dir, 'templates'),
            static_folder=os.path.join(base_dir, 'static'))

startup_error = None

@app.errorhandler(Exception)
def handle_exception(e):
    return f"<h1>Internal Server Error (Caught by Handler)</h1><pre>{traceback.format_exc()}</pre>", 500

# Configure SQLite DB for simplicity and portability
app.secret_key = 'super_secret_hrms_key_123'

# Check if current directory is writable (Vercel is read-only)
is_writable = False
try:
    with open('test_write.txt', 'w') as f:
        f.write('test')
    os.remove('test_write.txt')
    is_writable = True
except Exception:
    is_writable = False

if not is_writable:
    # Use /tmp for read-only environments like Vercel Serverless
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/hrms.db'
    app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hrms.db'
    app.config['UPLOAD_FOLDER'] = 'static/uploads'
    
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

def seed_data():
    """Populate database with a test employee if it's empty"""
    if Employee.query.count() == 0:
        emp = Employee(
            name='Ali Hassan',
            father_name='Muhammad Tufail',
            cnic='36302-1234567-9',
            dob=date(1990, 8, 14),
            address='House 42, St 5, Multan',
            mobile_no='0300-1234567',
            file_no='NH-2023-WB-092',
            department='Male Surgical Ward',
            designation='Ward Boy',
            bps=3,
            joining_date=date(2015, 1, 1),
            regularization_date=date(2018, 1, 1), # Regular employee since 2018
            retirement_date=date(2050, 8, 14)
        )
        db.session.add(emp)
        db.session.commit()
        
        # Add a couple of mock history logs for the seeded employee
        h1 = ServiceHistory(
            employee_id=emp.id,
            document_type='Leave Application',
            document_content='Generated 10-day casual leave application. Saved to digital profile.',
            generated_on=datetime(2023, 10, 12, 10, 30)
        )
        h2 = ServiceHistory(
            employee_id=emp.id,
            document_type='Warning Letter',
            document_content='Issued due to multiple unauthorized absences.',
            generated_on=datetime(2023, 9, 5, 14, 15)
        )
        db.session.add(h1)
        db.session.add(h2)
        db.session.commit()
        
    if User.query.count() == 0:
        admin_user = User(username='admin', role='HR Manager', email='admin@nishtar.com')
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()


# Create tables and seed data on startup
try:
    with app.app_context():
        db.create_all()
        seed_data()
except Exception as e:
    startup_error = str(e)
    print("Database Startup Error:", startup_error)

# --- Authentication Logic ---
@app.before_request
def require_login():
    global startup_error
    if startup_error:
        return f"<h1>Internal Server Error (Startup)</h1><p>The app failed to start correctly. Error details below so you can share them:</p><pre>{startup_error}</pre>", 500
        
    allowed_routes = ['login', 'register', 'forgot_password', 'api_request_otp', 'api_verify_otp', 'api_reset_password', 'static']
    if request.endpoint not in allowed_routes and 'user_id' not in session:
        return redirect(url_for('login'))

@app.context_processor
def inject_global_data():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    
    departments = []
    try:
        departments = Department.query.order_by(Department.name.asc()).all()
    except Exception:
        pass
        
    return dict(current_user=user, global_departments=departments)

@app.route('/api/departments', methods=['POST'])
def add_department():
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Department name is required'}), 400
        
    existing = Department.query.filter_by(name=name).first()
    if existing:
        return jsonify({'error': 'Department already exists'}), 400
        
    new_dept = Department(name=name)
    try:
        db.session.add(new_dept)
        db.session.commit()
        return jsonify({'message': 'Department added', 'id': new_dept.id, 'name': new_dept.name}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')
            return render_template('login.html')
            
    # Don't show login page if already logged in
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not username or not password:
            flash('Username and Password are required.', 'error')
            return render_template('register.html')
            
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'error')
            return render_template('register.html')

        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully! You can now login.', 'success')
        return redirect(url_for('login'))

    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    return render_template('register.html')

@app.route('/forgot-password', methods=['GET'])
def forgot_password():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('forgot_password.html')

@app.route('/api/request-otp', methods=['POST'])
def api_request_otp():
    data = request.json
    username_or_email = data.get('username', '').strip()
    
    user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()
    
    if not user:
        return jsonify({'success': False, 'message': 'Username or E-mail does not exist. Please check and try again.'})

    otp = str(random.randint(100000, 999999))
    user.reset_otp = otp
    user.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
    db.session.commit()
    print(f"--- FAKE OTP EMAIL TO: {username_or_email} --- OTP: {otp}\n", flush=True)

    return jsonify({'success': True, 'message': 'OTP aap ke registered e-mail address par bhej diya gaya hai. Meharbani farma kar OTP enter karein.', 'temp_otp': otp})

@app.route('/api/verify-otp', methods=['POST'])
def api_verify_otp():
    data = request.json
    username_or_email = data.get('username', '').strip()
    entered_otp = data.get('otp', '').strip()
    
    user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()
    
    if user and user.reset_otp == entered_otp and user.otp_expiry and user.otp_expiry > datetime.utcnow():
        return jsonify({'success': True, 'message': 'OTP Verify ho gaya hai. Apna naya password set karein.'})
    else:
        return jsonify({'success': False, 'message': 'Invalid OTP or OTP has expired. Please try again.'})

@app.route('/api/reset-password', methods=['POST'])
def api_reset_password():
    data = request.json
    username_or_email = data.get('username', '').strip()
    entered_otp = data.get('otp', '').strip()
    new_password = data.get('new_password', '')
    
    user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()
    
    if user and user.reset_otp == entered_otp and user.otp_expiry and user.otp_expiry > datetime.utcnow():
        if len(new_password) < 8:
            return jsonify({'success': False, 'message': 'Password must be at least 8 characters long.'})
            
        user.set_password(new_password)
        user.reset_otp = None
        user.otp_expiry = None
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Password reset successfully! You can now login.'})
    else:
        return jsonify({'success': False, 'message': 'Security verification failed. Please restart the process.'})

@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        user = User.query.get(session['user_id'])
        
        if not user.check_password(current_password):
            flash('Incorrect current password.', 'error')
            return redirect(url_for('change_password'))
            
        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('change_password'))
            
        if len(new_password) < 8:
            flash('New password must be at least 8 characters long.', 'error')
            return redirect(url_for('change_password'))
            
        user.set_password(new_password)
        db.session.commit()
        
        flash('Password changed successfully.', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('change_password.html', active_page='change_password')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# Root Route to Redirect to Dashboard
@app.route('/')
def index():
    return redirect(url_for('dashboard'))

# --- 1. Dashboard View & API ---
@app.route('/dashboard', methods=['GET'])
def dashboard():
    total_employees = Employee.query.count()
    today = date.today()
    expiring_contracts = Employee.query.filter(
        Employee.contract_expiration_date != None,
        Employee.contract_expiration_date >= today
    ).order_by(Employee.contract_expiration_date.asc()).all()
    
    # Calculate upcoming retirements approx
    upcoming_retirements_count = 0 

    # Fetch recent logs for dashboard
    recent_logs = ServiceHistory.query.order_by(ServiceHistory.generated_on.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                            active_page='dashboard',
                            total_employees=total_employees,
                            expiring_contracts_count=len(expiring_contracts),
                            upcoming_retirements_count=upcoming_retirements_count,
                            recent_logs=recent_logs)

# --- 2. Find Staff Directory View ---
@app.route('/directory', methods=['GET'])
def find_staff():
    employees = Employee.query.order_by(Employee.id.desc()).all()
    return render_template('find_staff.html', active_page='find_staff', employees=employees)

@app.route('/department-list', methods=['GET'])
def department_list():
    return render_template('department_list.html', active_page='department_list')

# --- 3. Global Activity Reports View ---
@app.route('/reports', methods=['GET'])
def reports():
    logs = ServiceHistory.query.order_by(ServiceHistory.generated_on.desc()).all()
    return render_template('reports.html', active_page='reports', logs=logs)

# --- API: Search / Filter ---
@app.route('/api/employees/search', methods=['GET'])
def search_employee():
    """ 
    1-click search functionality 
    Filter by Query param 'q' which checks CNIC, File No, or Name.
    """
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
        
    employees = Employee.query.filter(
        (Employee.file_no == query) | 
        (Employee.cnic == query) | 
        (Employee.name.ilike(f'%{query}%'))
    ).all()
    
    return jsonify([emp.to_dict() for emp in employees])

@app.route('/api/employees/department', methods=['GET'])
def get_employees_by_department():
    dept_name = request.args.get('dept', '')
    if not dept_name:
        return jsonify([])
        
    employees = Employee.query.filter_by(department=dept_name).order_by(Employee.bps.desc()).all()
    return jsonify([emp.to_dict() for emp in employees])

# --- 3. Profile Template View ---
@app.route('/employee/<int:employee_id>', methods=['GET'])
def view_employee_profile(employee_id):
    """
    Returns the HTML/CSS template for the Employee Profile page with live DB data.
    """
    employee = Employee.query.get_or_404(employee_id)
    # Fetch log history dynamically for this employee
    history = ServiceHistory.query.filter_by(employee_id=employee.id).order_by(ServiceHistory.generated_on.desc()).all()
    # Fetch all employees to populate the file number dropdown
    all_employees = Employee.query.order_by(Employee.file_no.asc()).all()
    
    return render_template('profile.html', active_page='profile', employee=employee, history=history, all_employees=all_employees)

# --- 4. Document Generator & Service History ---
@app.route('/api/employees/<int:employee_id>/generate_document', methods=['POST'])
def generate_document(employee_id):
    """
    1-click button to generate templates.
    Auto-saves to the Employee's Service History Log.
    """
    data = request.json
    doc_type = data.get('document_type')
    
    valid_documents = [
        'Explanation Letter', 'Show Cause Notice', 
        'Leave Application', 'Warning Letter', 
        'NOC', 'Retirement Orders'
    ]
    
    if doc_type not in valid_documents:
        return jsonify({'error': 'Invalid document type'}), 400
        
    employee = Employee.query.get_or_404(employee_id)
    
    # Template auto-fill logic representation
    doc_content = f"Official {doc_type} generated for {employee.name} (Designation: {employee.designation}, BPS-{employee.bps:02d}) on {datetime.now().strftime('%d %b %Y')}."
    
    # Save to Service History Log automatically
    history_entry = ServiceHistory(
        employee_id=employee.id,
        document_type=doc_type,
        document_content=doc_content
    )
    db.session.add(history_entry)
    db.session.commit()
    
    return jsonify({
        'message': f'{doc_type} generated successfully and logged.',
        'log': history_entry.to_dict()
    }), 201

# --- 5. Add Employee API ---


@app.route('/api/employees', methods=['POST'])
def add_employee():
    data = request.json
    try:
        new_emp = Employee(
            name=data.get('name'),
            father_name=data.get('father_name'),
            cnic=data.get('cnic'),
            dob=datetime.strptime(data['dob'], '%Y-%m-%d').date() if data.get('dob') else None,
            address=data.get('address'),
            mobile_no=data.get('mobile_no'),
            file_no=data.get('file_no'),
            designation=data.get('designation'),
            bps=int(data.get('bps')) if data.get('bps') else None,
            joining_date=datetime.strptime(data['joining_date'], '%Y-%m-%d').date() if data.get('joining_date') else None,
            contract_expiration_date=datetime.strptime(data['contract_expiration_date'], '%Y-%m-%d').date() if data.get('contract_expiration_date') else None,
            regularization_date=datetime.strptime(data['regularization_date'], '%Y-%m-%d').date() if data.get('regularization_date') else None,
            department=data.get('department'),
            retirement_date=datetime.strptime(data['retirement_date'], '%Y-%m-%d').date() if data.get('retirement_date') else None
        )
        db.session.add(new_emp)
        db.session.commit()
        return jsonify({'message': 'Employee added successfully!', 'id': new_emp.id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/employees/<int:employee_id>', methods=['PUT', 'DELETE'])
def edit_or_delete_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    
    if request.method == 'DELETE':
        db.session.delete(employee)
        db.session.commit()
        return jsonify({'message': 'Employee deleted successfully!'})
        
    if request.method == 'PUT':
        data = request.json
        try:
            employee.name = data.get('name', employee.name)
            employee.father_name = data.get('father_name', employee.father_name)
            employee.cnic = data.get('cnic', employee.cnic)
            employee.address = data.get('address', employee.address)
            employee.mobile_no = data.get('mobile_no', employee.mobile_no)
            employee.file_no = data.get('file_no', employee.file_no)
            employee.designation = data.get('designation', employee.designation)
            employee.department = data.get('department', employee.department)
            
            if data.get('bps'):
                employee.bps = int(data.get('bps'))
            if data.get('dob'):
                employee.dob = datetime.strptime(data['dob'], '%Y-%m-%d').date()
            if data.get('joining_date'):
                employee.joining_date = datetime.strptime(data['joining_date'], '%Y-%m-%d').date()
            
            if 'contract_expiration_date' in data:
                employee.contract_expiration_date = datetime.strptime(data['contract_expiration_date'], '%Y-%m-%d').date() if data['contract_expiration_date'] else None
            if 'regularization_date' in data:
                employee.regularization_date = datetime.strptime(data['regularization_date'], '%Y-%m-%d').date() if data['regularization_date'] else None
            if 'retirement_date' in data:
                employee.retirement_date = datetime.strptime(data['retirement_date'], '%Y-%m-%d').date() if data['retirement_date'] else None
                
            db.session.commit()
            return jsonify({'message': 'Employee updated successfully!', 'id': employee.id}), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 400

@app.route('/api/employees/<int:employee_id>/upload_picture', methods=['POST'])
def upload_picture(employee_id):
    if 'profile_image' not in request.files:
        return jsonify({'error': 'No file part'}), 400
        
    file = request.files['profile_image']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file:
        filename = secure_filename(f"emp_{employee_id}_{file.filename}")
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        employee = Employee.query.get_or_404(employee_id)
        employee.profile_picture = filename
        db.session.commit()
        
        return jsonify({'message': 'Profile picture uploaded successfully', 'filename': filename}), 200

if __name__ == '__main__':
    # Ensure templates and static directories exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    # Run the Flask app
    app.run()
