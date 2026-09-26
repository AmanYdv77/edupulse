# EduPulse Design Notes & Technical Decisions

## 1. Problem & Users
Most college systems record student marks only after semester exams are finished, when it is too late to help anyone who failed. I built EduPulse to spot academic risks 4 to 6 weeks before final exams so teachers and students can step in early.

The users are:
1. **Students:** Track study/sleep habits, view predicted scores, and see what to improve.
2. **Teachers:** Monitor class performance and see which students are at risk of failing.
3. **HODs & Deans:** Check department and school-level academic trends.
4. **University Executives:** View high-level university statistics with zero student names or personal details.

---

## 2. Architecture in One Paragraph
EduPulse is built with a **Django 6 REST API** and a **React 19 + TypeScript SPA** served from the same origin using secure session cookies. It uses **PostgreSQL 16** for data, **two separate Redis instances** (one for caching analytics, one as a Celery task queue for prediction snapshots), and a separate Python ML package (`edupulse_ml`) with a strict feature contract and model registry.

---

## 3. Key Design Decisions

### Decision 1: PostgreSQL Everywhere with Four Isolated Databases
* **Choice:** Use PostgreSQL for development, testing, end-to-end tests, and production (`edupulse_dev`, `edupulse_test`, `edupulse_e2e`, and production).
* **Alternatives Considered:** SQLite for dev/test and PostgreSQL for production.
* **Why I chose this:** SQLite hides bugs that appear in PostgreSQL (like JSON queries, date math, and locking). Using PostgreSQL everywhere ensures that what passes in tests will work in production. Name guards prevent tests or scripts from touching the wrong database.
* **Trade-off:** Running local tests requires Docker or a local PostgreSQL service.

### Decision 2: Two Models (Baseline Model A vs. Institutional Model B)
* **Choice:** Start with a baseline model (Model A) trained on public Kaggle data, and design an institutional model (Model B) for when real data is available.
* **Alternatives Considered:** Training one model on fake dummy data and using it for everything.
* **Why I chose this:** Public datasets don't reflect real college exams. Having two separate models makes it clear where the numbers come from, and Model B must pass a promotion check before going live.
* **Trade-off:** Requires maintaining two training pipelines and clear source labels in the UI.

### Decision 3: Ridge Regression Instead of Complex Black-Box Models
* **Choice:** Ridge linear regression with L2 regularization.
* **Alternatives Considered:** Deep Neural Networks or large Random Forests.
* **Why I chose this:** In my experiments, Ridge scored $R^2 \approx 0.73$, outperforming Random Forest ($R^2 \approx 0.64$). Ridge is fast, doesn't overfit easily, and gives clear linear coefficients so we can explain predictions to students in plain English.
* **Trade-off:** Assumes mostly linear relationships between study hours, attendance, and exam scores.

### Decision 4: Grouped Temporal Cross-Validation
* **Choice:** Use `GroupedKFold` grouped by `student_id` and hold out the latest semester as the test set.
* **Alternatives Considered:** Standard random 80/20 train-test split.
* **Why I chose this:** A random split puts rows from the same student in both training and test sets, causing data leakage and fake high accuracy. Grouping by student and holding out the latest semester tests real-world generalization.
* **Trade-off:** Requires multiple semesters of records to train properly.

### Decision 5: Banning Demographic Attributes from ML Inputs
* **Choice:** Strictly ban gender, caste category, disability status, family income, and home state from model inputs.
* **Alternatives Considered:** Feeding all available demographic columns into the model.
* **Why I chose this:** Predictions should be based solely on academic effort (study hours, sleep consistency, internal marks, attendance). Using demographic inputs creates biased predictions that unfairly penalize groups.
* **Trade-off:** Demographic data is only used in a separate fairness audit to check for disparate impact.

### Decision 6: Storing Habit Logs & Prediction Snapshots
* **Choice:** Keep daily/weekly habit logs in their own table and save prediction snapshots periodically.
* **Alternatives Considered:** Overwriting the official semester marks table with habit estimates.
* **Why I chose this:** Official university exam marks must remain immutable. Habit logs and predictions should be audit trails that don't tamper with official academic history.
* **Trade-off:** Uses a bit more database storage for snapshot tables.

### Decision 7: React SPA on Same-Origin with Session Cookies
* **Choice:** React 19 + TypeScript frontend built and served by Django/WhiteNoise with `HttpOnly` session cookies.
* **Alternatives Considered:** Separate frontend domain with JWT tokens in `localStorage`.
* **Why I chose this:** JWTs in `localStorage` are vulnerable to XSS token theft. Same-origin session cookies eliminate CORS configuration issues and keep authentication secure.
* **Trade-off:** The frontend build step is integrated into Django's static collection pipeline.

### Decision 8: Server-Derived Scope & Executive Aggregation
* **Choice:** The backend calculates the user's role scope (`scope_for(user)`); executive accounts only see aggregated averages.
* **Alternatives Considered:** Letting the client send department filters in the request.
* **Why I chose this:** Clients can be manipulated. Deriving scopes on the server guarantees that teachers only see their assigned classes and leadership cannot browse individual student profiles.
* **Trade-off:** Every API endpoint must pass through a scoping layer.

### Decision 9: Two Separate Redis Instances
* **Choice:** One Redis instance for caching (`allkeys-lru` eviction) and one for Celery message queues (`noeviction` + append-only persistence).
* **Alternatives Considered:** A single Redis instance with multiple databases.
* **Why I chose this:** If the cache gets full, it should drop old analytics aggregates without deleting pending Celery tasks. Keeping them separate protects queued background jobs.
* **Trade-off:** Running two lightweight containers instead of one.

---

## 4. Known Limitations
1. **Model A relies on synthetic Kaggle data:** It demonstrates that the pipeline works, but its predictions are only rough priors until Model B is trained on real institutional data.
2. **Correlation vs. Causation:** High study hours correlate with higher grades, but increasing logged hours does not guarantee a passing grade. Predictions are advisory only.
3. **No real-time data drift monitoring yet:** If curriculum difficulty changes drastically, models must be retrained manually.
4. **Single-institute scoping:** Built for one university structure at a time.

---

## 5. What I Would Do Next
1. Add automated model drift detection that alerts admins when prediction error increases over consecutive semesters.
2. Integrate LMS (Canvas / Moodle) webhooks for automatic attendance and assignment score syncing.
3. Add multi-institution tenancy support.

---

## 6. How I Used AI in this Project
I used AI as a coding assistant to help speed up writing boilerplate code, scaffolding tests, and building components. I personally guided the architecture, verified every file change, wrote the core design decisions, and ensured all 220+ tests pass cleanly.
