"""
Demo institutional data definitions and templates for EduPulse.

Provides structured definitions for ~3 departments (CSE, ECE, MECH),
faculty members, courses, batches, subjects, and 60 realistic student profiles.
"""

UNIVERSITY_DATA = {
    "name": "Apex Institute of Science & Technology",
    "code": "APEX",
    "established_year": 1985,
}

SCHOOL_DATA = {
    "name": "School of Engineering & Technology",
    "code": "SOET",
}

ADMIN_USERS = [
    {
        "username": "admin",
        "role": "SYSADMIN",
        "first_name": "System",
        "last_name": "Administrator",
        "email": "admin@apex.edu.test",
        "is_staff": True,
        "is_superuser": True,
    },
    {
        "username": "vc",
        "role": "VC",
        "first_name": "Ishaan",
        "last_name": "Sharma",
        "email": "vc@apex.edu.test",
        "is_staff": True,
        "is_superuser": False,
    },
    {
        "username": "registrar",
        "role": "REGISTRAR",
        "first_name": "Sunita",
        "last_name": "Deshmukh",
        "email": "registrar@apex.edu.test",
        "is_staff": True,
        "is_superuser": False,
    },
    {
        "username": "coe",
        "role": "CONTROLLER",
        "first_name": "Ramesh",
        "last_name": "Joshi",
        "email": "coe@apex.edu.test",
        "is_staff": True,
        "is_superuser": False,
    },
    {
        "username": "dean_engg",
        "role": "DEAN",
        "first_name": "Tara",
        "last_name": "Iyer",
        "email": "dean.engg@apex.edu.test",
        "is_staff": True,
        "is_superuser": False,
    },
]

DEPARTMENTS_DATA = [
    {
        "code": "CSE",
        "name": "Department of Computer Science & Engineering",
        "hod": {
            "username": "hod_cse",
            "first_name": "Shreya",
            "last_name": "Mehta",
            "email": "hod.cse@apex.edu.test",
        },
        "course": {
            "code": "BTCSE",
            "name": "B.Tech Computer Science & Engineering",
            "level": "UG",
            "duration_years": 4,
        },
        "batch_code": "2024-BTCSE",
        "teachers": [
            {
                "username": "teacher_cse1",
                "first_name": "Vikram",
                "last_name": "Kumar",
                "email": "vikram.cse@apex.edu.test",
                "staff_id": "FAC-CSE-01",
                "designation": "Associate Professor",
            },
            {
                "username": "teacher_cse2",
                "first_name": "Priya",
                "last_name": "Nair",
                "email": "priya.cse@apex.edu.test",
                "staff_id": "FAC-CSE-02",
                "designation": "Assistant Professor",
            },
        ],
        "subjects": [
            {"code": "CS101", "title": "Problem Solving & Programming in C", "credits": 4, "max_marks": 100},
            {"code": "CS102", "title": "Discrete Mathematical Structures", "credits": 4, "max_marks": 100},
            {"code": "CS103", "title": "Data Structures & Algorithms", "credits": 4, "max_marks": 100},
            {"code": "CS104", "title": "Digital Logic & Computer Design", "credits": 4, "max_marks": 100},
        ],
        "roll_prefix": "24CSE",
        "first_names": [
            "Aarav", "Aditi", "Akash", "Ananya", "Arjun",
            "Deepak", "Divya", "Gaurav", "Harsh", "Isha",
            "Kavya", "Manish", "Neha", "Pranav", "Pooja",
            "Rahul", "Riya", "Rohan", "Sneha", "Varun",
        ],
    },
    {
        "code": "ECE",
        "name": "Department of Electronics & Communication",
        "hod": {
            "username": "hod_ece",
            "first_name": "Suresh",
            "last_name": "Menon",
            "email": "hod.ece@apex.edu.test",
        },
        "course": {
            "code": "BTECE",
            "name": "B.Tech Electronics & Communication",
            "level": "UG",
            "duration_years": 4,
        },
        "batch_code": "2024-BTECE",
        "teachers": [
            {
                "username": "teacher_ece1",
                "first_name": "Anika",
                "last_name": "Menon",
                "email": "anika.ece@apex.edu.test",
                "staff_id": "FAC-ECE-01",
                "designation": "Associate Professor",
            },
            {
                "username": "teacher_ece2",
                "first_name": "Karthik",
                "last_name": "Rao",
                "email": "karthik.ece@apex.edu.test",
                "staff_id": "FAC-ECE-02",
                "designation": "Assistant Professor",
            },
        ],
        "subjects": [
            {"code": "EC101", "title": "Network Analysis & Synthesis", "credits": 4, "max_marks": 100},
            {"code": "EC102", "title": "Electronic Devices & Circuits", "credits": 4, "max_marks": 100},
            {"code": "EC103", "title": "Signals & Systems", "credits": 4, "max_marks": 100},
            {"code": "EC104", "title": "Electromagnetic Field Theory", "credits": 4, "max_marks": 100},
        ],
        "roll_prefix": "24ECE",
        "first_names": [
            "Abhinav", "Amrita", "Anand", "Bhavna", "Chetan",
            "Dipti", "Girish", "Himanshu", "Jyoti", "Karan",
            "Meera", "Naveen", "Pallavi", "Rajesh", "Sandhya",
            "Siddharth", "Swati", "Tanvi", "Vikas", "Yash",
        ],
    },
    {
        "code": "MECH",
        "name": "Department of Mechanical Engineering",
        "hod": {
            "username": "hod_mech",
            "first_name": "Rakesh",
            "last_name": "Gupta",
            "email": "hod.mech@apex.edu.test",
        },
        "course": {
            "code": "BTME",
            "name": "B.Tech Mechanical Engineering",
            "level": "UG",
            "duration_years": 4,
        },
        "batch_code": "2024-BTME",
        "teachers": [
            {
                "username": "teacher_mech1",
                "first_name": "Amit",
                "last_name": "Patel",
                "email": "amit.mech@apex.edu.test",
                "staff_id": "FAC-ME-01",
                "designation": "Professor",
            },
            {
                "username": "teacher_mech2",
                "first_name": "Kavita",
                "last_name": "Rao",
                "email": "kavita.mech@apex.edu.test",
                "staff_id": "FAC-ME-02",
                "designation": "Assistant Professor",
            },
        ],
        "subjects": [
            {"code": "ME101", "title": "Engineering Thermodynamics", "credits": 4, "max_marks": 100},
            {"code": "ME102", "title": "Mechanics of Solids", "credits": 4, "max_marks": 100},
            {"code": "ME103", "title": "Material Science & Metallurgy", "credits": 4, "max_marks": 100},
            {"code": "ME104", "title": "Fluid Mechanics", "credits": 4, "max_marks": 100},
        ],
        "roll_prefix": "24ME",
        "first_names": [
            "Ajay", "Alok", "Anil", "Arpita", "Bhaskar",
            "Chitra", "Dinesh", "Gautam", "Inder", "Jitendra",
            "Kishore", "Madhu", "Manoj", "Nitin", "Pankaj",
            "Ritu", "Sachin", "Sanjay", "Sunil", "Vivek",
        ],
    },
]

LAST_NAMES = [
    "Verma", "Singh", "Sharma", "Reddy", "Patel",
    "Nair", "Iyer", "Chopra", "Banerjee", "Bhat",
    "Das", "Kulkarni", "Ghosh", "Malhotra", "Kapoor",
    "Pillai", "Bose", "Joshi", "Mishra", "Saxena",
]
