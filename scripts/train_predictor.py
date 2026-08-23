import os
import sys
import pickle
import django
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score, mean_squared_error

# Setup Django environment
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "resultplatform.settings")
django.setup()

from academics.models import Result, SemesterResult

def train_model():
    print("Loading data from database...")
    results = Result.objects.select_related('student', 'student__user', 'subject').all()
    
    print("Loading semester behavioral metrics...")
    semester_results = {
        (sr.student_id, sr.semester): sr 
        for sr in SemesterResult.objects.all()
    }
    
    data = []
    for r in results:
        sem_res = semester_results.get((r.student_id, r.semester))
        if not sem_res or not r.max_marks:
            continue
            
        target = (r.total_secured / r.max_marks) * 100
        student = r.student
        user = student.user
        subject = r.subject
        
        data.append({
            # Target
            'percentage': target,
            
            # Static student profile features
            'distance_from_home': student.distance_from_home or 'Near',
            'parental_education_level': student.parental_education_level or 'College',
            'family_income': student.family_income or 'Medium',
            'internet_access': student.internet_access,
            'access_to_resources': student.access_to_resources or 'Medium',
            'learning_disabilities': student.learning_disabilities,
            
            # User demographics
            'gender': user.gender or 'Male',
            'category': user.category or 'General',
            'address_state': user.address_state or 'Delhi',
            
            # Subject details
            'subject_credits': subject.credits,
            'subject_type': subject.subject_type,
            
            # SemesterResult dynamic features
            'attendance_percentage': sem_res.attendance_percentage,
            'hours_studied_per_week': sem_res.hours_studied_per_week,
            'sleep_hours_per_night': sem_res.sleep_hours_per_night,
            'motivation_level': sem_res.motivation_level or 'Medium',
            'tutoring_sessions': sem_res.tutoring_sessions,
            'extracurricular_activities': sem_res.extracurricular_activities,
            'physical_activity': sem_res.physical_activity,
            'parental_involvement': sem_res.parental_involvement or 'Medium',
            'peer_influence': sem_res.peer_influence or 'Neutral',
        })
        
    df = pd.DataFrame(data)
    print(f"Loaded {len(df)} records for training.")
    
    # Features and Target
    X = df.drop(columns=['percentage'])
    y = df['percentage']
    
    # Categorical and Numeric Features
    categorical_cols = [
        'distance_from_home', 'parental_education_level', 'family_income',
        'access_to_resources', 'gender', 'category', 'address_state',
        'subject_type', 'motivation_level', 'parental_involvement', 'peer_influence'
    ]
    numeric_cols = [
        'subject_credits', 'attendance_percentage', 'hours_studied_per_week',
        'sleep_hours_per_night', 'tutoring_sessions', 'physical_activity'
    ]
    boolean_cols = [
        'internet_access', 'learning_disabilities', 'extracurricular_activities'
    ]
    
    # Convert bools to int
    for col in boolean_cols:
        X[col] = X[col].astype(int)
        
    # Preprocessor
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), numeric_cols + boolean_cols),
            ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_cols)
        ]
    )
    
    # Pipeline
    model = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('regressor', RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1))
    ])
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training model...")
    model.fit(X_train, y_train)
    
    # Evaluate
    predictions = model.predict(X_test)
    r2 = r2_score(y_test, predictions)
    rmse = np.sqrt(mean_squared_error(y_test, predictions))
    print(f"Model trained successfully!")
    print(f"R² Score: {r2:.4f}")
    print(f"RMSE: {rmse:.4f}%")
    
    # Export Model
    os.makedirs('ml', exist_ok=True)
    model_path = 'ml/student_predictor.pkl'
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
    print(f"Model exported to {model_path}")

if __name__ == "__main__":
    train_model()
