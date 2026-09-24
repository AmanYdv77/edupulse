import ast
from pathlib import Path
import pytest
from django.conf import settings
from django.test import Client
from tests.factories import make_university


class TestMLFeatureContract:
    """Verifies that the ML feature contract strictly enforces banned protected attributes."""

    def test_contract_contains_no_protected_or_unapproved_attributes(self):
        """FEATURES dict in edupulse_ml.contract must not contain any protected or unapproved attributes."""
        from edupulse_ml.contract import FEATURES, PROTECTED_ATTRIBUTES, REVIEW_REQUIRED

        # Zero overlap with protected attributes
        overlap_protected = set(FEATURES.keys()) & PROTECTED_ATTRIBUTES
        assert not overlap_protected, f"Protected attributes found in contract FEATURES: {overlap_protected}"

        # Zero overlap with review-required attributes (since none are approved in docs/ML_CONTRACT.md)
        overlap_review = set(FEATURES.keys()) & REVIEW_REQUIRED
        assert not overlap_review, f"Review-required attributes found in contract FEATURES: {overlap_review}"

    def test_validate_feature_list_bans_protected_attributes(self):
        """validate_feature_list must raise ValueError for protected attributes."""
        from edupulse_ml.contract import validate_feature_list

        for protected in ["gender", "category", "address_state", "learning_disabilities"]:
            with pytest.raises(ValueError, match="protected attribute"):
                validate_feature_list([protected])

    def test_validate_feature_list_bans_unapproved_review_attributes(self):
        """validate_feature_list must raise ValueError for review-required attributes."""
        from edupulse_ml.contract import validate_feature_list

        for attr in ["family_income", "parental_education_level", "distance_from_home", "internet_access", "access_to_resources"]:
            with pytest.raises(ValueError, match="not approved"):
                validate_feature_list([attr])

    def test_validate_feature_list_bans_unknown_attributes(self):
        """validate_feature_list must raise ValueError for unknown attributes."""
        from edupulse_ml.contract import validate_feature_list

        with pytest.raises(ValueError, match="Unknown feature"):
            validate_feature_list(["random_unknown_feature"])

    def test_validate_feature_list_enforces_model_kind(self):
        """validate_feature_list must enforce model slot allowances (baseline vs institute)."""
        from edupulse_ml.contract import validate_feature_list

        # internal_assessment_score is institute-only
        with pytest.raises(ValueError, match="not permitted for model kind 'baseline'"):
            validate_feature_list(["internal_assessment_score"], model_kind="baseline")

        # But valid for institute
        assert validate_feature_list(["internal_assessment_score"], model_kind="institute") is True

    def test_validate_row_range_and_types(self):
        """validate_row checks data types and valid boundaries without fabricating defaults."""
        from edupulse_ml.contract import validate_row

        valid_row = {
            "attendance_percentage": 85.0,
            "hours_studied": 15.0,
            "sleep_hours": 7.5,
            "previous_score": 78.0,
            "tutoring_sessions": 2,
            "physical_activity": 4.0,
        }
        assert validate_row(valid_row) == []

        # Out-of-bounds attendance
        problems = validate_row({"attendance_percentage": 105.0})
        assert any("attendance_percentage" in p and "between" in p for p in problems)

        problems_neg = validate_row({"attendance_percentage": -5.0})
        assert any("attendance_percentage" in p for p in problems_neg)

        # Out-of-bounds sleep
        problems_sleep = validate_row({"sleep_hours": 26.0})
        assert any("sleep_hours" in p for p in problems_sleep)

        # Invalid type
        problems_type = validate_row({"tutoring_sessions": "two"})
        assert any("tutoring_sessions" in p and "type" in p for p in problems_type)

    def test_codebase_scanner_bans_protected_attributes_in_feature_lists(self):
        """
        Scans all Python files under app/ and fails if 'gender', 'category',
        or 'address_state' appear inside any list assigned to a variable whose
        name contains 'feature' or 'columns'.
        """
        banned_strings = {"gender", "category", "address_state", "learning_disabilities"}
        app_dir = Path(settings.BASE_DIR)

        violations = []

        for py_file in app_dir.rglob("*.py"):
            # Skip migrations, virtualenv, and test files
            if "migrations" in py_file.parts or ".venv" in py_file.parts or "tests" in py_file.parts:
                continue

            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except Exception:
                continue

            for node in ast.walk(tree):
                # Look for Assign or AnnAssign: x = [...] or x: list = [...]
                target_names = []
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            target_names.append(target.id)
                elif isinstance(node, ast.AnnAssign):
                    if isinstance(node.target, ast.Name):
                        target_names.append(node.target.id)

                for name in target_names:
                    lower_name = name.lower()
                    if "feature" in lower_name or "column" in lower_name or "input" in lower_name:
                        # Inspect the value being assigned
                        val_node = node.value if hasattr(node, "value") else None
                        if isinstance(val_node, (ast.List, ast.Set, ast.Tuple)):
                            for elt in val_node.elts:
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                    if elt.value in banned_strings:
                                        violations.append(
                                            f"{py_file.name}:{node.lineno} variable '{name}' contains banned '{elt.value}'"
                                        )

        assert not violations, f"Protected attributes found in feature/column lists:\n" + "\n".join(violations)

    @pytest.mark.django_db
    def test_my_predictions_ui_shows_no_active_model(self, client: Client):
        """When accessing /my-predictions/, the UI clearly displays 'No active prediction model'."""
        uni = make_university(students_per_batch=1)
        student_user = uni["students"][0].user
        client.force_login(student_user)

        response = client.get("/my-predictions/")
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "No active prediction model" in content
