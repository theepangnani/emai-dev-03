"""Ontario university program admission requirements — static reference data (#506).

Each entry maps a program name to:
- universities: list of Ontario universities offering the program
- required_courses: Ontario course codes that are mandatory prerequisites
- recommended_courses: Ontario course codes that strengthen the application
- min_average: typical minimum admission average (varies by university/year)
- description: human-readable note about key requirements
"""

UNIVERSITY_PROGRAMS: dict[str, dict] = {
    "Computer Science": {
        "universities": [
            "University of Toronto",
            "University of Waterloo",
            "McMaster University",
            "York University",
            "Toronto Metropolitan University",
            "University of Ottawa",
            "Carleton University",
        ],
        "required_courses": ["MHF4U", "MCV4U"],
        "recommended_courses": ["ICS4U", "MDM4U", "SCH4U"],
        "min_average": 85,
        "description": "Requires Grade 12 Advanced Functions and Calculus & Vectors. "
                       "Computer Science and Data Management are strongly recommended.",
    },
    "Engineering": {
        "universities": [
            "University of Toronto",
            "University of Waterloo",
            "McMaster University",
            "Queen's University",
            "Western University",
            "University of Ottawa",
            "Carleton University",
        ],
        "required_courses": ["MHF4U", "MCV4U", "SPH4U"],
        "recommended_courses": ["ICS4U", "SCH4U"],
        "min_average": 87,
        "description": "Requires Advanced Functions, Calculus & Vectors, and Physics. "
                       "Chemistry and Computer Science are strongly recommended.",
    },
    "Medicine / Pre-Med": {
        "universities": [
            "University of Toronto",
            "McMaster University",
            "Queen's University",
            "Western University",
            "University of Ottawa",
        ],
        "required_courses": ["SBI4U", "SCH4U", "MHF4U"],
        "recommended_courses": ["SPH4U", "MCV4U", "ENG4U"],
        "min_average": 90,
        "description": "Requires Biology, Chemistry, and Advanced Functions. A very high average "
                       "(90%+) is essential. Physics and English are also important.",
    },
    "Business": {
        "universities": [
            "University of Toronto (Rotman)",
            "Wilfrid Laurier University (BBA)",
            "Western University (Ivey)",
            "Queen's University (Smith)",
            "York University (Schulich)",
            "Ryerson/TMU",
        ],
        "required_courses": ["ENG4U"],
        "recommended_courses": ["MDM4U", "BOH4M", "BAF3M", "MHF4U"],
        "min_average": 80,
        "description": "English is required. Data Management, Business Leadership, and "
                       "Financial Accounting are recommended. Some programs require MHF4U.",
    },
    "Arts & Humanities": {
        "universities": [
            "University of Toronto",
            "Western University",
            "Queen's University",
            "McMaster University",
            "York University",
            "University of Guelph",
        ],
        "required_courses": ["ENG4U"],
        "recommended_courses": ["OLC4O", "HSB4U", "HHG4M", "FSF4U"],
        "min_average": 75,
        "description": "English is required. Social Sciences, Philosophy, and a Second "
                       "Language strengthen applications in Arts & Humanities programs.",
    },
    "Nursing": {
        "universities": [
            "University of Toronto",
            "McMaster University",
            "Western University",
            "Queen's University",
            "Toronto Metropolitan University",
            "York University",
        ],
        "required_courses": ["SBI4U", "ENG4U"],
        "recommended_courses": ["SCH4U", "PSK4U", "HSP3U"],
        "min_average": 82,
        "description": "Biology and English are required. Chemistry, Psychology, and Health "
                       "Sciences are strongly recommended.",
    },
    "Education": {
        "universities": [
            "University of Toronto (OISE)",
            "Western University",
            "Queen's University",
            "York University",
            "University of Ottawa",
            "Brock University",
        ],
        "required_courses": ["ENG4U"],
        "recommended_courses": ["PSK4U", "HSB4U", "HHG4M"],
        "min_average": 75,
        "description": "English is required. Psychology, Human Development, and Social "
                       "Sciences are recommended for aspiring educators.",
    },
    "Law (Undergraduate)": {
        "universities": [
            "Carleton University (Law & Legal Studies)",
            "York University (Criminology)",
            "University of Guelph",
            "Brock University",
        ],
        "required_courses": ["ENG4U"],
        "recommended_courses": ["CLN4U", "HSB4U", "CPW4U", "OLC4O"],
        "min_average": 80,
        "description": "English and strong writing skills are essential. Law, Canadian "
                       "and International Law, and Social Sciences are valuable.",
    },
    "Architecture": {
        "universities": [
            "University of Toronto (Daniels)",
            "Carleton University",
            "Toronto Metropolitan University",
            "University of Waterloo",
        ],
        "required_courses": ["ENG4U", "MHF4U"],
        "recommended_courses": ["MCV4U", "AWR4M", "TGJ4M"],
        "min_average": 83,
        "description": "English and Advanced Functions are required. Calculus, Visual Arts, "
                       "and Technology Design are strongly recommended.",
    },
    "Kinesiology": {
        "universities": [
            "McMaster University",
            "Western University",
            "Brock University",
            "University of Guelph",
            "Toronto Metropolitan University",
        ],
        "required_courses": ["SBI4U", "ENG4U"],
        "recommended_courses": ["SPH4U", "PSK4U", "SCH4U"],
        "min_average": 78,
        "description": "Biology and English are required. Physics, Psychology, and Chemistry "
                       "are recommended for Kinesiology programs.",
    },
    "Mathematics & Statistics": {
        "universities": [
            "University of Waterloo",
            "University of Toronto",
            "McMaster University",
            "Queen's University",
            "Western University",
        ],
        "required_courses": ["MHF4U", "MCV4U"],
        "recommended_courses": ["MDM4U", "ICS4U"],
        "min_average": 85,
        "description": "Advanced Functions and Calculus & Vectors are required. "
                       "Data Management and Computer Science are strongly recommended.",
    },
    "Environmental Science": {
        "universities": [
            "University of Guelph",
            "University of Toronto",
            "McMaster University",
            "Carleton University",
            "Western University",
        ],
        "required_courses": ["SBI4U", "SCH4U"],
        "recommended_courses": ["MHF4U", "SPH4U", "ENG4U", "CGF3M"],
        "min_average": 78,
        "description": "Biology and Chemistry are required. Physics, Advanced Functions, "
                       "English, and Geography are strongly recommended.",
    },
}
