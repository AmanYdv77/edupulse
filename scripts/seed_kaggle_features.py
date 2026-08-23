import os
import sys
import random
import django

# Setup Django environment
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "resultplatform.settings")
django.setup()

from academics.models import StudentProfile, SemesterResult

def seed_student_profiles():
    print("Seeding Student Profiles with static Kaggle features...")
    profiles = StudentProfile.objects.all()
    count = 0
    for profile in profiles:
        # Distance from Home
        profile.distance_from_home = random.choices(["Near", "Moderate", "Far"], weights=[0.4, 0.4, 0.2])[0]
        # Parental Education
        profile.parental_education_level = random.choices(["High School", "College", "Postgraduate"], weights=[0.5, 0.3, 0.2])[0]
        # Family Income
        profile.family_income = random.choices(["Low", "Medium", "High"], weights=[0.3, 0.5, 0.2])[0]
        # Internet Access
        profile.internet_access = random.choices([True, False], weights=[0.9, 0.1])[0]
        # Access to Resources
        profile.access_to_resources = random.choices(["Low", "Medium", "High"], weights=[0.2, 0.5, 0.3])[0]
        # Learning Disabilities
        profile.learning_disabilities = random.choices([True, False], weights=[0.05, 0.95])[0]
        
        profile.save()
        count += 1
    
    print(f"Updated {count} Student Profiles.")

def seed_semester_results():
    print("Seeding Semester Results with dynamic behavioral features...")
    results = SemesterResult.objects.all()
    count = 0
    for result in results:
        # Use SGPA (if > 0) to subtly influence the random distribution to maintain correlations for the ML model
        base_factor = result.sgpa / 10.0 if result.sgpa > 0 else 0.7
        
        # Attendance Percentage (mostly high, correlated with SGPA)
        attendance = max(40, min(100, int(random.gauss(50 + (base_factor * 40), 10))))
        result.attendance_percentage = attendance
        
        # Hours Studied (correlated)
        hours = max(0, min(40, int(random.gauss(5 + (base_factor * 20), 5))))
        result.hours_studied_per_week = hours
        
        # Sleep Hours
        sleep = max(4, min(10, random.gauss(6.5 + (base_factor), 1.5)))
        result.sleep_hours_per_night = round(sleep, 1)
        
        # Motivation
        if base_factor > 0.8:
            mot_weights = [0.1, 0.3, 0.6]
        elif base_factor > 0.6:
            mot_weights = [0.2, 0.6, 0.2]
        else:
            mot_weights = [0.6, 0.3, 0.1]
        result.motivation_level = random.choices(["Low", "Medium", "High"], weights=mot_weights)[0]
        
        # Tutoring
        result.tutoring_sessions = random.randint(0, 5)
        
        # Extracurricular
        result.extracurricular_activities = random.choice([True, False])
        
        # Physical Activity
        result.physical_activity = random.randint(0, 7)
        
        # Parental Involvement
        result.parental_involvement = random.choices(["Low", "Medium", "High"], weights=[0.3, 0.4, 0.3])[0]
        
        # Peer Influence
        if base_factor > 0.7:
            peer_weights = [0.6, 0.3, 0.1]
        else:
            peer_weights = [0.2, 0.4, 0.4]
        result.peer_influence = random.choices(["Positive", "Neutral", "Negative"], weights=peer_weights)[0]
        
        result.save()
        count += 1
        
    print(f"Updated {count} Semester Results.")

if __name__ == "__main__":
    seed_student_profiles()
    seed_semester_results()
    print("Database successfully backfilled with Kaggle features!")
