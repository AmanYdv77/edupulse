# Result Platform — Milestone 1 ✅

The foundation: a Django project with a **custom User model that has a `role`**,
the **admin panel** working, and **6 sample users** to log in with.

This is deliberately small. Dashboards, results, and predictions come later.

---

## What's inside (the files that matter)

```
app/
├── manage.py                      # your "remote control"
├── resultplatform/
│   ├── settings.py                # config — note AUTH_USER_MODEL + 'accounts'
│   └── urls.py                    # main URL map (admin only, for now)
├── accounts/
│   ├── models.py                  # ⭐ the custom User + Role choices
│   └── admin.py                   # registers User in the admin panel
└── seed_sample_users.py           # creates the 6 sample users
```

---

## How to run it on YOUR laptop (VS Code)

1. **Install Python** (3.10+), then in a terminal:
   ```bash
   pip install django
   ```
2. **Open the `app/` folder in VS Code.**
3. **Set up the database** (creates the tables from our models):
   ```bash
   python manage.py migrate
   ```
4. **Create the sample users:**
   ```bash
   python manage.py shell < seed_sample_users.py
   ```
   (Or make your own admin: `python manage.py createsuperuser`)
5. **Run the server:**
   ```bash
   python manage.py runserver
   ```
6. **Open** http://127.0.0.1:8000/admin/ in your browser.

---

## Login details (sample data only)

All passwords: **`Pass@123`**

| Username | Role |
|---|---|
| `admin` | System Administrator (superuser — use this for /admin) |
| `vc` | Vice Chancellor |
| `dean_engg` | Dean |
| `hod_cse` | Head of Department |
| `teacher_cse` | Teacher |
| `student_cs` | Student |

> ⚠️ Only `admin` can open the admin panel right now (it's the superuser).
> The others exist in the database with their roles — we'll build their
> dashboards in later milestones.

---

## What to look at / try

- Log into `/admin/` as `admin`.
- Click **Users** → you'll see all 6, each with a **Role** column.
- Open a user → scroll down → see the **"Result Platform info"** section with
  `role` and `phone`. That `role` is the seed of the whole hierarchy.

---

## ✅ Milestone 1 checklist (all done)

- [x] Django project + `accounts` app created
- [x] Custom `User` model with a `role` field (set before first migrate)
- [x] `AUTH_USER_MODEL` configured in settings
- [x] Admin panel shows & filters by role
- [x] 6 sample users seeded
- [x] Server boots; `/admin/` works

## ▶️ Next milestone (when you're ready)
**Milestone 2:** a simple login page + a "home" page that greets you by name and
shows your role — your first NON-admin page, and the first taste of Views +
Templates + the hierarchy.
