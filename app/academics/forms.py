from django import forms
from .models import HabitCheckInLog, StudentHabitPreference

class HabitCheckInForm(forms.ModelForm):
    class Meta:
        model = HabitCheckInLog
        fields = [
            "log_type",
            "hours_studied",
            "sleep_hours",
            "motivation_level",
            "tutoring_sessions",
            "physical_activity",
            "notes",
        ]
        widgets = {
            "log_type": forms.Select(attrs={"class": "form-select", "id": "id_log_type"}),
            "hours_studied": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.5", "min": "0", "max": "100",
                "id": "id_hours_studied", "placeholder": "e.g. 4.5"
            }),
            "sleep_hours": forms.NumberInput(attrs={
                "class": "form-control", "step": "0.5", "min": "0", "max": "24",
                "id": "id_sleep_hours", "placeholder": "e.g. 7.5"
            }),
            "motivation_level": forms.Select(attrs={"class": "form-select", "id": "id_motivation_level"}),
            "tutoring_sessions": forms.NumberInput(attrs={
                "class": "form-control", "min": "0", "max": "20",
                "id": "id_tutoring_sessions", "placeholder": "0"
            }),
            "physical_activity": forms.NumberInput(attrs={
                "class": "form-control", "min": "0", "max": "30",
                "id": "id_physical_activity", "placeholder": "0"
            }),
            "notes": forms.TextInput(attrs={
                "class": "form-control", "placeholder": "Optional quick note on focus or challenges..."
            }),
        }


class HabitPreferenceForm(forms.ModelForm):
    class Meta:
        model = StudentHabitPreference
        fields = ["frequency"]
        widgets = {
            "frequency": forms.RadioSelect(attrs={"class": "form-check-input"}),
        }
