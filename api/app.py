import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
import csv
import re
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Initialize Flask App
app = Flask(__name__, 
    template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
    static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jobs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

BASE_DIR = Path(__file__).resolve().parent.parent
JOBS_FILE = BASE_DIR / "jobs.csv"

# ==================== DATABASE MODELS ====================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150))
    phone = db.Column(db.String(20))
    skills = db.Column(db.JSON)
    desired_role = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password, password)

class Job(db.Model):
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    company = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    salary = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    categories = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SavedJob(db.Model):
    __tablename__ = 'saved_jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='saved_jobs')
    job = db.relationship('Job', backref='saved_by_users')

class Application(db.Model):
    __tablename__ = 'applications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    resume_filename = db.Column(db.String(255))
    cover_letter = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='applications')
    job = db.relationship('Job', backref='applications')

# ==================== LOGIN MANAGER ====================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== SKILL WEIGHTS ====================

SKILL_WEIGHTS = {
    "python": 3, "machine learning": 3, "artificial intelligence": 4,
    "deep learning": 3, "data science": 3, "data analysis": 2,
    "statistics": 2, "sql": 2, "tensorflow": 2.5, "pytorch": 2.5,
    "computer vision": 3, "natural language processing": 2.5,
    "aws": 2, "azure": 2, "docker": 1.5, "kubernetes": 1.5,
    "linux": 1, "html": 1.5, "css": 1.5, "javascript": 2,
    "bootstrap": 1, "react": 2, "node.js": 2, "rest api": 2,
    "django": 1.5, "flask": 1.5, "mongodb": 1.5, "java": 1.5,
    "git": 1, "data structures": 1, "excel": 1, "power bi": 1.5,
    "cyber security": 3, "web development": 2.5, "cloud computing": 3,
}

SKILL_ALIASES = {
    "python": ["python"],
    "machine learning": ["machine learning", "ml"],
    "artificial intelligence": ["artificial intelligence", "ai"],
    "deep learning": ["deep learning", "dl"],
    "data science": ["data science", "ds"],
    "aws": ["aws"], "azure": ["azure"], "docker": ["docker"],
}

# ==================== UTILITY FUNCTIONS ====================

def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def extract_user_skills(text):
    skills = []
    if not text:
        return skills
    for raw in re.split(r"[,;\n]+", text):
        skill = raw.strip().lower()
        if skill and skill not in skills:
            skills.append(skill)
    return skills

def infer_categories(job_text):
    text = normalize_text(job_text)
    categories = []
    if any(term in text for term in ["ai", "artificial intelligence"]):
        categories.append("ai")
    if any(term in text for term in ["machine learning", "ml"]):
        categories.append("machine-learning")
    if any(term in text for term in ["data science"]):
        categories.append("data-science")
    return categories

def load_jobs_from_db():
    jobs = Job.query.all()
    result = []
    for job in jobs:
        result.append({
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "salary": job.salary,
            "description": job.description,
            "categories": job.categories if job.categories else [],
            "match_score": None,
        })
    return result

def import_jobs_from_csv():
    if Job.query.count() > 0:
        return
    
    if not JOBS_FILE.exists():
        return
    
    with JOBS_FILE.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    
    for row in rows:
        job = Job(
            title=row["Job_Title"],
            company=row["Company"],
            location=row["Location"],
            salary=row["Salary"],
            description=row["Description"],
            categories=infer_categories(f"{row['Job_Title']} {row['Description']}")
        )
        db.session.add(job)
    
    db.session.commit()

def score_job(job, user_skills, desired_role):
    job_text = normalize_text(f"{job['title']} {job['description']}")
    score = 0
    
    for skill in user_skills:
        if skill in SKILL_WEIGHTS:
            score += SKILL_WEIGHTS[skill]
    
    if not user_skills:
        return 0
    
    max_possible = sum(SKILL_WEIGHTS.get(skill, 1) for skill in user_skills)
    if max_possible == 0:
        max_possible = 1
    
    percent = min(100, int(round((score / max_possible) * 100)))
    return percent

# ==================== ROUTES ====================

@app.route("/")
def index():
    jobs = load_jobs_from_db()
    return render_template("index.html", jobs=jobs, summary=None)

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        full_name = request.form.get("full_name", "").strip()
        
        if User.query.filter_by(username=username).first():
            flash("❌ Username already exists!", "danger")
            return redirect(url_for('register'))
        
        user = User(username=username, email=email, full_name=full_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash("✅ Account created! Please login.", "success")
        return redirect(url_for('login'))
    
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash("❌ Invalid credentials!", "danger")
    
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("✅ Logged out!", "success")
    return redirect(url_for('index'))

@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=current_user)

@app.route("/profile/update", methods=["POST"])
@login_required
def update_profile():
    current_user.full_name = request.form.get("full_name", "").strip()
    current_user.phone = request.form.get("phone", "").strip()
    current_user.desired_role = request.form.get("desired_role", "").strip()
    current_user.skills = extract_user_skills(request.form.get("skills", "").strip())
    
    db.session.commit()
    flash("✅ Profile updated!", "success")
    return redirect(url_for('profile'))

@app.route("/match", methods=["GET", "POST"])
def match_jobs():
    if request.method == "GET":
        jobs = load_jobs_from_db()
        return render_template("index.html", jobs=jobs, summary=None)
    
    desired_role = request.form.get("role", "").strip()
    skills_text = request.form.get("skills", "").strip()
    
    user_skills = extract_user_skills(skills_text + " " + desired_role)
    jobs = load_jobs_from_db()
    results = []
    
    for job in jobs:
        score = score_job(job, user_skills, desired_role)
        if score > 0:
            results.append({**job, "match_score": score})
    
    results = sorted(results, key=lambda x: x["match_score"], reverse=True)[:8]
    
    summary = {
        "jobs_found": len(results),
        "highest_match": max([r["match_score"] for r in results]) if results else 0,
        "skills_entered": len(user_skills),
        "recommended": results[0]["title"] if results else "N/A"
    }
    
    return render_template("index.html", jobs=results, summary=summary)

@app.route("/save-job/<int:job_id>", methods=["POST"])
@login_required
def save_job(job_id):
    job = Job.query.get(job_id)
    if not job:
        return {"status": "error"}, 404
    
    saved = SavedJob.query.filter_by(user_id=current_user.id, job_id=job_id).first()
    
    if saved:
        db.session.delete(saved)
        db.session.commit()
        return {"status": "removed"}
    else:
        new_saved = SavedJob(user_id=current_user.id, job_id=job_id)
        db.session.add(new_saved)
        db.session.commit()
        return {"status": "saved"}

@app.route("/saved-jobs")
@login_required
def saved_jobs():
    saved = SavedJob.query.filter_by(user_id=current_user.id).all()
    jobs = []
    for saved_job in saved:
        job = saved_job.job
        jobs.append({
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "salary": job.salary,
            "description": job.description,
            "categories": job.categories if job.categories else [],
            "saved_at": saved_job.saved_at
        })
    
    return render_template("saved_jobs.html", jobs=jobs)

@app.route("/apply", methods=["POST"])
@login_required
def apply_job():
    job_id = request.form.get("job_id")
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    
    if not all([job_id, full_name, email, phone]):
        return {"status": "error", "message": "Missing fields"}, 400
    
    job = Job.query.get(job_id)
    if not job:
        return {"status": "error"}, 404
    
    existing = Application.query.filter_by(user_id=current_user.id, job_id=job_id).first()
    if existing:
        return {"status": "error", "message": "Already applied"}, 400
    
    application = Application(
        user_id=current_user.id,
        job_id=job_id,
        full_name=full_name,
        email=email,
        phone=phone,
        cover_letter=request.form.get("cover_letter", "").strip(),
        status='pending'
    )
    
    db.session.add(application)
    db.session.commit()
    
    return {"status": "success", "message": "Applied successfully!"}

@app.route("/my-applications")
@login_required
def my_applications():
    applications = Application.query.filter_by(user_id=current_user.id).all()
    
    apps = []
    for app in applications:
        job = app.job
        apps.append({
            "id": app.id,
            "job_title": job.title,
            "company": job.company,
            "location": job.location,
            "status": app.status,
            "applied_at": app.applied_at,
        })
    
    return render_template("my_applications.html", applications=apps)

@app.route("/application/<int:app_id>/cancel", methods=["POST"])
@login_required
def cancel_application(app_id):
    application = Application.query.get(app_id)
    if not application:
        return {"status": "error"}, 404
    
    if application.user_id != current_user.id:
        return {"status": "error"}, 403
    
    db.session.delete(application)
    db.session.commit()
    
    return {"status": "success"}

@app.route("/applications-stats")
@login_required
def applications_stats():
    total = Application.query.filter_by(user_id=current_user.id).count()
    pending = Application.query.filter_by(user_id=current_user.id, status='pending').count()
    
    return {
        "total": total,
        "pending": pending,
        "reviewed": 0,
        "accepted": 0,
        "rejected": 0
    }

# Initialize database when the module is imported
with app.app_context():
    db.create_all()
    import_jobs_from_csv()

if __name__ == "__main__":
    app.run(debug=False)