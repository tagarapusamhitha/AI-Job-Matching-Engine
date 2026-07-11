from pathlib import Path
import csv
import re
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jobs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

BASE_DIR = Path(__file__).resolve().parent
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
        """Hash and set password"""
        self.password = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

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
    
    def __repr__(self):
        return f'<Job {self.title}>'
# ...existing Job model...

class SavedJob(db.Model):
    __tablename__ = 'saved_jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='saved_jobs')
    job = db.relationship('Job', backref='saved_by_users')
    
    def __repr__(self):
        return f'<SavedJob {self.user_id}-{self.job_id}>'

# ...rest of your code...

# ==================== LOGIN MANAGER ====================

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID"""
    return User.query.get(int(user_id))

# ==================== SKILL CONFIGURATION ====================

SKILL_WEIGHTS = {
    "python": 3,
    "machine learning": 3,
    "artificial intelligence": 4,
    "deep learning": 3,
    "data science": 3,
    "data analysis": 2,
    "statistics": 2,
    "sql": 2,
    "tensorflow": 2.5,
    "pytorch": 2.5,
    "computer vision": 3,
    "natural language processing": 2.5,
    "aws": 2,
    "azure": 2,
    "docker": 1.5,
    "kubernetes": 1.5,
    "linux": 1,
    "html": 1.5,
    "css": 1.5,
    "javascript": 2,
    "bootstrap": 1,
    "react": 2,
    "node.js": 2,
    "rest api": 2,
    "django": 1.5,
    "flask": 1.5,
    "mongodb": 1.5,
    "java": 1.5,
    "git": 1,
    "data structures": 1,
    "excel": 1,
    "power bi": 1.5,
    "cyber security": 3,
    "web development": 2.5,
    "cloud computing": 3,
    "cloud": 2,
    "research": 1.5,
}

SKILL_ALIASES = {
    "python": ["python"],
    "machine learning": ["machine learning", "ml"],
    "artificial intelligence": ["artificial intelligence", "ai"],
    "deep learning": ["deep learning", "dl"],
    "data science": ["data science", "ds"],
    "data analysis": ["data analysis"],
    "statistics": ["statistics", "statistical"],
    "sql": ["sql"],
    "tensorflow": ["tensorflow", "tf"],
    "pytorch": ["pytorch"],
    "computer vision": ["computer vision", "cv"],
    "natural language processing": ["natural language processing", "nlp"],
    "aws": ["aws"],
    "azure": ["azure"],
    "docker": ["docker"],
    "kubernetes": ["kubernetes"],
    "linux": ["linux"],
    "html": ["html"],
    "css": ["css"],
    "javascript": ["javascript", "js"],
    "bootstrap": ["bootstrap"],
    "react": ["react"],
    "node.js": ["node js", "node.js", "node"],
    "rest api": ["rest api", "rest-api"],
    "django": ["django"],
    "flask": ["flask"],
    "mongodb": ["mongodb"],
    "java": ["java"],
    "git": ["git"],
    "data structures": ["data structures"],
    "excel": ["excel"],
    "power bi": ["power bi", "powerbi"],
    "cyber security": ["cyber security", "cyber-security"],
    "web development": ["web development", "web-dev", "webdev"],
    "cloud computing": ["cloud computing", "cloud"],
    "research": ["research"],
}

FILTER_LABELS = {
    "all": "All",
    "ai": "AI",
    "machine-learning": "Machine Learning",
    "data-science": "Data Science",
    "python": "Python",
    "web-development": "Web Development",
    "cyber-security": "Cyber Security",
    "cloud-computing": "Cloud Computing",
}

# ==================== UTILITY FUNCTIONS ====================

def normalize_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def normalize_skill(skill):
    text = normalize_text(skill)
    if not text:
        return ""
    for canonical, aliases in SKILL_ALIASES.items():
        if text in aliases:
            return canonical
    return text

def extract_user_skills(text):
    skills = []
    if not text:
        return skills
    for raw in re.split(r"[,;\n]+", text):
        skill = normalize_skill(raw.strip())
        if skill and skill not in skills:
            skills.append(skill)
    return skills

def text_contains_skill(text, skill):
    aliases = SKILL_ALIASES.get(skill, [skill])
    for alias in aliases:
        alias_norm = normalize_text(alias)
        if re.search(r"\b" + re.escape(alias_norm) + r"\b", text):
            return True
    return False

def infer_categories(job_text):
    text = normalize_text(job_text)
    categories = []

    if any(term in text for term in ["ai", "artificial intelligence"]):
        categories.append("ai")
    if any(term in text for term in ["machine learning", "ml"]):
        categories.append("machine-learning")
    if any(term in text for term in ["data science", "data scientist", "ds"]):
        categories.append("data-science")
    if "python" in text:
        categories.append("python")
    if any(term in text for term in ["web development", "html", "css", "javascript", "react", "node js", "bootstrap"]):
        categories.append("web-development")
    if any(term in text for term in ["cyber security", "security"]):
        categories.append("cyber-security")
    if any(term in text for term in ["cloud computing", "aws", "azure", "cloud"]):
        categories.append("cloud-computing")
    return categories

def load_jobs_from_db():
    """Load all jobs from database"""
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
    """Import jobs from CSV to database (run once)"""
    if Job.query.count() > 0:
        print("✅ Jobs already in database!")
        return
    
    with JOBS_FILE.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    
    for row in rows:
        title = row["Job_Title"]
        description = row["Description"]
        categories = infer_categories(f"{title} {description}")
        
        job = Job(
            title=title,
            company=row["Company"],
            location=row["Location"],
            salary=row["Salary"],
            description=description,
            categories=categories
        )
        db.session.add(job)
    
    db.session.commit()
    print(f"✅ Imported {len(rows)} jobs to database!")

def score_job(job, user_skills, desired_role):
    job_text = normalize_text(f"{job['title']} {job['description']}")
    score = 0

    for skill in user_skills:
        if skill in SKILL_WEIGHTS and text_contains_skill(job_text, skill):
            score += SKILL_WEIGHTS[skill]

    role_norm = normalize_text(desired_role)
    title_norm = normalize_text(job["title"])

    if role_norm and role_norm in title_norm:
        score += 8
    elif role_norm:
        role_words = [word for word in role_norm.split() if len(word) > 2]
        if any(word in title_norm for word in role_words):
            score += 4

    if not user_skills:
        return 0

    max_possible = sum(SKILL_WEIGHTS.get(skill, 1) for skill in user_skills if skill in SKILL_WEIGHTS)
    if max_possible == 0:
        max_possible = 1

    percent = min(100, int(round((score / max_possible) * 100)))
    return percent

def build_summary(results, skills_entered):
    if not results:
        return None
    highest = max(results, key=lambda item: item["match_score"])
    return {
        "jobs_found": len(results),
        "highest_match": highest["match_score"],
        "recommended": highest["title"],
        "skills_entered": skills_entered,
    }

# ==================== AUTHENTICATION ROUTES ====================

@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        full_name = request.form.get("full_name", "").strip()
        
        # Validation
        if not all([username, email, password, full_name]):
            flash("❌ All fields are required!", "danger")
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash("❌ Passwords do not match!", "danger")
            return redirect(url_for('register'))
        
        if len(password) < 6:
            flash("❌ Password must be at least 6 characters!", "danger")
            return redirect(url_for('register'))
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            flash("❌ Username already exists!", "danger")
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash("❌ Email already registered!", "danger")
            return redirect(url_for('register'))
        
        # Create user
        user = User(username=username, email=email, full_name=full_name)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash("✅ Account created successfully! Please login.", "success")
        return redirect(url_for('login'))
    
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash(f"✅ Welcome back, {user.full_name}!", "success")
            return redirect(url_for('index'))
        else:
            flash("❌ Invalid username or password!", "danger")
    
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    """User logout"""
    logout_user()
    flash("✅ You have been logged out!", "success")
    return redirect(url_for('index'))

@app.route("/profile")
@login_required
def profile():
    """User profile page"""
    return render_template(
        "profile.html",
        user=current_user,
        filter_labels=FILTER_LABELS
    )

@app.route("/profile/update", methods=["POST"])
@login_required
def update_profile():
    """Update user profile"""
    current_user.full_name = request.form.get("full_name", "").strip()
    current_user.phone = request.form.get("phone", "").strip()
    current_user.desired_role = request.form.get("desired_role", "").strip()
    
    skills_text = request.form.get("skills", "").strip()
    current_user.skills = extract_user_skills(skills_text)
    
    db.session.commit()
    
    flash("✅ Profile updated successfully!", "success")
    return redirect(url_for('profile'))

# ==================== JOB ROUTES ====================

@app.route("/")
def index():
    jobs = load_jobs_from_db()
    return render_template(
        "index.html",
        jobs=jobs,
        summary=None,
        filter_labels=FILTER_LABELS,
    )

@app.route("/match", methods=["GET", "POST"])
def match_jobs():
    if request.method == "GET":
        jobs = load_jobs_from_db()
        return render_template(
            "index.html",
            jobs=jobs,
            summary=None,
            filter_labels=FILTER_LABELS,
        )

    desired_role = request.form.get("role", "").strip()
    skills_text = request.form.get("skills", "").strip()

    raw_skills = extract_user_skills(skills_text)
    role_skills = extract_user_skills(desired_role)

    user_skills = []
    for skill in raw_skills + role_skills:
        if skill and skill not in user_skills:
            user_skills.append(skill)

    jobs = load_jobs_from_db()
    results = []

    for job in jobs:
        score = score_job(job, user_skills, desired_role)
        if user_skills:
            if score > 0:
                results.append({**job, "match_score": score})
        else:
            results.append({**job, "match_score": 0})

    results = sorted(results, key=lambda item: item["match_score"], reverse=True)[:8]
    summary = build_summary(results, len(user_skills))

    return render_template(
        "index.html",
        jobs=results,
        summary=summary,
        filter_labels=FILTER_LABELS,
    )
# ...existing code...

# ==================== SAVED JOBS ROUTES ====================

@app.route("/save-job/<int:job_id>", methods=["POST"])
@login_required
def save_job(job_id):
    """Save or unsave a job"""
    job = Job.query.get(job_id)
    
    if not job:
        return {"status": "error", "message": "Job not found"}, 404
    
    # Check if already saved
    saved = SavedJob.query.filter_by(user_id=current_user.id, job_id=job_id).first()
    
    if saved:
        # Remove from saved
        db.session.delete(saved)
        db.session.commit()
        return {"status": "removed"}
    else:
        # Add to saved
        new_saved = SavedJob(user_id=current_user.id, job_id=job_id)
        db.session.add(new_saved)
        db.session.commit()
        return {"status": "saved"}

@app.route("/saved-jobs")
@login_required
def saved_jobs():
    """View all saved jobs"""
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
            "match_score": None,
            "saved_at": saved_job.saved_at
        })
    
    return render_template(
        "saved_jobs.html",
        jobs=jobs,
        filter_labels=FILTER_LABELS
    )
# ...existing SavedJob model...

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
    status = db.Column(db.String(20), default='pending')  # pending, reviewed, rejected, accepted
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='applications')
    job = db.relationship('Job', backref='applications')
    
    def __repr__(self):
        return f'<Application {self.user_id}-{self.job_id}>'

# ...rest of your code...

# ...rest of code...
# ...existing code...

# ==================== APPLICATION TRACKING ROUTES ====================

@app.route("/apply", methods=["POST"])
@login_required
def apply_job():
    """Submit job application"""
    job_id = request.form.get("job_id")
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    cover_letter = request.form.get("cover_letter", "").strip()
    
    # Validation
    if not all([job_id, full_name, email, phone]):
        return {"status": "error", "message": "Missing required fields"}, 400
    
    job = Job.query.get(job_id)
    if not job:
        return {"status": "error", "message": "Job not found"}, 404
    
    # Check if already applied
    existing = Application.query.filter_by(
        user_id=current_user.id,
        job_id=job_id
    ).first()
    
    if existing:
        return {"status": "error", "message": "You already applied for this job"}, 400
    
    # Handle resume file
    resume_filename = None
    if 'resume' in request.files:
        file = request.files['resume']
        if file and file.filename:
            # Save file
            filename = f"{current_user.id}_{job_id}_{datetime.utcnow().timestamp()}.pdf"
            filepath = os.path.join(app.config.get('UPLOAD_FOLDER', 'uploads'), filename)
            os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads'), exist_ok=True)
            file.save(filepath)
            resume_filename = filename
    
    # Create application
    application = Application(
        user_id=current_user.id,
        job_id=job_id,
        full_name=full_name,
        email=email,
        phone=phone,
        resume_filename=resume_filename,
        cover_letter=cover_letter,
        status='pending'
    )
    
    db.session.add(application)
    db.session.commit()
    
    return {"status": "success", "message": "Application submitted successfully!"}

@app.route("/my-applications")
@login_required
def my_applications():
    """View user's applications"""
    applications = Application.query.filter_by(user_id=current_user.id).all()
    
    apps = []
    for app in applications:
        job = app.job
        apps.append({
            "id": app.id,
            "job_title": job.title,
            "company": job.company,
            "location": job.location,
            "salary": job.salary,
            "status": app.status,
            "applied_at": app.applied_at,
            "updated_at": app.updated_at,
            "full_name": app.full_name,
            "email": app.email,
            "phone": app.phone,
            "cover_letter": app.cover_letter
        })
    
    return render_template("my_applications.html", applications=apps)

@app.route("/application/<int:app_id>/cancel", methods=["POST"])
@login_required
def cancel_application(app_id):
    """Cancel an application"""
    application = Application.query.get(app_id)
    
    if not application:
        return {"status": "error", "message": "Application not found"}, 404
    
    if application.user_id != current_user.id:
        return {"status": "error", "message": "Unauthorized"}, 403
    
    db.session.delete(application)
    db.session.commit()
    
    return {"status": "success", "message": "Application cancelled"}

@app.route("/applications-stats")
@login_required
def applications_stats():
    """Get application statistics"""
    total = Application.query.filter_by(user_id=current_user.id).count()
    pending = Application.query.filter_by(user_id=current_user.id, status='pending').count()
    reviewed = Application.query.filter_by(user_id=current_user.id, status='reviewed').count()
    accepted = Application.query.filter_by(user_id=current_user.id, status='accepted').count()
    rejected = Application.query.filter_by(user_id=current_user.id, status='rejected').count()
    
    return {
        "total": total,
        "pending": pending,
        "reviewed": reviewed,
        "accepted": accepted,
        "rejected": rejected
    }

# ...rest of your code...

# ==================== MAIN ====================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        import_jobs_from_csv()
    
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)