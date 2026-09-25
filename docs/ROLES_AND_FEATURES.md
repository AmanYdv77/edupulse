# Roles and Features Contract

## 1. Principles
- **Least Privilege:** Each role receives the minimum data and capabilities necessary to perform its duties.
- **Server-Derived Scope:** The server derives scope from the authenticated user's profile and institutional assignments (`scope_for(user)`); the client never sends or dictates scope parameters.
- **Aggregates Only for Executives:** University leadership (Vice Chancellor, Registrar, Controller of Examinations) inspect macro institutional trends and cohort aggregates; they never receive individual student names, roll numbers, or personal telemetry.
- **Zero Third-Party Leaks:** No protected attributes, email addresses, phone numbers, or private student identifiers are exposed in public or cross-role responses.

---

## 2. Role Definition & Access Matrix

| Role | Operational Scope | Sees Student Names? | Core Screens & Capabilities | Granted Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| **Student** | Own record only | Own record only | Dashboard, personal results, daily/weekly habit check-in, personal predictions with honest model labels, top factors, and advisory disclaimer. | `view_own_results`<br>`view_own_predictions`<br>`submit_habit_checkin`<br>`view_own_habits` |
| **Teacher** | Assigned subjects & batches | Yes, for students in taught batches | Class analytics (pass rates, histograms, trends), internal marks entry, roster export (rate-limited and audited), teaching assignments. | `view_class_analytics`<br>`enter_internal_marks`<br>`export_class_roster`<br>`view_teaching_assignments` |
| **HOD** | Department | Yes, within department | Department analytics (courses, subjects, faculty), at-risk student roster, department export. | `view_department_analytics`<br>`view_at_risk_roster`<br>`export_department_roster` |
| **Dean** | School (multi-department) | Yes, within school | School analytics, cross-department comparison, at-risk student roster, school export. | `view_school_analytics`<br>`view_at_risk_roster`<br>`export_school_roster` |
| **VC / Registrar / Controller** | University-wide | **No** (Aggregates only) | Executive overview: institutional KPIs, school/department comparison, longitudinal trends. Drill-down restricted to aggregates ($\ge 10$ students). | `view_executive_analytics` |
| **System Admin** | System infrastructure | **No student analytics** | Model registry management (view versions, inspect metrics, activate candidate models), system health monitoring, Django admin access. | `manage_models`<br>`view_system_health`<br>`access_admin` |

---

## 3. Capability Names (Used in Code)
The following canonical capability string tokens are returned by `/api/v1/me/` and enforced by server permissions:
- `view_own_results`
- `view_own_predictions`
- `submit_habit_checkin`
- `view_own_habits`
- `view_teaching_assignments`
- `enter_internal_marks`
- `export_class_roster`
- `view_class_analytics`
- `view_department_analytics`
- `view_school_analytics`
- `view_executive_analytics`
- `view_at_risk_roster`
- `export_department_roster`
- `export_school_roster`
- `manage_models`
- `view_system_health`
- `access_admin`

---

## 4. Privacy & Governance Settings
- **Minimum Group Size (`ANALYTICS_MIN_GROUP_SIZE`):** `10`
  Any breakdown or cohort smaller than 10 students is masked and merged into `"Other (hidden)"` to prevent deanonymization via small sample sizes.
- **Roster Export Throttling:**
  Authorized faculty roles (Teacher, HOD, Dean) may export scoped rosters at a rate limit of **5 exports per hour per user**.
- **Audit Logging:**
  Every roster export writes an immutable audit record containing `user_id`, `scope_level`, `filters_applied`, `row_count`, and `timestamp`. Export audit logs are retained for **90 days**.

---

## 5. Edge Cases & Inactive Accounts
- **Multiple Assignments:** If a faculty member is both a Teacher and HOD, their HOD role encompasses their departmental scope while retaining teaching assignment marks entry.
- **Inactive / Unauthenticated Users:** Returns an empty capability list `[]` and immediately prompts authentication.
- **Protected Attributes:** Demographics (gender, category, disability status, family income) are strictly quarantined from all JSON API responses.

---

## 6. Document Governance
- **Author:** EduPulse Core Architecture Team
- **Status:** Approved
- **Effective Version:** API v1.0
