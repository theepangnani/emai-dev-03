"""
Ontario curriculum expectations seed data (#571).

Provides seed_curriculum_data(db) which is idempotent (safe to call on every startup).
Seeds ~120 realistic Ontario curriculum expectations across 5 core OSSD courses:
  - MCR3U  Functions (Grade 11)
  - MHF4U  Advanced Functions (Grade 12)
  - ENG3U  English (Grade 11)
  - SBI3U  Biology (Grade 11)
  - CHC2D  Canadian History (Grade 10)
"""
import logging
from sqlalchemy.orm import Session

from app.models.curriculum import CurriculumExpectation

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Expectation definitions
# ---------------------------------------------------------------------------

EXPECTATIONS = [
    # -----------------------------------------------------------------------
    # MCR3U — Functions, Grade 11 (University)
    # -----------------------------------------------------------------------

    # Strand A: Characteristics of Functions
    dict(course_code="MCR3U", grade_level=11, strand="A: Characteristics of Functions",
         expectation_code="A1", description="Demonstrate an understanding of functions, their representations, and their inverses, and make connections between the algebraic and graphical representations of functions using transformations.", expectation_type="overall"),
    dict(course_code="MCR3U", grade_level=11, strand="A: Characteristics of Functions",
         expectation_code="A1.1", description="Explain the meaning of the term function, and distinguish a function from a relation that is not a function, by using examples drawn from ordered pairs, graphs, equations, and descriptions of practical situations.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="A: Characteristics of Functions",
         expectation_code="A1.2", description="Represent a function numerically (table of values), graphically (mapping diagram, graph), and algebraically; write the equation or rule of a function given its graph or a table of values.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="A: Characteristics of Functions",
         expectation_code="A1.3", description="Explain the meaning of the terms domain and range for a function, determine the domain and range of a function from its graph, and state the domain and range using set notation.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="A: Characteristics of Functions",
         expectation_code="A1.4", description="Identify and describe key features of the graph of a function by using the terminology: domain, range, x- and y-intercepts, maximum and minimum values, intervals of increase and decrease, symmetry.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="A: Characteristics of Functions",
         expectation_code="A2", description="Determine the zeros and the maximum or minimum of a quadratic function, and solve problems involving quadratic functions, including those arising from real-world applications.", expectation_type="overall"),
    dict(course_code="MCR3U", grade_level=11, strand="A: Characteristics of Functions",
         expectation_code="A2.1", description="Determine the number of zeros (x-intercepts) of a quadratic function, using a variety of strategies; determine the zeros of a quadratic function, using a variety of strategies.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="A: Characteristics of Functions",
         expectation_code="A2.2", description="Determine the maximum or minimum value of a quadratic function whose equation is given in vertex form or in standard form, using an algebraic or graphical approach.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="A: Characteristics of Functions",
         expectation_code="A3.1", description="Determine, through investigation using technology, the roles of the parameters a, k, d, and c in functions of the form y = af(k(x − d)) + c, and describe these roles in terms of transformations on the graph of f(x).", expectation_type="specific"),

    # Strand B: Exponential Functions
    dict(course_code="MCR3U", grade_level=11, strand="B: Exponential Functions",
         expectation_code="B1", description="Demonstrate an understanding of the exponent rules of multiplication and division, and apply them to simplify expressions; connect exponential representations to logarithmic notation.", expectation_type="overall"),
    dict(course_code="MCR3U", grade_level=11, strand="B: Exponential Functions",
         expectation_code="B1.1", description="Graph, with and without technology, an exponential relation, given its equation in the form y = a^x (a > 0, a ≠ 1), define the exponential function, and explain its key features.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="B: Exponential Functions",
         expectation_code="B1.2", description="Determine, through investigation, using a variety of tools and strategies, the exponential function and the laws of exponents for any real exponent.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="B: Exponential Functions",
         expectation_code="B2.1", description="Collect data that can be modelled as an exponential function, through investigation with and without technology, from primary sources, using a variety of tools, or from secondary sources, and graph the data.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="B: Exponential Functions",
         expectation_code="B2.2", description="Identify exponential functions, including those that arise from real-world applications involving growth and decay, given various representations, and explain any restrictions on the domain and range.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="B: Exponential Functions",
         expectation_code="B3.1", description="Pose and solve problems related to models of exponential functions drawn from a variety of applications, and communicate the solutions with clarity and justification.", expectation_type="specific"),

    # Strand C: Discrete Functions
    dict(course_code="MCR3U", grade_level=11, strand="C: Discrete Functions",
         expectation_code="C1", description="Demonstrate an understanding of recursive sequences, represent recursive sequences in a variety of ways, and make connections to Pascal's triangle.", expectation_type="overall"),
    dict(course_code="MCR3U", grade_level=11, strand="C: Discrete Functions",
         expectation_code="C1.1", description="Make connections between sequences and discrete functions, represent sequences using function notation, and distinguish between a discrete function and a continuous function.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="C: Discrete Functions",
         expectation_code="C1.2", description="Determine and describe a recursive procedure for generating a sequence, given the initial conditions and the general term.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="C: Discrete Functions",
         expectation_code="C2.1", description="Identify sequences as arithmetic, geometric, or neither, given a numeric or algebraic representation.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="C: Discrete Functions",
         expectation_code="C2.2", description="Determine the formula for the general term of an arithmetic or geometric sequence, through investigation using a variety of tools, and apply the formula to calculate any term in a sequence.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="C: Discrete Functions",
         expectation_code="C3.1", description="Connect the formula for the nth term of a geometric series to the process of adding the terms using a finite geometric series, and apply to solve related problems.", expectation_type="specific"),

    # Strand D: Trigonometric Functions
    dict(course_code="MCR3U", grade_level=11, strand="D: Trigonometric Functions",
         expectation_code="D1", description="Demonstrate an understanding of the meaning and application of radian measure; make connections between radian measure and degree measure.", expectation_type="overall"),
    dict(course_code="MCR3U", grade_level=11, strand="D: Trigonometric Functions",
         expectation_code="D1.1", description="Demonstrate an understanding of the meaning and application of radian measure; convert between radian measure and degree measure.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="D: Trigonometric Functions",
         expectation_code="D1.2", description="Determine, with technology, the primary trigonometric ratios and the reciprocal trigonometric ratios of angles expressed in radian measure.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="D: Trigonometric Functions",
         expectation_code="D2.1", description="Sketch the graphs of f(x) = sin x and f(x) = cos x for angle measures expressed in radians, and determine and describe their key properties.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="D: Trigonometric Functions",
         expectation_code="D2.2", description="Make connections between the tangent ratio and the sine and cosine ratios, graph the function f(x) = tan x, and determine and describe its key properties.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="D: Trigonometric Functions",
         expectation_code="D3.1", description="Collect data that can be modelled as a sinusoidal function, through investigation with and without technology, from primary sources, using a variety of tools, and graph the data.", expectation_type="specific"),
    dict(course_code="MCR3U", grade_level=11, strand="D: Trigonometric Functions",
         expectation_code="D3.2", description="Identify sinusoidal functions, including those that arise from real-world applications involving periodic phenomena, given various representations, and explain any restrictions on the domain and range.", expectation_type="specific"),

    # -----------------------------------------------------------------------
    # MHF4U — Advanced Functions, Grade 12 (University)
    # -----------------------------------------------------------------------

    # Strand A: Exponential and Logarithmic Functions
    dict(course_code="MHF4U", grade_level=12, strand="A: Exponential and Logarithmic Functions",
         expectation_code="A1", description="Demonstrate an understanding of the relationship between exponential expressions and logarithmic expressions, evaluate logarithms, and apply the laws of logarithms to simplify numeric expressions.", expectation_type="overall"),
    dict(course_code="MHF4U", grade_level=12, strand="A: Exponential and Logarithmic Functions",
         expectation_code="A1.1", description="Recognize the logarithm of a number to a given base as the exponent to which the base must be raised to get the number, and evaluate common logarithms and natural logarithms using a scientific calculator.", expectation_type="specific"),
    dict(course_code="MHF4U", grade_level=12, strand="A: Exponential and Logarithmic Functions",
         expectation_code="A1.2", description="Determine, with technology, the approximate logarithm of a number to any base, including base 10 and base e.", expectation_type="specific"),
    dict(course_code="MHF4U", grade_level=12, strand="A: Exponential and Logarithmic Functions",
         expectation_code="A2.1", description="Recognize exponential functions and logarithmic functions, make connections between the two functions, and use the inverse relationship to solve exponential and logarithmic equations.", expectation_type="specific"),
    dict(course_code="MHF4U", grade_level=12, strand="A: Exponential and Logarithmic Functions",
         expectation_code="A2.2", description="Solve problems involving exponential and logarithmic functions drawn from a variety of applications, and communicate the solutions with clarity and justification.", expectation_type="specific"),
    dict(course_code="MHF4U", grade_level=12, strand="A: Exponential and Logarithmic Functions",
         expectation_code="A3.1", description="Determine the derivative of exponential functions using first principles, and apply the chain rule and other differentiation rules to determine derivatives involving exponential functions.", expectation_type="specific"),

    # Strand B: Trigonometric Functions
    dict(course_code="MHF4U", grade_level=12, strand="B: Trigonometric Functions",
         expectation_code="B1", description="Demonstrate an understanding of the meaning and application of radian measure; determine the exact values of trigonometric ratios for special angles, and use the reciprocal trigonometric ratios.", expectation_type="overall"),
    dict(course_code="MHF4U", grade_level=12, strand="B: Trigonometric Functions",
         expectation_code="B1.1", description="Recognize equivalent trigonometric expressions, and verify equivalences using graphing technology.", expectation_type="specific"),
    dict(course_code="MHF4U", grade_level=12, strand="B: Trigonometric Functions",
         expectation_code="B2.1", description="Prove trigonometric identities, including those involving the sum and difference formulas for sine and cosine, double-angle formulas, and the identities sin²x + cos²x = 1.", expectation_type="specific"),
    dict(course_code="MHF4U", grade_level=12, strand="B: Trigonometric Functions",
         expectation_code="B2.2", description="Solve linear and quadratic trigonometric equations for the domain of all real numbers and for a restricted domain, and explain the solutions with reference to the unit circle.", expectation_type="specific"),
    dict(course_code="MHF4U", grade_level=12, strand="B: Trigonometric Functions",
         expectation_code="B3.1", description="Recognize sinusoidal functions arising from real-world applications and model them using function notation; determine and interpret key properties in context.", expectation_type="specific"),

    # Strand C: Polynomial and Rational Functions
    dict(course_code="MHF4U", grade_level=12, strand="C: Polynomial and Rational Functions",
         expectation_code="C1", description="Identify and describe some key features of polynomial functions, and make connections between the numeric, graphical, and algebraic representations of polynomial functions.", expectation_type="overall"),
    dict(course_code="MHF4U", grade_level=12, strand="C: Polynomial and Rational Functions",
         expectation_code="C1.1", description="Recognize a polynomial expression and the equation of a polynomial function, give reasons why it is a function, and identify the degree and the leading coefficient of the polynomial.", expectation_type="specific"),
    dict(course_code="MHF4U", grade_level=12, strand="C: Polynomial and Rational Functions",
         expectation_code="C1.2", description="Compare, through investigation using graphing technology, the numeric, graphical, and algebraic representations of polynomial functions.", expectation_type="specific"),
    dict(course_code="MHF4U", grade_level=12, strand="C: Polynomial and Rational Functions",
         expectation_code="C2.1", description="Determine, through investigation using technology, the roles of the parameters a, k, d, and c in functions of the form y = af(k(x − d)) + c, and describe these roles in terms of transformations on the graph of f(x).", expectation_type="specific"),
    dict(course_code="MHF4U", grade_level=12, strand="C: Polynomial and Rational Functions",
         expectation_code="C3.1", description="Identify key features of the graphs of rational functions, including horizontal and vertical asymptotes, and make connections between the algebraic and graphical representations of rational functions.", expectation_type="specific"),
    dict(course_code="MHF4U", grade_level=12, strand="C: Polynomial and Rational Functions",
         expectation_code="C3.2", description="Determine, through investigation, connections between the graphs of rational functions and the graphs of their component polynomial functions.", expectation_type="specific"),

    # Strand D: Characteristics of Functions
    dict(course_code="MHF4U", grade_level=12, strand="D: Characteristics of Functions",
         expectation_code="D1", description="Demonstrate an understanding of average and instantaneous rate of change, and determine, numerically and graphically, and interpret the average rate of change of a function over a given interval.", expectation_type="overall"),
    dict(course_code="MHF4U", grade_level=12, strand="D: Characteristics of Functions",
         expectation_code="D1.1", description="Gather, interpret, and describe information about real-world applications of rates of change, and recognize different ways in which rate of change is communicated.", expectation_type="specific"),
    dict(course_code="MHF4U", grade_level=12, strand="D: Characteristics of Functions",
         expectation_code="D1.2", description="Determine, through investigation, connections between the slope of a secant on the graph of a function and the average rate of change of the function over an interval.", expectation_type="specific"),
    dict(course_code="MHF4U", grade_level=12, strand="D: Characteristics of Functions",
         expectation_code="D2.1", description="Determine, through investigation using various tools and strategies, the instantaneous rate of change of a function at a given value, using the slopes of secants through the given point.", expectation_type="specific"),
    dict(course_code="MHF4U", grade_level=12, strand="D: Characteristics of Functions",
         expectation_code="D3.1", description="Combine two or more functions using operations (addition, subtraction, multiplication, division), and determine the key features of the resulting function.", expectation_type="specific"),

    # -----------------------------------------------------------------------
    # ENG3U — English, Grade 11 (University)
    # -----------------------------------------------------------------------

    # Strand A: Oral Communication
    dict(course_code="ENG3U", grade_level=11, strand="A: Oral Communication",
         expectation_code="A1", description="Listen in order to understand and respond appropriately in a variety of situations for a variety of purposes.", expectation_type="overall"),
    dict(course_code="ENG3U", grade_level=11, strand="A: Oral Communication",
         expectation_code="A1.1", description="Identify a variety of listening strategies and use them appropriately before, during, and after listening in order to understand and interpret texts.", expectation_type="specific"),
    dict(course_code="ENG3U", grade_level=11, strand="A: Oral Communication",
         expectation_code="A1.2", description="Demonstrate an understanding of appropriate listening behaviour by adapting active listening strategies to suit a range of situations, including work in groups.", expectation_type="specific"),
    dict(course_code="ENG3U", grade_level=11, strand="A: Oral Communication",
         expectation_code="A2.1", description="Use oral communication skills to communicate complex ideas and information clearly and coherently for a variety of purposes and audiences.", expectation_type="specific"),
    dict(course_code="ENG3U", grade_level=11, strand="A: Oral Communication",
         expectation_code="A2.2", description="Identify a variety of presentation techniques, and use them appropriately and effectively to engage an audience.", expectation_type="specific"),

    # Strand B: Reading and Literature Studies
    dict(course_code="ENG3U", grade_level=11, strand="B: Reading and Literature Studies",
         expectation_code="B1", description="Read and demonstrate an understanding of a variety of literary, informational, and graphic texts, using a range of strategies to construct meaning.", expectation_type="overall"),
    dict(course_code="ENG3U", grade_level=11, strand="B: Reading and Literature Studies",
         expectation_code="B1.1", description="Identify a variety of reading comprehension strategies and use them appropriately before, during, and after reading to understand texts.", expectation_type="specific"),
    dict(course_code="ENG3U", grade_level=11, strand="B: Reading and Literature Studies",
         expectation_code="B2.1", description="Analyse texts in terms of the information, ideas, issues, or themes they explore, examining how various aspects of the texts contribute to the presentation or development of these elements.", expectation_type="specific"),
    dict(course_code="ENG3U", grade_level=11, strand="B: Reading and Literature Studies",
         expectation_code="B2.2", description="Analyse the way that works in various genres and traditions use literary devices, forms, and stylistic elements to create meaning.", expectation_type="specific"),
    dict(course_code="ENG3U", grade_level=11, strand="B: Reading and Literature Studies",
         expectation_code="B3.1", description="Demonstrate critical thinking by identifying and examining the perspectives and/or biases found in texts and assessing the validity and credibility of information.", expectation_type="specific"),
    dict(course_code="ENG3U", grade_level=11, strand="B: Reading and Literature Studies",
         expectation_code="B4.1", description="Identify a variety of text forms, text features, and stylistic elements and explain how they help communicate meaning.", expectation_type="specific"),

    # Strand C: Writing
    dict(course_code="ENG3U", grade_level=11, strand="C: Writing",
         expectation_code="C1", description="Generate, gather, and organize ideas and information to write for an intended purpose and audience.", expectation_type="overall"),
    dict(course_code="ENG3U", grade_level=11, strand="C: Writing",
         expectation_code="C1.1", description="Identify the topic, purpose, and audience for a variety of writing tasks; understand how context and constraints shape the writing process.", expectation_type="specific"),
    dict(course_code="ENG3U", grade_level=11, strand="C: Writing",
         expectation_code="C2.1", description="Write for different purposes and audiences using a variety of literary, informational, and graphic forms; apply the appropriate form, voice, and register for the context.", expectation_type="specific"),
    dict(course_code="ENG3U", grade_level=11, strand="C: Writing",
         expectation_code="C3.1", description="Use a variety of sentence structures and techniques, including rhetorical devices, to make writing clear, correct, and engaging for the intended audience.", expectation_type="specific"),
    dict(course_code="ENG3U", grade_level=11, strand="C: Writing",
         expectation_code="C4.1", description="Apply knowledge of grammar and usage conventions to write accurately and in a style appropriate to the purpose and audience.", expectation_type="specific"),

    # Strand D: Media Studies
    dict(course_code="ENG3U", grade_level=11, strand="D: Media Studies",
         expectation_code="D1", description="Demonstrate an understanding of a variety of media texts.", expectation_type="overall"),
    dict(course_code="ENG3U", grade_level=11, strand="D: Media Studies",
         expectation_code="D1.1", description="Explain how a variety of factors, including the economic, social, historical, and political contexts, may affect a media producer's choice of content and form.", expectation_type="specific"),
    dict(course_code="ENG3U", grade_level=11, strand="D: Media Studies",
         expectation_code="D2.1", description="Identify the conventions and techniques used in a variety of media forms and explain how they help convey meaning.", expectation_type="specific"),
    dict(course_code="ENG3U", grade_level=11, strand="D: Media Studies",
         expectation_code="D3.1", description="Create media texts for different purposes and audiences, using appropriate forms, conventions, and techniques.", expectation_type="specific"),

    # -----------------------------------------------------------------------
    # SBI3U — Biology, Grade 11 (University)
    # -----------------------------------------------------------------------

    # Strand A: Scientific Investigation Skills and Career Exploration
    dict(course_code="SBI3U", grade_level=11, strand="A: Scientific Investigation Skills",
         expectation_code="A1", description="Demonstrate scientific investigation skills (related to both inquiry and research) in the four areas of skills: initiating and planning, performing and recording, analysing and interpreting, and communicating.", expectation_type="overall"),
    dict(course_code="SBI3U", grade_level=11, strand="A: Scientific Investigation Skills",
         expectation_code="A1.1", description="Formulate relevant scientific questions about observed relationships, ideas, problems, or issues, make informed predictions, and/or formulate educated hypotheses to focus inquiries or research.", expectation_type="specific"),
    dict(course_code="SBI3U", grade_level=11, strand="A: Scientific Investigation Skills",
         expectation_code="A1.2", description="Identify scientific questions that can be investigated, and identify issues, events, or problems that are best addressed through other means, including other subject areas.", expectation_type="specific"),
    dict(course_code="SBI3U", grade_level=11, strand="A: Scientific Investigation Skills",
         expectation_code="A2.1", description="Perform investigations safely, accurately, and with skill, following the instructions and recommendations of the laboratory or field protocols.", expectation_type="specific"),

    # Strand B: Diversity of Living Things
    dict(course_code="SBI3U", grade_level=11, strand="B: Diversity of Living Things",
         expectation_code="B1", description="Analyse the economic and environmental advantages and disadvantages of the use of microorganisms by humans.", expectation_type="overall"),
    dict(course_code="SBI3U", grade_level=11, strand="B: Diversity of Living Things",
         expectation_code="B2.1", description="Investigate the structures and functions of the components of cells and explain how these components contribute to cell processes such as growth, division, and reproduction.", expectation_type="specific"),
    dict(course_code="SBI3U", grade_level=11, strand="B: Diversity of Living Things",
         expectation_code="B3.1", description="Describe the major features used to classify organisms in the three domains and six kingdoms, and apply the Linnaean classification system to classify organisms.", expectation_type="specific"),
    dict(course_code="SBI3U", grade_level=11, strand="B: Diversity of Living Things",
         expectation_code="B3.2", description="Describe the distinguishing characteristics of organisms in the six kingdoms and explain how their characteristics determine their roles in various ecosystems.", expectation_type="specific"),

    # Strand C: Evolution
    dict(course_code="SBI3U", grade_level=11, strand="C: Evolution",
         expectation_code="C1", description="Analyse the economic and environmental costs and benefits of technologies and processes that involve the application of concepts related to evolution.", expectation_type="overall"),
    dict(course_code="SBI3U", grade_level=11, strand="C: Evolution",
         expectation_code="C2.1", description="Investigate evolutionary processes and the evidence for evolution using observational data and fossil records.", expectation_type="specific"),
    dict(course_code="SBI3U", grade_level=11, strand="C: Evolution",
         expectation_code="C3.1", description="Explain the theory of evolution by natural selection, using the evidence from various fields of study that supports the theory.", expectation_type="specific"),
    dict(course_code="SBI3U", grade_level=11, strand="C: Evolution",
         expectation_code="C3.2", description="Describe the mechanisms by which new species arise, including natural selection, genetic drift, founder effects, and reproductive isolation.", expectation_type="specific"),

    # Strand D: Genetic Processes
    dict(course_code="SBI3U", grade_level=11, strand="D: Genetic Processes",
         expectation_code="D1", description="Analyse societal issues, and ethical and legal implications related to genetic technologies.", expectation_type="overall"),
    dict(course_code="SBI3U", grade_level=11, strand="D: Genetic Processes",
         expectation_code="D2.1", description="Investigate the processes of mitosis and meiosis and explain how errors in these processes can lead to genetic mutations and diseases.", expectation_type="specific"),
    dict(course_code="SBI3U", grade_level=11, strand="D: Genetic Processes",
         expectation_code="D3.1", description="Explain the concepts of heredity, including dominance/recessiveness, incomplete dominance, co-dominance, multiple alleles, and polygenic inheritance.", expectation_type="specific"),
    dict(course_code="SBI3U", grade_level=11, strand="D: Genetic Processes",
         expectation_code="D3.2", description="Explain, using Punnett squares and pedigree charts, how genetic traits are transmitted and predict the probability of specific traits appearing in offspring.", expectation_type="specific"),
    dict(course_code="SBI3U", grade_level=11, strand="D: Genetic Processes",
         expectation_code="D3.3", description="Describe the structure of DNA and explain the processes of DNA replication, transcription, and translation, and their roles in cell function.", expectation_type="specific"),

    # Strand E: Animals: Structure and Function
    dict(course_code="SBI3U", grade_level=11, strand="E: Animals: Structure and Function",
         expectation_code="E1", description="Analyse the relationships between the functional requirements of animals and the structures that have evolved to fulfil those requirements.", expectation_type="overall"),
    dict(course_code="SBI3U", grade_level=11, strand="E: Animals: Structure and Function",
         expectation_code="E2.1", description="Investigate the interdependence of the structures and functions of the major organ systems in animals, and describe how body systems contribute to maintaining homeostasis.", expectation_type="specific"),
    dict(course_code="SBI3U", grade_level=11, strand="E: Animals: Structure and Function",
         expectation_code="E3.1", description="Explain the major processes that occur in the digestive, circulatory, respiratory, nervous, endocrine, immune, and reproductive systems of animals.", expectation_type="specific"),

    # Strand F: Plants: Anatomy, Growth, and Function
    dict(course_code="SBI3U", grade_level=11, strand="F: Plants: Anatomy, Growth, and Function",
         expectation_code="F1", description="Analyse the relationships between the functional requirements of plants and the structures that have evolved to fulfil those requirements.", expectation_type="overall"),
    dict(course_code="SBI3U", grade_level=11, strand="F: Plants: Anatomy, Growth, and Function",
         expectation_code="F2.1", description="Investigate the structures and functions of plant tissues and organs and explain how they contribute to the processes of plant growth, photosynthesis, gas exchange, and transport.", expectation_type="specific"),
    dict(course_code="SBI3U", grade_level=11, strand="F: Plants: Anatomy, Growth, and Function",
         expectation_code="F3.1", description="Explain the processes of photosynthesis and cellular respiration in plants, and describe the roles of chloroplasts and mitochondria in these processes.", expectation_type="specific"),
    dict(course_code="SBI3U", grade_level=11, strand="F: Plants: Anatomy, Growth, and Function",
         expectation_code="F3.2", description="Describe the mechanisms by which plants respond to environmental stimuli, including the roles of plant hormones (auxins, gibberellins, cytokinins, abscisic acid, ethylene).", expectation_type="specific"),

    # -----------------------------------------------------------------------
    # CHC2D — Canadian History Since World War I, Grade 10 (Applied)
    # -----------------------------------------------------------------------

    # Strand A: Communities: Local, National, and Global Connections
    dict(course_code="CHC2D", grade_level=10, strand="A: Communities: Local, National, and Global Connections",
         expectation_code="A1", description="Analyse contributions of various individuals and groups to Canadian identity and heritage since the First World War.", expectation_type="overall"),
    dict(course_code="CHC2D", grade_level=10, strand="A: Communities: Local, National, and Global Connections",
         expectation_code="A1.1", description="Demonstrate an understanding of the contributions of individuals and groups, including Aboriginal peoples, to the building of Canadian society since 1914.", expectation_type="specific"),
    dict(course_code="CHC2D", grade_level=10, strand="A: Communities: Local, National, and Global Connections",
         expectation_code="A1.2", description="Explain how key events, developments, and individuals have shaped the identity of various communities in Canada since 1914.", expectation_type="specific"),
    dict(course_code="CHC2D", grade_level=10, strand="A: Communities: Local, National, and Global Connections",
         expectation_code="A2.1", description="Describe the experiences of various groups in Canada during periods of war and explain how these experiences contributed to Canada's national identity.", expectation_type="specific"),
    dict(course_code="CHC2D", grade_level=10, strand="A: Communities: Local, National, and Global Connections",
         expectation_code="A3.1", description="Analyse the impact of immigration and cultural diversity on Canadian society since 1914, and explain the role of multiculturalism in shaping Canadian identity.", expectation_type="specific"),
    dict(course_code="CHC2D", grade_level=10, strand="A: Communities: Local, National, and Global Connections",
         expectation_code="A3.2", description="Describe the role of French-English relations in the development of Canadian identity and the evolution of Quebec as a distinct society within Canada.", expectation_type="specific"),

    # Strand B: Change and Continuity
    dict(course_code="CHC2D", grade_level=10, strand="B: Change and Continuity",
         expectation_code="B1", description="Analyse significant turning points in Canadian history since the First World War, and assess their significance to the development of Canadian society.", expectation_type="overall"),
    dict(course_code="CHC2D", grade_level=10, strand="B: Change and Continuity",
         expectation_code="B1.1", description="Describe the major political, social, and economic changes in Canada since 1914, and explain how these changes have shaped modern Canadian society.", expectation_type="specific"),
    dict(course_code="CHC2D", grade_level=10, strand="B: Change and Continuity",
         expectation_code="B2.1", description="Analyse the effects of the First World War on Canadian society and explain how the war contributed to Canada's emerging sense of nationhood.", expectation_type="specific"),
    dict(course_code="CHC2D", grade_level=10, strand="B: Change and Continuity",
         expectation_code="B2.2", description="Describe the causes and consequences of the Great Depression in Canada and explain its lasting effects on Canadian society and government policy.", expectation_type="specific"),
    dict(course_code="CHC2D", grade_level=10, strand="B: Change and Continuity",
         expectation_code="B3.1", description="Analyse the impact of the Second World War on Canada, including Canada's role in the war effort, the home front experience, and the post-war changes in Canadian society.", expectation_type="specific"),
    dict(course_code="CHC2D", grade_level=10, strand="B: Change and Continuity",
         expectation_code="B3.2", description="Describe the major social, political, and economic developments in Canada in the post-war period (1945–1970), including the baby boom, suburbanization, and the rise of the welfare state.", expectation_type="specific"),
    dict(course_code="CHC2D", grade_level=10, strand="B: Change and Continuity",
         expectation_code="B4.1", description="Analyse key political and social developments in Canada from the 1970s to the present, including the patriation of the Constitution, the Charter of Rights and Freedoms, and changing political landscapes.", expectation_type="specific"),

    # Strand C: Conflict and Cooperation
    dict(course_code="CHC2D", grade_level=10, strand="C: Conflict and Cooperation",
         expectation_code="C1", description="Analyse the causes of key conflicts involving Canada and explain how they have shaped Canadian foreign policy and Canada's role in international affairs.", expectation_type="overall"),
    dict(course_code="CHC2D", grade_level=10, strand="C: Conflict and Cooperation",
         expectation_code="C1.1", description="Analyse the causes and consequences of Canada's involvement in major conflicts since 1914, including the First and Second World Wars, the Korean War, and peacekeeping missions.", expectation_type="specific"),
    dict(course_code="CHC2D", grade_level=10, strand="C: Conflict and Cooperation",
         expectation_code="C2.1", description="Describe Canada's role in international organizations and peacekeeping efforts, and explain how these activities have shaped Canada's international reputation.", expectation_type="specific"),
    dict(course_code="CHC2D", grade_level=10, strand="C: Conflict and Cooperation",
         expectation_code="C2.2", description="Analyse the impact of Canadian foreign policy decisions on Canada's relationships with other nations, and evaluate the effectiveness of these policies.", expectation_type="specific"),
    dict(course_code="CHC2D", grade_level=10, strand="C: Conflict and Cooperation",
         expectation_code="C3.1", description="Explain the significance of the Cold War for Canada, including Canada's role in NATO and NORAD, and describe the social and political effects of Cold War tensions on Canadian society.", expectation_type="specific"),
]


def seed_curriculum_data(db: Session) -> None:
    """Seed Ontario curriculum expectations (idempotent)."""
    # Check if already seeded by looking for any existing record
    existing = db.query(CurriculumExpectation).first()
    if existing:
        return  # Already seeded

    logger.info("Seeding Ontario curriculum expectations (#571)...")
    count = 0
    for record in EXPECTATIONS:
        expectation = CurriculumExpectation(**record)
        db.add(expectation)
        count += 1

    try:
        db.commit()
        logger.info("Seeded %d Ontario curriculum expectations across %d courses",
                    count,
                    len({r["course_code"] for r in EXPECTATIONS}))
    except Exception as exc:
        db.rollback()
        logger.error("Failed to seed curriculum expectations: %s", exc)
        raise
