from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True) 
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='HR Manager') # e.g., Admin, HR Manager
    
    # OTP Security Fields
    reset_otp = db.Column(db.String(6), nullable=True)
    otp_expiry = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Employee(db.Model):
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # 1. Personal Info
    name = db.Column(db.String(100), nullable=False)
    father_name = db.Column(db.String(100), nullable=False)
    cnic = db.Column(db.String(15), unique=True, nullable=False) # Expected format: 00000-0000000-0
    dob = db.Column(db.Date, nullable=False)
    address = db.Column(db.Text, nullable=False)
    mobile_no = db.Column(db.String(15), nullable=False)
    profile_picture = db.Column(db.String(255), nullable=True, default='default-avatar.png')
    
    # 2. Service Info
    file_no = db.Column(db.String(50), unique=True, nullable=False)
    designation = db.Column(db.String(100), nullable=False)
    bps = db.Column(db.Integer, nullable=False) # Restricted between 1 and 4 via validation layer
    joining_date = db.Column(db.Date, nullable=False)
    contract_expiration_date = db.Column(db.Date, nullable=True) # Null if regular
    regularization_date = db.Column(db.Date, nullable=True)      # Null if contract
    department = db.Column(db.String(150), nullable=True)        # Ward / Department
    retirement_date = db.Column(db.Date, nullable=True)          # Date of Retirement
    
    # Relationships
    service_history = db.relationship('ServiceHistory', backref='employee', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'father_name': self.father_name,
            'cnic': self.cnic,
            'dob': self.dob.isoformat() if self.dob else None,
            'address': self.address,
            'mobile_no': self.mobile_no,
            'profile_picture': self.profile_picture,
            'file_no': self.file_no,
            'designation': self.designation,
            'bps': self.bps,
            'joining_date': self.joining_date.isoformat() if self.joining_date else None,
            'contract_expiration_date': self.contract_expiration_date.isoformat() if self.contract_expiration_date else None,
            'regularization_date': self.regularization_date.isoformat() if self.regularization_date else None,
            'department': self.department,
            'retirement_date': self.retirement_date.isoformat() if self.retirement_date else None
        }

class ServiceHistory(db.Model):
    __tablename__ = 'service_history'
    
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    
    # Type of document generated
    document_type = db.Column(db.String(100), nullable=False) 
    # e.g., 'Explanation Letter', 'Show Cause Notice', 'Leave Application', 'Warning Letter', 'NOC', 'Retirement Orders'
    
    # Content or path to the saved PDF
    document_content = db.Column(db.Text, nullable=True)
    
    # Auto-timestamp for service log
    generated_on = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'document_type': self.document_type,
            'generated_on': self.generated_on.strftime("%Y-%m-%d %H:%M:%S"),
            'document_content': self.document_content
        }
