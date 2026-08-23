# 🎓 Student Performance Prediction & College Result Management Platform

Welcome to the **College Result Management + Prediction Platform**. This project is a relational database-backed web application and analytical sandbox that stores academic results, manages granular, role-based dashboards, and integrates machine learning to predict student performance.

---

## 📂 Project Structure

The project has been cleaned up and reorganized into the following folders:

```
Student_Performance_Prediction/
├── Readme.md                    # This file (Project overview & setup guide)
├── app/                         # Django web application
│   ├── academics/               # Academic models (University, Course, Result, etc.)
│   ├── accounts/                # Custom user models & role-based dashboard views
│   ├── resultplatform/          # Core Django configuration (settings, urls)
│   ├── templates/               # HTML template files
│   ├── db.sqlite3               # Active seeded database (sqlite)
│   ├── manage.py                # Django CLI manager
│   └── .gitignore               # Django gitignore file
├── ml/                          # Machine learning workspace
│   └── trainer.ipynb            # Jupyter notebook for model training & evaluation
├── docs/                        # Project guidelines, designs, and blueprints
│   ├── DATABASE_DESIGN.md       # Relational database schema reference
│   ├── DJANGO_CHEATSHEET.md     # Django cheatsheet helper
│   ├── DJANGO_GUIDE.html        # Learning Django guide
│   ├── LEARNING_GUIDE.html      # Main platform learning guide
│   └── RESULT_PLATFORM_BLUEPRINT.md # Platform roadmap and layers
├── scripts/                     # Seeding and data loading scripts
│   ├── import_university_data.py # Loads the complete 800-student raw dataset
│   ├── seed_academics.py        # Small-scale testing seeder
│   └── seed_sample_users.py     # Simple user account seeder
└── data/                        # Raw source database files
    └── university.db            # Raw database template representing 800 students
```

---

## 🚀 Getting Started

### 1. Prerequisites
Ensure you have Python 3.10+ installed.

### 2. Install Django
Open a terminal at the project root and install Django:
```bash
pip install django
```

### 3. Initialize & Seeding the Database
The active database (`app/db.sqlite3`) is already fully seeded. If you ever need to reset and re-import the database, follow these steps:

1. Navigate to the `app/` directory:
   ```bash
   cd app
   ```
2. Reset migrations and tables:
   ```bash
   python manage.py migrate
   ```
3. Run the import script from the Django shell:
   ```bash
   python manage.py shell -c "exec(open('../scripts/import_university_data.py').read())"
   ```
   *(This imports the complete 800-student database from `data/university.db` and takes just a few seconds.)*

### 4. Run the Dev Server
From the `app/` folder, start the development server:
```bash
python manage.py runserver
```
Open your browser and navigate to:
*   **Web App:** http://127.0.0.1:8000/
*   **Admin Panel:** http://127.0.0.1:8000/admin/

---

## 🔐 Credentials & Roles

All seeded accounts use the password: **`Pass@123`**

You can log in with different accounts to see the hierarchical data visibility in action:

| Username | Role | Scope / What they see |
|---|---|---|
| `admin` | System Administrator | Full access to `/admin` panel |
| `vc` | Vice Chancellor | All 800 students across the university |
| `dean_engg` | Dean of Engineering | Scoped to School of Engineering (~300 students) |
| `hod_cse` | Head of Computer Science | Scoped to CSE department (~150 students) |
| `cse_fac01` | CSE Teacher | Scoped only to students in classes they teach (~125) |
| `25-engg-cse-ug-001` | Student | Accesses only their own semester grade card |

---

## 📊 Roadmap Status

Refer to [RESULT_PLATFORM_BLUEPRINT.md](docs/RESULT_PLATFORM_BLUEPRINT.md) for full context.

- [x] **Layer 1: MVP Storage + Login + View** (Completed)
  - Custom User model with roles, full university schema, bulk seeder, and scoped pages.
- [ ] **Layer 2: Analytics & Dashboards** (In-Progress)
  - Replace placeholders (e.g., student SGPA trend charts, topper lists, department comparison tools).
- [ ] **Layer 3: Predictive ML Integration** (In-Progress)
  - Preprocessing and training pipelines are explored in [trainer.ipynb](ml/trainer.ipynb).
  - Next step: serialize the model and implement prediction endpoints inside the Django web app.
