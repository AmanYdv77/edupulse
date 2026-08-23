import os
import pickle
import pandas as pd
from django.conf import settings
from academics.models import Subject, SemesterResult

# Load the trained ML model pipeline
MODEL_PATH = os.path.join(settings.BASE_DIR, '..', 'ml', 'student_predictor.pkl')
_model = None

def get_model():
    global _model
    if _model is None:
        if os.path.exists(MODEL_PATH):
            with open(MODEL_PATH, 'rb') as f:
                _model = pickle.load(f)
        else:
            print(f"Warning: ML model not found at {MODEL_PATH}")
    return _model

def predict_current_subjects(student):
    """
    Predicts the expected exam score percentage for all subjects
    in the student's current active semester.
    """
    model = get_model()
    if not model:
        return []
        
    # 1. Fetch current subjects
    current_subjects = Subject.objects.filter(
        course=student.course,
        semester=student.current_semester
    )
    if not current_subjects.exists():
        return []
        
    # 2. Get behavioral metrics (try current sem, default to latest past sem, or fallback to baselines)
    sem_res = SemesterResult.objects.filter(
        student=student, 
        semester=student.current_semester
    ).first()
    
    if not sem_res:
        # Fallback to the latest available semester behavior
        sem_res = SemesterResult.objects.filter(student=student).order_by('-semester').first()
        
    # Define fallback defaults if no record exists
    attendance = sem_res.attendance_percentage if sem_res else 85.0
    hours_studied = sem_res.hours_studied_per_week if sem_res else 15.0
    sleep = sem_res.sleep_hours_per_night if sem_res else 7.0
    motivation = sem_res.motivation_level if sem_res else 'Medium'
    tutoring = sem_res.tutoring_sessions if sem_res else 1
    extracurricular = sem_res.extracurricular_activities if sem_res else False
    physical = sem_res.physical_activity if sem_res else 3
    parental = sem_res.parental_involvement if sem_res else 'Medium'
    peer = sem_res.peer_influence if sem_res else 'Neutral'
    
    predictions = []
    user = student.user
    
    for subject in current_subjects:
        # Construct single-row DataFrame matching the model's feature names
        input_data = pd.DataFrame([{
            'distance_from_home': student.distance_from_home or 'Near',
            'parental_education_level': student.parental_education_level or 'College',
            'family_income': student.family_income or 'Medium',
            'internet_access': int(student.internet_access),
            'access_to_resources': student.access_to_resources or 'Medium',
            'learning_disabilities': int(student.learning_disabilities),
            
            'gender': user.gender or 'Male',
            'category': user.category or 'General',
            'address_state': user.address_state or 'Delhi',
            
            'subject_credits': subject.credits,
            'subject_type': subject.subject_type,
            
            'attendance_percentage': attendance,
            'hours_studied_per_week': hours_studied,
            'sleep_hours_per_night': sleep,
            'motivation_level': motivation,
            'tutoring_sessions': tutoring,
            'extracurricular_activities': int(extracurricular),
            'physical_activity': physical,
            'parental_involvement': parental,
            'peer_influence': peer
        }])
        
        # Predict
        predicted_pct = model.predict(input_data)[0]
        predicted_pct = max(0, min(100, predicted_pct)) # bound between 0 and 100
        
        # Map percentage to expected letter grade & status
        if predicted_pct >= 90:
            letter_grade = 'O'
        elif predicted_pct >= 80:
            letter_grade = 'A+'
        elif predicted_pct >= 70:
            letter_grade = 'A'
        elif predicted_pct >= 60:
            letter_grade = 'B+'
        elif predicted_pct >= 50:
            letter_grade = 'B'
        else:
            letter_grade = 'F'
            
        status = 'PASS' if predicted_pct >= 50 else 'FAIL'
        
        predictions.append({
            'subject_code': subject.code,
            'subject_title': subject.title,
            'subject_credits': subject.credits,
            'predicted_percentage': round(predicted_pct, 1),
            'expected_grade': letter_grade,
            'status': status,
            'is_at_risk': predicted_pct < 50
        })
        
    return predictions
