# ==============================
# AI Job Matching Engine
# Clean Flask Backend
# PART 1/3
# ==============================

import os
import csv
import re
import tempfile
from pathlib import Path
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify
)

from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# ==============================
# PATH CONFIGURATION
# ==============================

BASE_DIR = Path(
    os.getcwd()
)

TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


# ==============================
# FLASK INITIALIZATION
# ==============================

app = Flask(
    __name__,
    template_folder=str(TEMPLATE_DIR),
    static_folder=str(STATIC_DIR)
)


# ==============================
# DATABASE CONFIGURATION
# ==============================

database_url = os.environ.get("DATABASE_URL")


if database_url:
    # Render PostgreSQL fix
    database_url = database_url.replace(
        "postgres://",
        "postgresql://"
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url

else:
    # Local / Vercel fallback
    db_file = os.path.join(
        tempfile.gettempdir(),
        "jobs.db"
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"sqlite:///{db_file}"
    )


app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "development-secret-key"
)


# Upload folder

UPLOAD_FOLDER = os.path.join(
    tempfile.gettempdir(),
    "uploads"
)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER



# Database

db = SQLAlchemy(app)



# Login manager

login_manager = LoginManager()

login_manager.init_app(app)

login_manager.login_view = "login"



# ==============================
# DATABASE MODELS
# ==============================


class User(
    UserMixin,
    db.Model
):

    __tablename__ = "users"


    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )


    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )


    password = db.Column(
        db.String(255),
        nullable=False
    )


    full_name = db.Column(
        db.String(150)
    )


    phone = db.Column(
        db.String(20)
    )


    desired_role = db.Column(
        db.String(100)
    )


    skills = db.Column(
        db.JSON,
        default=[]
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


    def set_password(self, password):

        self.password = generate_password_hash(
            password
        )


    def check_password(self, password):

        return check_password_hash(
            self.password,
            password
        )


    def __repr__(self):

        return self.username





class Job(db.Model):

    __tablename__ = "jobs"


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    title = db.Column(
        db.String(200),
        nullable=False
    )


    company = db.Column(
        db.String(200)
    )


    location = db.Column(
        db.String(200)
    )


    salary = db.Column(
        db.String(100)
    )


    description = db.Column(
        db.Text,
        nullable=False
    )


    categories = db.Column(
        db.JSON
    )


    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


    def __repr__(self):

        return self.title





class SavedJob(db.Model):

    __tablename__ = "saved_jobs"


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id")
    )


    job_id = db.Column(
        db.Integer,
        db.ForeignKey("jobs.id")
    )


    saved_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


    user = db.relationship(
        "User",
        backref="saved_jobs"
    )


    job = db.relationship(
        "Job",
        backref="saved_by_users"
    )





class Application(db.Model):

    __tablename__ = "applications"


    id = db.Column(
        db.Integer,
        primary_key=True
    )


    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )


    job_id = db.Column(
        db.Integer,
        db.ForeignKey("jobs.id"),
        nullable=False
    )


    full_name = db.Column(
        db.String(150)
    )


    email = db.Column(
        db.String(120)
    )


    phone = db.Column(
        db.String(20)
    )


    resume_filename = db.Column(
        db.String(255)
    )


    cover_letter = db.Column(
        db.Text
    )


    status = db.Column(
        db.String(50),
        default="pending"
    )


    applied_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


    user = db.relationship(
        "User",
        backref="applications"
    )


    job = db.relationship(
        "Job",
        backref="applications"
    )


    def __repr__(self):

        return f"Application {self.id}"



# ==============================
# LOGIN USER LOADER
# ==============================


@login_manager.user_loader
def load_user(user_id):

    return User.query.get(
        int(user_id)
    )
# ==============================
# PART 2/3
# AI MATCHING ENGINE + AUTH
# ==============================


# ==============================
# JOB CSV LOCATION
# ==============================

JOBS_FILE = (
    BASE_DIR /
    "jobs.csv"
)



# ==============================
# SKILL WEIGHTS
# ==============================

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

    "html": 1,
    "css": 1,
    "javascript": 2,

    "react": 2,
    "node.js": 2,

    "flask": 1.5,
    "django": 1.5,

    "mongodb": 1.5,

    "java": 1.5,

    "git": 1,

    "data structures": 1,

    "power bi": 1.5,

    "cyber security": 3,

    "cloud computing": 3

}




# ==============================
# SKILL ALIASES
# ==============================


SKILL_ALIASES = {


    "python":
    [
        "python",
        "py"
    ],


    "machine learning":
    [
        "machine learning",
        "ml"
    ],


    "artificial intelligence":
    [
        "artificial intelligence",
        "ai"
    ],


    "deep learning":
    [
        "deep learning",
        "dl"
    ],


    "data science":
    [
        "data science",
        "ds"
    ],


    "natural language processing":
    [
        "natural language processing",
        "nlp"
    ],


    "computer vision":
    [
        "computer vision",
        "cv"
    ],


    "javascript":
    [
        "javascript",
        "js"
    ],


    "node.js":
    [
        "node",
        "node js",
        "node.js"
    ],


    "power bi":
    [
        "power bi",
        "powerbi"
    ]

}





# ==============================
# TEXT UTILITIES
# ==============================


def normalize_text(text):

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9 ]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()





def normalize_skill(skill):

    skill = normalize_text(skill)


    for main, aliases in SKILL_ALIASES.items():

        if skill in aliases:

            return main


    return skill





def extract_user_skills(text):

    skills = []


    if not text:
        return skills


    parts = re.split(
        r"[,;\n]+",
        text
    )


    for item in parts:

        skill = normalize_skill(item)


        if skill and skill not in skills:

            skills.append(skill)


    return skills





def text_contains_skill(text, skill):

    aliases = SKILL_ALIASES.get(
        skill,
        [skill]
    )


    for alias in aliases:

        if normalize_text(alias) in text:

            return True


    return False





# ==============================
# JOB CATEGORY DETECTION
# ==============================


def infer_categories(text):

    text = normalize_text(text)

    categories = []


    if "ai" in text or "artificial intelligence" in text:
        categories.append("ai")


    if "machine learning" in text:
        categories.append(
            "machine-learning"
        )


    if "data science" in text:
        categories.append(
            "data-science"
        )


    if "python" in text:
        categories.append(
            "python"
        )


    if any(
        x in text
        for x in
        [
            "html",
            "css",
            "javascript",
            "react",
            "node"
        ]
    ):

        categories.append(
            "web-development"
        )


    return categories





# ==============================
# IMPORT JOBS FROM CSV
# ==============================


def import_jobs_from_csv():


    if Job.query.count() > 0:

        return


    if not JOBS_FILE.exists():

        print(
            "jobs.csv not found"
        )

        return



    with open(
        JOBS_FILE,
        encoding="utf-8"
    ) as file:


        reader = csv.DictReader(file)


        count = 0


        for row in reader:


            job = Job(

                title=row.get(
                    "Job_Title",
                    "Unknown"
                ),


                company=row.get(
                    "Company",
                    "Unknown"
                ),


                location=row.get(
                    "Location",
                    "Remote"
                ),


                salary=row.get(
                    "Salary",
                    "Not specified"
                ),


                description=row.get(
                    "Description",
                    ""
                ),


                categories=infer_categories(

                    row.get(
                        "Job_Title",
                        ""
                    )
                    +
                    " "
                    +
                    row.get(
                        "Description",
                        ""
                    )

                )

            )


            db.session.add(job)

            count += 1



        db.session.commit()


        print(
            f"{count} jobs imported"
        )





# ==============================
# LOAD JOB DATA
# ==============================


def load_jobs():


    jobs = Job.query.all()


    data = []


    for job in jobs:


        data.append({

            "id": job.id,

            "title": job.title,

            "company": job.company,

            "location": job.location,

            "salary": job.salary,

            "description": job.description,

            "categories": job.categories or []

        })


    return data





# ==============================
# AI MATCH SCORE
# ==============================


def score_job(job, skills, role):


    text = normalize_text(

        job["title"]
        +
        " "
        +
        job["description"]

    )


    score = 0



    for skill in skills:


        if skill in SKILL_WEIGHTS:


            if text_contains_skill(
                text,
                skill
            ):

                score += SKILL_WEIGHTS[skill]



    if role:


        role = normalize_text(role)


        if role in normalize_text(job["title"]):

            score += 8




    maximum = sum(

        SKILL_WEIGHTS.get(
            s,
            1
        )

        for s in skills

    )


    if maximum == 0:

        return 0



    return min(

        100,

        int(
            (score / maximum)
            *
            100
        )

    )





# ==============================
# AUTH ROUTES
# ==============================



@app.route(
    "/register",
    methods=["GET","POST"]
)

def register():


    if request.method == "POST":


        username = request.form.get(
            "username"
        )


        email = request.form.get(
            "email"
        )


        password = request.form.get(
            "password"
        )


        full_name = request.form.get(
            "full_name"
        )


        if User.query.filter_by(
            username=username
        ).first():

            flash(
                "Username already exists"
            )

            return redirect(
                url_for("register")
            )


        user = User(

            username=username,

            email=email,

            full_name=full_name

        )


        user.set_password(
            password
        )


        db.session.add(user)

        db.session.commit()


        flash(
            "Registration successful"
        )


        return redirect(
            url_for("login")
        )


    return render_template(
        "register.html"
    )





@app.route(
    "/login",
    methods=["GET","POST"]
)

def login():


    if request.method=="POST":


        username=request.form.get(
            "username"
        )


        password=request.form.get(
            "password"
        )



        user=User.query.filter_by(
            username=username
        ).first()



        if user and user.check_password(
            password
        ):


            login_user(user)


            return redirect(
                url_for("index")
            )



        flash(
            "Invalid login"
        )


    return render_template(
        "login.html"
    )





@app.route("/logout")

@login_required

def logout():


    logout_user()


    return redirect(
        url_for("index")
    )





@app.route(
    "/profile/update",
    methods=["POST"]
)

@login_required

def update_profile():


    current_user.full_name = request.form.get(
        "full_name"
    )


    current_user.phone = request.form.get(
        "phone"
    )


    current_user.desired_role = request.form.get(
        "desired_role"
    )


    current_user.skills = extract_user_skills(

        request.form.get(
            "skills"
        )

    )


    db.session.commit()


    flash(
        "Profile updated"
    )


    return redirect(
        url_for("profile")
    )
# ==============================
# PART 3/3
# JOB ROUTES + APPLICATION SYSTEM
# ==============================



# ==============================
# HOME PAGE
# ==============================


@app.route("/")
def index():

    jobs = load_jobs()

    return render_template(
        "index.html",
        jobs=jobs,
        summary=None
    )




# ==============================
# PROFILE PAGE
# ==============================


@app.route("/profile")
@login_required
def profile():

    return render_template(
        "profile.html",
        user=current_user
    )





# ==============================
# AI JOB MATCHING ROUTE
# ==============================


@app.route(
    "/match",
    methods=["POST"]
)

def match_jobs():


    skills_text = request.form.get(
        "skills",
        ""
    )


    role = request.form.get(
        "role",
        ""
    )


    skills = extract_user_skills(
        skills_text
        +
        " "
        +
        role
    )


    jobs = load_jobs()


    results = []


    for job in jobs:


        score = score_job(
            job,
            skills,
            role
        )


        if score > 0:


            results.append({

                **job,

                "match_score": score

            })



    results = sorted(

        results,

        key=lambda x:x["match_score"],

        reverse=True

    )[:10]



    summary = {

        "jobs_found":len(results),

        "highest_match":

            results[0]["match_score"]

            if results

            else 0,


        "recommended":

            results[0]["title"]

            if results

            else "No match"

    }



    return render_template(

        "index.html",

        jobs=results,

        summary=summary

    )





# ==============================
# SAVE / UNSAVE JOB
# ==============================


@app.route(
    "/save-job/<int:job_id>",
    methods=["POST"]
)

@login_required

def save_job(job_id):


    existing = SavedJob.query.filter_by(

        user_id=current_user.id,

        job_id=job_id

    ).first()



    if existing:


        db.session.delete(existing)

        db.session.commit()


        return jsonify({

            "status":"removed"

        })



    saved = SavedJob(

        user_id=current_user.id,

        job_id=job_id

    )


    db.session.add(saved)

    db.session.commit()



    return jsonify({

        "status":"saved"

    })





# ==============================
# SAVED JOBS PAGE
# ==============================


@app.route("/saved-jobs")

@login_required

def saved_jobs():


    saved = SavedJob.query.filter_by(

        user_id=current_user.id

    ).all()



    jobs=[]



    for item in saved:


        job=item.job


        jobs.append({

            "id":job.id,

            "title":job.title,

            "company":job.company,

            "location":job.location,

            "salary":job.salary,

            "description":job.description

        })



    return render_template(

        "saved_jobs.html",

        jobs=jobs

    )





# ==============================
# APPLY JOB
# ==============================


@app.route(

    "/apply",

    methods=["POST"]

)

@login_required

def apply_job():



    job_id=request.form.get(
        "job_id"
    )



    existing=Application.query.filter_by(

        user_id=current_user.id,

        job_id=job_id

    ).first()



    if existing:


        return jsonify({

            "message":
            "Already applied"

        })



    resume=None



    if "resume" in request.files:


        file=request.files["resume"]


        if file.filename:


            filename=(

                str(current_user.id)

                +

                "_"

                +

                file.filename

            )


            path=os.path.join(

                app.config["UPLOAD_FOLDER"],

                filename

            )


            file.save(path)


            resume=filename




    application=Application(

        user_id=current_user.id,

        job_id=job_id,

        full_name=request.form.get(
            "full_name"
        ),


        email=request.form.get(
            "email"
        ),


        phone=request.form.get(
            "phone"
        ),


        cover_letter=request.form.get(
            "cover_letter"
        ),


        resume_filename=resume

    )



    db.session.add(application)

    db.session.commit()



    return jsonify({

        "message":
        "Application submitted"

    })





# ==============================
# MY APPLICATIONS
# ==============================


@app.route("/my-applications")

@login_required

def my_applications():


    applications = Application.query.filter_by(

        user_id=current_user.id

    ).all()



    data=[]



    for app_item in applications:


        data.append({

            "job":
            app_item.job.title,


            "company":
            app_item.job.company,


            "status":
            app_item.status,


            "date":
            app_item.applied_at

        })



    return render_template(

        "my_applications.html",

        applications=data

    )





# ==============================
# APPLICATION STATISTICS API
# ==============================


@app.route("/applications-stats")

@login_required

def application_stats():


    return jsonify({

        "total":

        Application.query.filter_by(

            user_id=current_user.id

        ).count(),



        "pending":

        Application.query.filter_by(

            user_id=current_user.id,

            status="pending"

        ).count()

    })





# ==============================
# DATABASE INITIALIZATION
# ==============================


def initialize_database():


    with app.app_context():


        db.create_all()


        import_jobs_from_csv()



try:

    initialize_database()


except Exception as e:


    print(
        "Database initialization error:",
        e
    )





# ==============================
# APPLICATION START
# ==============================
# Vercel requires exported Flask app
application = app

