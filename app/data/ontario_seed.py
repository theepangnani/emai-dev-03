"""
Ontario course catalog seed data (#500, #511).

Provides seed_ontario_data(db) which is idempotent (safe to call on every startup).
Seeds:
  - 5 Ontario school boards (TDSB, PDSB, YRDSB, HDSB, OCDSB)
  - ~80 core OSSD courses covering all compulsory requirements, with correct
    is_compulsory flags, compulsory_category values, and prerequisite chains.
"""

import logging
from sqlalchemy.orm import Session

from app.models.ontario_board import OntarioBoard
from app.models.course_catalog import CourseCatalogItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Board definitions
# ---------------------------------------------------------------------------

BOARDS = [
    {
        "code": "TDSB",
        "name": "Toronto District School Board",
        "region": "Toronto",
        "website_url": "https://www.tdsb.on.ca",
    },
    {
        "code": "PDSB",
        "name": "Peel District School Board",
        "region": "Peel Region",
        "website_url": "https://www.peelschools.org",
    },
    {
        "code": "YRDSB",
        "name": "York Region District School Board",
        "region": "York Region",
        "website_url": "https://www.yrdsb.ca",
    },
    {
        "code": "HDSB",
        "name": "Halton District School Board",
        "region": "Halton Region",
        "website_url": "https://www.hdsb.ca",
    },
    {
        "code": "OCDSB",
        "name": "Ottawa-Carleton District School Board",
        "region": "Ottawa-Carleton",
        "website_url": "https://www.ocdsb.ca",
    },
]

# ---------------------------------------------------------------------------
# Course definitions
# board_id=None means the course is universal (offered by all boards)
# ---------------------------------------------------------------------------

# Each course dict keys:
#   course_code, course_name, subject_area, grade_level, pathway,
#   credit_value (default 1.0), is_compulsory (default False),
#   compulsory_category (None), prerequisite_codes ([]),
#   description (None), is_ib, is_ap, is_shsm (all False)

COURSES = [
    # ────────── ENGLISH (compulsory Grades 9-12) ──────────
    {
        "course_code": "ENG1D",
        "course_name": "English, Grade 9, Academic",
        "subject_area": "English",
        "grade_level": 9,
        "pathway": "D",
        "is_compulsory": True,
        "compulsory_category": "English",
        "prerequisite_codes": [],
        "description": "This course is designed to develop the oral communication, reading, writing, and media literacy skills that students need for success in secondary school and daily life.",
    },
    {
        "course_code": "ENG1P",
        "course_name": "English, Grade 9, Applied",
        "subject_area": "English",
        "grade_level": 9,
        "pathway": "P",
        "is_compulsory": True,
        "compulsory_category": "English",
        "prerequisite_codes": [],
        "description": "This course focuses on the development of literacy skills required for everyday life.",
    },
    {
        "course_code": "ENG2D",
        "course_name": "English, Grade 10, Academic",
        "subject_area": "English",
        "grade_level": 10,
        "pathway": "D",
        "is_compulsory": True,
        "compulsory_category": "English",
        "prerequisite_codes": ["ENG1D"],
        "description": "This course emphasizes the development of literacy, communication, and critical and creative thinking skills through the study and creation of increasingly complex and challenging texts.",
    },
    {
        "course_code": "ENG2P",
        "course_name": "English, Grade 10, Applied",
        "subject_area": "English",
        "grade_level": 10,
        "pathway": "P",
        "is_compulsory": True,
        "compulsory_category": "English",
        "prerequisite_codes": ["ENG1P"],
        "description": "This course emphasizes the development of literacy, communication, and critical thinking skills through the study and creation of a variety of informational, literary, and graphic texts.",
    },
    {
        "course_code": "ENG3U",
        "course_name": "English, Grade 11, University",
        "subject_area": "English",
        "grade_level": 11,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["ENG2D"],
        "description": "This course emphasizes the development of literacy, communication, and critical and creative thinking skills through the study and creation of increasingly complex and challenging texts.",
    },
    {
        "course_code": "ENG3C",
        "course_name": "English, Grade 11, College",
        "subject_area": "English",
        "grade_level": 11,
        "pathway": "C",
        "is_compulsory": False,
        "prerequisite_codes": ["ENG2P"],
        "description": "This course emphasizes the development of literacy and communication skills.",
    },
    {
        "course_code": "ENG4U",
        "course_name": "English, Grade 12, University",
        "subject_area": "English",
        "grade_level": 12,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["ENG3U"],
        "description": "This course emphasizes the consolidation of literacy, communication, and critical and creative thinking skills necessary for success in academic and daily life.",
    },
    {
        "course_code": "ENG4C",
        "course_name": "English, Grade 12, College",
        "subject_area": "English",
        "grade_level": 12,
        "pathway": "C",
        "is_compulsory": False,
        "prerequisite_codes": ["ENG3C"],
        "description": "This course emphasizes the consolidation of literacy, communication, and critical thinking skills.",
    },

    # ────────── MATHEMATICS (compulsory Grades 9-10) ──────────
    {
        "course_code": "MPM1D",
        "course_name": "Principles of Mathematics, Grade 9, Academic",
        "subject_area": "Mathematics",
        "grade_level": 9,
        "pathway": "D",
        "is_compulsory": True,
        "compulsory_category": "Mathematics",
        "prerequisite_codes": [],
        "description": "This course enables students to develop an understanding of mathematical concepts related to algebra, analytic geometry, and measurement and geometry through investigation, the effective use of technology, and abstract reasoning.",
    },
    {
        "course_code": "MFM1P",
        "course_name": "Foundations of Mathematics, Grade 9, Applied",
        "subject_area": "Mathematics",
        "grade_level": 9,
        "pathway": "P",
        "is_compulsory": True,
        "compulsory_category": "Mathematics",
        "prerequisite_codes": [],
        "description": "This course enables students to develop an understanding of mathematical concepts related to introductory algebra, proportional reasoning, and measurement and geometry through investigation, the effective use of technology, and hands-on activities.",
    },
    {
        "course_code": "MPM2D",
        "course_name": "Principles of Mathematics, Grade 10, Academic",
        "subject_area": "Mathematics",
        "grade_level": 10,
        "pathway": "D",
        "is_compulsory": True,
        "compulsory_category": "Mathematics",
        "prerequisite_codes": ["MPM1D"],
        "description": "This course enables students to broaden their understanding of relationships and extend their problem-solving and algebraic skills through investigation, the effective use of technology, and abstract reasoning.",
    },
    {
        "course_code": "MFM2P",
        "course_name": "Foundations of Mathematics, Grade 10, Applied",
        "subject_area": "Mathematics",
        "grade_level": 10,
        "pathway": "P",
        "is_compulsory": True,
        "compulsory_category": "Mathematics",
        "prerequisite_codes": ["MFM1P"],
        "description": "This course enables students to consolidate their understanding of linear relations and extend their problem-solving and algebraic skills to investigate and represent the relationships found in geometric and measurement contexts.",
    },
    {
        "course_code": "MCR3U",
        "course_name": "Functions, Grade 11, University",
        "subject_area": "Mathematics",
        "grade_level": 11,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["MPM2D"],
        "description": "This course introduces the mathematical concept of the function by extending students' experiences with linear and quadratic relations.",
    },
    {
        "course_code": "MCF3M",
        "course_name": "Functions and Applications, Grade 11, University/College",
        "subject_area": "Mathematics",
        "grade_level": 11,
        "pathway": "M",
        "is_compulsory": False,
        "prerequisite_codes": ["MPM2D"],
        "description": "This course introduces basic features of the function by extending students' experiences with quadratic relations.",
    },
    {
        "course_code": "MBF3C",
        "course_name": "Foundations for College Mathematics, Grade 11, College",
        "subject_area": "Mathematics",
        "grade_level": 11,
        "pathway": "C",
        "is_compulsory": False,
        "prerequisite_codes": ["MFM2P"],
        "description": "This course enables students to broaden their understanding of mathematics as a problem-solving tool in the real world.",
    },
    {
        "course_code": "MHF4U",
        "course_name": "Advanced Functions, Grade 12, University",
        "subject_area": "Mathematics",
        "grade_level": 12,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["MCR3U"],
        "description": "This course extends students' experience with functions. Students will investigate the properties of polynomial, rational, logarithmic, and trigonometric functions.",
    },
    {
        "course_code": "MCV4U",
        "course_name": "Calculus and Vectors, Grade 12, University",
        "subject_area": "Mathematics",
        "grade_level": 12,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["MHF4U"],
        "description": "This course builds on students' previous experience with functions and their developing understanding of rates of change.",
    },
    {
        "course_code": "MDM4U",
        "course_name": "Mathematics of Data Management, Grade 12, University",
        "subject_area": "Mathematics",
        "grade_level": 12,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["MCR3U"],
        "description": "This course broadens students' understanding of mathematics as it relates to managing data.",
    },
    {
        "course_code": "MAP4C",
        "course_name": "Foundations for College Mathematics, Grade 12, College",
        "subject_area": "Mathematics",
        "grade_level": 12,
        "pathway": "C",
        "is_compulsory": False,
        "prerequisite_codes": ["MBF3C"],
        "description": "This course enables students to broaden their understanding of real-world applications of mathematics.",
    },

    # ────────── SCIENCE (compulsory Grades 9-10) ──────────
    {
        "course_code": "SNC1D",
        "course_name": "Science, Grade 9, Academic",
        "subject_area": "Science",
        "grade_level": 9,
        "pathway": "D",
        "is_compulsory": True,
        "compulsory_category": "Science",
        "prerequisite_codes": [],
        "description": "This course enables students to develop their understanding of basic concepts in biology, chemistry, earth and space science, and physics, and to relate science to technology, society, and the environment.",
    },
    {
        "course_code": "SNC1P",
        "course_name": "Science, Grade 9, Applied",
        "subject_area": "Science",
        "grade_level": 9,
        "pathway": "P",
        "is_compulsory": True,
        "compulsory_category": "Science",
        "prerequisite_codes": [],
        "description": "This course enables students to develop their understanding of basic concepts in biology, chemistry, earth and space science, and physics, and to relate science to technology, society, and the environment.",
    },
    {
        "course_code": "SNC2D",
        "course_name": "Science, Grade 10, Academic",
        "subject_area": "Science",
        "grade_level": 10,
        "pathway": "D",
        "is_compulsory": True,
        "compulsory_category": "Science",
        "prerequisite_codes": ["SNC1D"],
        "description": "This course enables students to enhance their understanding of concepts in biology, chemistry, earth and space science, and physics, and of the interrelationships between science, technology, society, and the environment.",
    },
    {
        "course_code": "SNC2P",
        "course_name": "Science, Grade 10, Applied",
        "subject_area": "Science",
        "grade_level": 10,
        "pathway": "P",
        "is_compulsory": True,
        "compulsory_category": "Science",
        "prerequisite_codes": ["SNC1P"],
        "description": "This course enables students to develop a deeper understanding of concepts in biology, chemistry, earth and space science, and physics.",
    },
    {
        "course_code": "SCH3U",
        "course_name": "Chemistry, Grade 11, University",
        "subject_area": "Science",
        "grade_level": 11,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["SNC2D"],
        "description": "This course enables students to deepen their understanding of chemistry through the study of the properties of chemicals and chemical bonds.",
    },
    {
        "course_code": "SCH3M",
        "course_name": "Chemistry, Grade 11, University/College",
        "subject_area": "Science",
        "grade_level": 11,
        "pathway": "M",
        "is_compulsory": False,
        "prerequisite_codes": ["SNC2D"],
        "description": "This course enables students to deepen their understanding of chemistry through the study of the properties of chemicals and chemical bonds.",
    },
    {
        "course_code": "SCH4U",
        "course_name": "Chemistry, Grade 12, University",
        "subject_area": "Science",
        "grade_level": 12,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["SCH3U"],
        "description": "This course enables students to deepen their understanding of chemistry through the study of organic chemistry, the structure and properties of matter, energy changes and rates of reaction, equilibrium in chemical systems, and electrochemistry.",
    },
    {
        "course_code": "SCH4C",
        "course_name": "Chemistry, Grade 12, College",
        "subject_area": "Science",
        "grade_level": 12,
        "pathway": "C",
        "is_compulsory": False,
        "prerequisite_codes": ["SCH3M"],
        "description": "This course enables students to deepen their understanding of chemistry.",
    },
    {
        "course_code": "SPH3U",
        "course_name": "Physics, Grade 11, University",
        "subject_area": "Science",
        "grade_level": 11,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["SNC2D"],
        "description": "This course develops students' understanding of the basic concepts of physics. Students will explore kinematics, with an emphasis on linear motion; different kinds of forces; energy transformations; the properties of mechanical waves and sound; and electricity and magnetism.",
    },
    {
        "course_code": "SPH4U",
        "course_name": "Physics, Grade 12, University",
        "subject_area": "Science",
        "grade_level": 12,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["SPH3U"],
        "description": "This course enables students to deepen their understanding of physics concepts and theories. Students will continue their exploration of energy transformations and the forces that affect motion, and will investigate electrical, gravitational, and magnetic fields and electromagnetic radiation.",
    },
    {
        "course_code": "SBI3U",
        "course_name": "Biology, Grade 11, University",
        "subject_area": "Science",
        "grade_level": 11,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["SNC2D"],
        "description": "This course furthers students' understanding of the processes that occur in biological systems. Students will study theory and conduct investigations in the areas of biodiversity, evolution, genetic processes, the structure and function of animals, and the anatomy, growth, and function of plants.",
    },
    {
        "course_code": "SBI4U",
        "course_name": "Biology, Grade 12, University",
        "subject_area": "Science",
        "grade_level": 12,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["SBI3U"],
        "description": "This course provides students with the opportunity for in-depth study of the concepts and processes associated with biological systems.",
    },

    # ────────── CANADIAN HISTORY (compulsory Grade 10) ──────────
    {
        "course_code": "CHC2D",
        "course_name": "Canadian History Since World War I, Grade 10, Academic",
        "subject_area": "Canadian and World Studies",
        "grade_level": 10,
        "pathway": "D",
        "is_compulsory": True,
        "compulsory_category": "Canadian History",
        "prerequisite_codes": [],
        "description": "This course explores social, economic, and political developments and events and their impact on the lives of different groups in Canada since 1914.",
    },
    {
        "course_code": "CHC2P",
        "course_name": "Canadian History Since World War I, Grade 10, Applied",
        "subject_area": "Canadian and World Studies",
        "grade_level": 10,
        "pathway": "P",
        "is_compulsory": True,
        "compulsory_category": "Canadian History",
        "prerequisite_codes": [],
        "description": "This course explores social, economic, and political developments and events and their impact on the lives of different groups in Canada since 1914.",
    },

    # ────────── CANADIAN GEOGRAPHY (compulsory Grade 9) ──────────
    {
        "course_code": "CGC1D",
        "course_name": "Issues in Canadian Geography, Grade 9, Academic",
        "subject_area": "Canadian and World Studies",
        "grade_level": 9,
        "pathway": "D",
        "is_compulsory": True,
        "compulsory_category": "Canadian Geography",
        "prerequisite_codes": [],
        "description": "This course examines interrelationships within and between Canada's natural and human systems and how these systems interconnect with those in other parts of the world.",
    },
    {
        "course_code": "CGC1P",
        "course_name": "Issues in Canadian Geography, Grade 9, Applied",
        "subject_area": "Canadian and World Studies",
        "grade_level": 9,
        "pathway": "P",
        "is_compulsory": True,
        "compulsory_category": "Canadian Geography",
        "prerequisite_codes": [],
        "description": "This course examines interrelationships within and between Canada's natural and human systems.",
    },

    # ────────── CIVICS (compulsory Grade 10, 0.5 credit) ──────────
    {
        "course_code": "CHV2O",
        "course_name": "Civics and Citizenship, Grade 10, Open",
        "subject_area": "Canadian and World Studies",
        "grade_level": 10,
        "pathway": "O",
        "credit_value": 0.5,
        "is_compulsory": True,
        "compulsory_category": "Civics",
        "prerequisite_codes": [],
        "description": "This course explores rights and responsibilities associated with being an active citizen in a democratic society. Students will explore issues of civic importance such as healthy schools, community planning, environmental responsibility, and the influence of social media.",
    },

    # ────────── CAREER STUDIES (compulsory Grade 10, 0.5 credit) ──────────
    {
        "course_code": "GLC2O",
        "course_name": "Career Studies, Grade 10, Open",
        "subject_area": "Guidance and Career Education",
        "grade_level": 10,
        "pathway": "O",
        "credit_value": 0.5,
        "is_compulsory": True,
        "compulsory_category": "Career Studies",
        "prerequisite_codes": [],
        "description": "This course teaches students how to develop and achieve personal goals for future learning, work, and community involvement.",
    },

    # ────────── HEALTH & PHYSICAL EDUCATION (compulsory) ──────────
    {
        "course_code": "PPL1O",
        "course_name": "Health and Physical Education, Grade 9, Open",
        "subject_area": "Health and Physical Education",
        "grade_level": 9,
        "pathway": "O",
        "is_compulsory": True,
        "compulsory_category": "Health and Physical Education",
        "prerequisite_codes": [],
        "description": "This course equips students with the knowledge and skills they need to make healthy choices now and lead healthy, active lives in the future.",
    },
    {
        "course_code": "PPL2O",
        "course_name": "Health and Physical Education, Grade 10, Open",
        "subject_area": "Health and Physical Education",
        "grade_level": 10,
        "pathway": "O",
        "is_compulsory": True,
        "compulsory_category": "Health and Physical Education",
        "prerequisite_codes": ["PPL1O"],
        "description": "This course focuses on the importance of regular physical activity in students' daily lives and the development of health literacy.",
    },
    {
        "course_code": "PPL3O",
        "course_name": "Health and Physical Education, Grade 11, Open",
        "subject_area": "Health and Physical Education",
        "grade_level": 11,
        "pathway": "O",
        "is_compulsory": False,
        "prerequisite_codes": ["PPL2O"],
        "description": "This course focuses on the importance of regular physical activity in students' daily lives.",
    },

    # ────────── ARTS (compulsory — 1 credit in Gr 9-12) ──────────
    {
        "course_code": "AVI1O",
        "course_name": "Visual Arts, Grade 9, Open",
        "subject_area": "Arts",
        "grade_level": 9,
        "pathway": "O",
        "is_compulsory": True,
        "compulsory_category": "Arts",
        "prerequisite_codes": [],
        "description": "This course enables students to develop their skills in producing, responding to, and analyzing visual art. Students will create two- and three-dimensional art works.",
    },
    {
        "course_code": "AVI2O",
        "course_name": "Visual Arts, Grade 10, Open",
        "subject_area": "Arts",
        "grade_level": 10,
        "pathway": "O",
        "is_compulsory": False,
        "prerequisite_codes": ["AVI1O"],
        "description": "This course enables students to develop their skills in producing, responding to, and analyzing visual art.",
    },
    {
        "course_code": "AMU1O",
        "course_name": "Music, Grade 9, Open",
        "subject_area": "Arts",
        "grade_level": 9,
        "pathway": "O",
        "is_compulsory": True,
        "compulsory_category": "Arts",
        "prerequisite_codes": [],
        "description": "This course provides students with opportunities to develop musical literacy through the creation, performance, and critical analysis of music.",
    },
    {
        "course_code": "ATC1O",
        "course_name": "Drama, Grade 9, Open",
        "subject_area": "Arts",
        "grade_level": 9,
        "pathway": "O",
        "is_compulsory": True,
        "compulsory_category": "Arts",
        "prerequisite_codes": [],
        "description": "This course provides students with opportunities to explore dramatic forms and theatrical traditions from various times and places and to create and perform drama for a variety of audiences and purposes.",
    },
    {
        "course_code": "ATC2O",
        "course_name": "Drama, Grade 10, Open",
        "subject_area": "Arts",
        "grade_level": 10,
        "pathway": "O",
        "is_compulsory": False,
        "prerequisite_codes": ["ATC1O"],
        "description": "This course provides students with opportunities to explore dramatic forms and theatrical traditions.",
    },
    {
        "course_code": "ATC3M",
        "course_name": "Drama, Grade 11, University/College",
        "subject_area": "Arts",
        "grade_level": 11,
        "pathway": "M",
        "is_compulsory": False,
        "prerequisite_codes": ["ATC2O"],
        "description": "This course enables students to further develop their skills and knowledge in drama.",
    },

    # ────────── FRENCH AS A SECOND LANGUAGE ──────────
    {
        "course_code": "FSF1D",
        "course_name": "Core French, Grade 9, Academic",
        "subject_area": "French as a Second Language",
        "grade_level": 9,
        "pathway": "D",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course emphasizes the development of oral communication, reading, and writing skills. Students will develop their ability to understand and speak French in a variety of everyday situations.",
    },
    {
        "course_code": "FSF1P",
        "course_name": "Core French, Grade 9, Applied",
        "subject_area": "French as a Second Language",
        "grade_level": 9,
        "pathway": "P",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course emphasizes the development of oral communication, reading, and writing skills in French.",
    },
    {
        "course_code": "FSF2D",
        "course_name": "Core French, Grade 10, Academic",
        "subject_area": "French as a Second Language",
        "grade_level": 10,
        "pathway": "D",
        "is_compulsory": False,
        "prerequisite_codes": ["FSF1D"],
        "description": "This course continues to emphasize the development of oral communication, reading, and writing skills in French.",
    },
    {
        "course_code": "FSF3U",
        "course_name": "Core French, Grade 11, University",
        "subject_area": "French as a Second Language",
        "grade_level": 11,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["FSF2D"],
        "description": "This course draws on a variety of themes to promote extensive reading and communication skills.",
    },
    {
        "course_code": "FSF4U",
        "course_name": "Core French, Grade 12, University",
        "subject_area": "French as a Second Language",
        "grade_level": 12,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["FSF3U"],
        "description": "This course provides students with opportunities to speak and interact in French independently.",
    },

    # ────────── COMPUTER SCIENCE ──────────
    {
        "course_code": "ICS3U",
        "course_name": "Introduction to Computer Science, Grade 11, University",
        "subject_area": "Computer Science",
        "grade_level": 11,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course introduces students to computer science. Students will design software independently and as part of a team, using industry-standard programming tools and applying the software development life-cycle model.",
    },
    {
        "course_code": "ICS4U",
        "course_name": "Computer Science, Grade 12, University",
        "subject_area": "Computer Science",
        "grade_level": 12,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["ICS3U"],
        "description": "This course enables students to further develop knowledge and skills in computer science. Students will use modular design principles to create complex and fully documented programs.",
    },
    {
        "course_code": "ICS3C",
        "course_name": "Introduction to Computer Science, Grade 11, College",
        "subject_area": "Computer Science",
        "grade_level": 11,
        "pathway": "C",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course introduces students to computer science and fundamental programming concepts using an industry-standard programming environment.",
    },

    # ────────── BUSINESS ──────────
    {
        "course_code": "BBI1O",
        "course_name": "Introduction to Business, Grade 9, Open",
        "subject_area": "Business Studies",
        "grade_level": 9,
        "pathway": "O",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course introduces students to the world of business. Students will develop an understanding of the environment in which businesses operate.",
    },
    {
        "course_code": "BAF3M",
        "course_name": "Financial Accounting Fundamentals, Grade 11, University/College",
        "subject_area": "Business Studies",
        "grade_level": 11,
        "pathway": "M",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course introduces students to the fundamental principles and procedures of accounting. Students will develop financial analysis and decision-making skills.",
    },
    {
        "course_code": "BDI3C",
        "course_name": "Entrepreneurship: The Venture, Grade 11, College",
        "subject_area": "Business Studies",
        "grade_level": 11,
        "pathway": "C",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course focuses on the concept of entrepreneurship. Students will acquire an understanding of the characteristics of an entrepreneur and the skills needed to establish a successful business venture.",
    },
    {
        "course_code": "BOH4M",
        "course_name": "Business Leadership: Management Fundamentals, Grade 12, University/College",
        "subject_area": "Business Studies",
        "grade_level": 12,
        "pathway": "M",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course focuses on the development of leadership and management skills. Students will analyse various management theories and apply them in business contexts.",
    },
    {
        "course_code": "BAT4M",
        "course_name": "Financial Accounting Principles, Grade 12, University/College",
        "subject_area": "Business Studies",
        "grade_level": 12,
        "pathway": "M",
        "is_compulsory": False,
        "prerequisite_codes": ["BAF3M"],
        "description": "This course enables students to develop a thorough understanding of financial accounting principles for various types of business.",
    },

    # ────────── SOCIAL SCIENCES ──────────
    {
        "course_code": "HSP3U",
        "course_name": "Introduction to Anthropology, Psychology, and Sociology, Grade 11, University",
        "subject_area": "Social Sciences and Humanities",
        "grade_level": 11,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course provides students with opportunities to think critically about theories, questions, and issues related to anthropology, psychology, and sociology.",
    },
    {
        "course_code": "HHS4U",
        "course_name": "Families in Canada, Grade 12, University",
        "subject_area": "Social Sciences and Humanities",
        "grade_level": 12,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["HSP3U"],
        "description": "This course enables students to analyse and evaluate the importance of families in Canadian society.",
    },
    {
        "course_code": "HFA4U",
        "course_name": "Individuals and Families in a Diverse Society, Grade 12, University",
        "subject_area": "Social Sciences and Humanities",
        "grade_level": 12,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["HSP3U"],
        "description": "This course enables students to analyse the development of individuals across the life span and the dynamic nature of relationships within families and communities.",
    },
    {
        "course_code": "HZB4M",
        "course_name": "Philosophy: Questions and Theories, Grade 12, University/College",
        "subject_area": "Social Sciences and Humanities",
        "grade_level": 12,
        "pathway": "M",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course enables students to acquire an understanding of the nature of philosophy and philosophical reasoning.",
    },

    # ────────── LAW ──────────
    {
        "course_code": "CLU3M",
        "course_name": "Understanding Canadian Law, Grade 11, University/College",
        "subject_area": "Canadian and World Studies",
        "grade_level": 11,
        "pathway": "M",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course explores Canadian law, with a focus on legal theory, legal processes, and factors influencing law.",
    },
    {
        "course_code": "CLN4U",
        "course_name": "Canadian and International Law, Grade 12, University",
        "subject_area": "Canadian and World Studies",
        "grade_level": 12,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": ["CLU3M"],
        "description": "This course explores Canadian and international law. Students will develop an understanding of the principles and sources of law, the processes of legal reasoning, and the roles and responsibilities of citizens.",
    },

    # ────────── MEDIA ARTS ──────────
    {
        "course_code": "ASM1O",
        "course_name": "Media Arts, Grade 9, Open",
        "subject_area": "Arts",
        "grade_level": 9,
        "pathway": "O",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course introduces students to media arts and the variety of tools used to create, analyse, and express ideas using media.",
    },
    {
        "course_code": "ASM2O",
        "course_name": "Media Arts, Grade 10, Open",
        "subject_area": "Arts",
        "grade_level": 10,
        "pathway": "O",
        "is_compulsory": False,
        "prerequisite_codes": ["ASM1O"],
        "description": "This course enables students to extend their understanding and application of media arts.",
    },
    {
        "course_code": "ASM3M",
        "course_name": "Media Arts, Grade 11, University/College",
        "subject_area": "Arts",
        "grade_level": 11,
        "pathway": "M",
        "is_compulsory": False,
        "prerequisite_codes": ["ASM2O"],
        "description": "This course enables students to develop their skills in creating media art works and in analysing media art.",
    },

    # ────────── WORLD HISTORY & GEOGRAPHY (Grade 11-12) ──────────
    {
        "course_code": "CHW3M",
        "course_name": "World History to the End of the Fifteenth Century, Grade 11, University/College",
        "subject_area": "Canadian and World Studies",
        "grade_level": 11,
        "pathway": "M",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course investigates the major civilizations that existed around the world up to the end of the fifteenth century.",
    },
    {
        "course_code": "CHY4U",
        "course_name": "World History Since the Fifteenth Century, Grade 12, University",
        "subject_area": "Canadian and World Studies",
        "grade_level": 12,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course traces the development of the modern world from the fifteenth century to the present.",
    },
    {
        "course_code": "CGW4U",
        "course_name": "World Issues: A Geographic Analysis, Grade 12, University",
        "subject_area": "Canadian and World Studies",
        "grade_level": 12,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course focuses on the geographic dimensions of major global issues.",
    },

    # ────────── TECHNOLOGICAL EDUCATION ──────────
    {
        "course_code": "TTJ1O",
        "course_name": "Exploring Technologies, Grade 9, Open",
        "subject_area": "Technological Education",
        "grade_level": 9,
        "pathway": "O",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course introduces students to a range of technological areas such as communications technology, computer technology, construction technology, green industries, hairstyling, hospitality and tourism, manufacturing technology, and transportation technology.",
    },
    {
        "course_code": "TCJ3C",
        "course_name": "Construction Technology, Grade 11, College",
        "subject_area": "Technological Education",
        "grade_level": 11,
        "pathway": "C",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course introduces students to basic construction technology skills, including blueprint reading, rough and finished carpentry, electrical systems, and plumbing.",
    },
    {
        "course_code": "TMJ3C",
        "course_name": "Manufacturing Technology, Grade 11, College",
        "subject_area": "Technological Education",
        "grade_level": 11,
        "pathway": "C",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course introduces students to key aspects of manufacturing such as computer-aided design and manufacturing (CAD/CAM), precision measurement, and materials processing.",
    },

    # ────────── COOPERATIVE EDUCATION ──────────
    {
        "course_code": "COP1O",
        "course_name": "Co-operative Education, Grade 9–12, Open",
        "subject_area": "Co-operative Education",
        "grade_level": 11,
        "pathway": "O",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This program provides students with the opportunity to relate work experience to their studies and to develop career-related knowledge and skills by working in the community.",
    },

    # ────────── POLITICS & ECONOMICS ──────────
    {
        "course_code": "CPC3O",
        "course_name": "Politics at Work: Navigating Issues in a Diverse World, Grade 11, Open",
        "subject_area": "Canadian and World Studies",
        "grade_level": 11,
        "pathway": "O",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course introduces students to political concepts and skills required to understand and participate in a democratic society.",
    },
    {
        "course_code": "CIA4U",
        "course_name": "Analysing Current Economic Issues, Grade 12, University",
        "subject_area": "Canadian and World Studies",
        "grade_level": 12,
        "pathway": "U",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course examines current economic issues, events, and trends from a variety of perspectives.",
    },

    # ────────── PHYSICAL EDUCATION (SENIOR) ──────────
    {
        "course_code": "PAF4O",
        "course_name": "Fitness and Lifestyle Management, Grade 12, Open",
        "subject_area": "Health and Physical Education",
        "grade_level": 12,
        "pathway": "O",
        "is_compulsory": False,
        "prerequisite_codes": [],
        "description": "This course focuses on the importance of regular physical activity and healthy lifestyle choices for students' well-being throughout their lives.",
    },
]


# ---------------------------------------------------------------------------
# Seed function
# ---------------------------------------------------------------------------

def seed_ontario_data(db: Session) -> None:
    """
    Idempotent seed: insert Ontario boards and OSSD courses if they don't exist.
    Safe to call on every app startup.
    """
    # Check if already seeded
    existing_board_count = db.query(OntarioBoard).count()
    if existing_board_count > 0:
        logger.debug("Ontario boards already seeded — skipping")
        return

    logger.info("Seeding Ontario school boards and OSSD course catalog...")

    # Insert boards
    for board_data in BOARDS:
        board = OntarioBoard(
            code=board_data["code"],
            name=board_data["name"],
            region=board_data.get("region"),
            website_url=board_data.get("website_url"),
            is_active=True,
        )
        db.add(board)

    try:
        db.commit()
        logger.info("Seeded %d Ontario boards", len(BOARDS))
    except Exception as exc:
        db.rollback()
        logger.error("Failed to seed Ontario boards: %s", exc)
        return

    # Insert courses (all universal: board_id=None)
    inserted = 0
    for course_data in COURSES:
        # Check-before-insert for idempotency (in case of partial seed)
        existing = (
            db.query(CourseCatalogItem)
            .filter(
                CourseCatalogItem.course_code == course_data["course_code"],
                CourseCatalogItem.board_id == None,  # noqa: E711
            )
            .first()
        )
        if existing:
            continue

        course = CourseCatalogItem(
            board_id=None,  # Universal — available to all boards
            course_code=course_data["course_code"],
            course_name=course_data["course_name"],
            subject_area=course_data["subject_area"],
            grade_level=course_data["grade_level"],
            pathway=course_data.get("pathway", "O"),
            credit_value=course_data.get("credit_value", 1.0),
            is_compulsory=course_data.get("is_compulsory", False),
            compulsory_category=course_data.get("compulsory_category"),
            prerequisite_codes=course_data.get("prerequisite_codes") or [],
            description=course_data.get("description"),
            is_ib=course_data.get("is_ib", False),
            is_ap=course_data.get("is_ap", False),
            is_shsm=course_data.get("is_shsm", False),
        )
        db.add(course)
        inserted += 1

    try:
        db.commit()
        logger.info("Seeded %d OSSD courses in the course catalog", inserted)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to seed OSSD courses: %s", exc)
