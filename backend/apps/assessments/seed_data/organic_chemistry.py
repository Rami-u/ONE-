"""Plain seed data for the demo chemistry workspace. Lists and dicts only."""

COURSE = {
    "title": "Organic Chemistry 101",
    "description": "Introduction to hydrocarbons and aromatic compounds.",
}

SECTIONS = [
    {"title": "Aliphatic hydrocarbons", "position": 1},
    {"title": "Aromatic hydrocarbons", "position": 2},
]

# section = index into SECTIONS
LESSONS = [
    {"title": "Alkanes and alkenes", "section": 0, "position": 1,
     "content": "Saturated and unsaturated hydrocarbons and their naming."},
    {"title": "Aromatic compounds: benzene", "section": 1, "position": 2,
     "content": "Structure of benzene, resonance and aromaticity."},
    {"title": "Reactions of benzene", "section": 1, "position": 3,
     "content": "Electrophilic aromatic substitution."},
    {"title": "IUPAC nomenclature", "section": 0, "position": 4,
     "content": "Naming organic compounds systematically."},
]

# lesson = index into LESSONS
TOPICS = [
    {"name": "Alkanes", "slug": "alkanes", "lesson": 0},
    {"name": "Alkenes", "slug": "alkenes", "lesson": 0},
    {"name": "Benzene structure", "slug": "benzene-structure", "lesson": 1},
    {"name": "Aromaticity (Hueckel rule)", "slug": "aromaticity", "lesson": 1},
    {"name": "Substitution reactions", "slug": "substitution-reactions", "lesson": 2},
    {"name": "Nomenclature", "slug": "nomenclature", "lesson": 3},
]


def _mcq(topic, stem, options, correct, explanation, difficulty="medium", points="1.00"):
    return {
        "topic": topic,
        "question_type": "mcq",
        "stem": stem,
        "options": [{"id": key, "text": text} for key, text in options],
        "correct_answer": correct,
        "explanation": explanation,
        "difficulty": difficulty,
        "points": points,
    }


def _tf(topic, stem, correct, explanation, difficulty="easy", points="1.00"):
    return {
        "topic": topic,
        "question_type": "true_false",
        "stem": stem,
        "options": None,
        "correct_answer": correct,
        "explanation": explanation,
        "difficulty": difficulty,
        "points": points,
    }


def _short(topic, stem, answers, explanation, difficulty="medium", points="2.00"):
    return {
        "topic": topic,
        "question_type": "short",
        "stem": stem,
        "options": None,
        "correct_answer": answers,
        "explanation": explanation,
        "difficulty": difficulty,
        "points": points,
    }


def _essay(topic, stem, rubric, explanation, difficulty="hard", points="5.00"):
    return {
        "topic": topic,
        "question_type": "essay",
        "stem": stem,
        "options": None,
        "correct_answer": rubric,
        "explanation": explanation,
        "difficulty": difficulty,
        "points": points,
    }


QUESTIONS = [
    # ---- alkanes (0-3)
    _mcq("alkanes", "What is the general formula of alkanes?",
         [("a", "CnH2n+2"), ("b", "CnH2n"), ("c", "CnH2n-2"), ("d", "CnHn")], "a",
         "Alkanes are saturated, so they follow CnH2n+2.", "easy"),
    _tf("alkanes", "Methane is the simplest alkane.", True,
        "Methane (CH4) has a single carbon atom."),
    _short("alkanes", "Name the alkane with three carbon atoms.", ["propane"],
           "Prop- means three carbons and -ane means alkane.", "easy"),
    _mcq("alkanes", "Which reaction is typical for alkanes?",
         [("a", "Addition"), ("b", "Free radical substitution"),
          ("c", "Electrophilic addition"), ("d", "Polymerisation")], "b",
         "Alkanes have only single bonds, so they react by radical substitution.", "medium"),
    # ---- alkenes (4-7)
    _mcq("alkenes", "Which functional group do alkenes contain?",
         [("a", "C-C single bond"), ("b", "C=C double bond"),
          ("c", "C-O bond"), ("d", "C-triple-C bond")], "b",
         "Alkenes contain at least one carbon-carbon double bond.", "easy"),
    _tf("alkenes", "Alkenes mainly undergo addition reactions.", True,
        "The pi bond is easily broken, which allows addition.", "medium"),
    _short("alkenes", "What is the formula of ethene?", ["c2h4"],
           "Ethene has two carbons and follows CnH2n.", "medium"),
    _mcq("alkenes", "Which reagent is used to test for a C=C double bond?",
         [("a", "Bromine water"), ("b", "Limewater"),
          ("c", "Litmus paper"), ("d", "Silver nitrate")], "a",
         "Bromine water is decolourised by alkenes.", "medium"),
    # ---- nomenclature (8-11)
    _mcq("nomenclature", "What is the IUPAC name of CH3CH2CH2CH3?",
         [("a", "Propane"), ("b", "Butane"), ("c", "Pentane"), ("d", "Ethane")], "b",
         "Four carbons in a chain give butane.", "easy"),
    _tf("nomenclature", "In IUPAC naming the longest carbon chain gives the parent name.", True,
        "The parent chain is the longest continuous chain."),
    _short("nomenclature", "What prefix means five carbon atoms?", ["pent", "pent-"],
           "Pent- is the prefix for five carbons.", "easy"),
    _mcq("nomenclature", "What is the name of a two carbon alkene?",
         [("a", "Ethane"), ("b", "Ethene"), ("c", "Ethyne"), ("d", "Methene")], "b",
         "Two carbons plus a double bond gives ethene.", "medium"),
    # ---- benzene-structure (12-15)
    _mcq("benzene-structure", "Which molecular formula corresponds to benzene?",
         [("a", "C6H12"), ("b", "C6H6"), ("c", "C6H14"), ("d", "C5H6")], "b",
         "Benzene is C6H6 with a planar ring of six carbons.", "easy"),
    _tf("benzene-structure", "All carbon-carbon bonds in benzene have the same length.", True,
        "Delocalised electrons make every C-C bond equal.", "medium"),
    _short("benzene-structure", "How many pi electrons are delocalised in benzene?", ["6", "six"],
           "Each of the six carbons contributes one pi electron.", "medium"),
    _essay("benzene-structure", "Explain why benzene is more stable than a hypothetical cyclohexatriene.",
           "Delocalisation of six pi electrons gives resonance stabilisation.",
           "Resonance stabilisation lowers the energy of benzene.", "hard"),
    # ---- aromaticity (16-19)
    _mcq("aromaticity", "According to Hueckel's rule an aromatic ring has how many pi electrons?",
         [("a", "4n"), ("b", "4n+2"), ("c", "2n"), ("d", "3n")], "b",
         "Aromatic systems have 4n+2 pi electrons.", "medium"),
    _tf("aromaticity", "An aromatic compound must be planar and cyclic.", True,
        "Planarity and a continuous cycle of p orbitals are required.", "medium"),
    _short("aromaticity", "What is the value of n for benzene in the 4n+2 rule?", ["1"],
           "6 = 4(1)+2 so n is 1.", "hard"),
    _mcq("aromaticity", "Which of these is aromatic?",
         [("a", "Cyclohexane"), ("b", "Benzene"), ("c", "Cyclohexene"), ("d", "Hexane")], "b",
         "Only benzene is planar, cyclic and has 6 delocalised pi electrons.", "easy"),
    # ---- substitution-reactions (20-23)
    _mcq("substitution-reactions", "Which type of reaction is typical for benzene?",
         [("a", "Electrophilic substitution"), ("b", "Electrophilic addition"),
          ("c", "Nucleophilic addition"), ("d", "Elimination")], "a",
         "Substitution keeps the stable aromatic ring intact.", "medium"),
    _tf("substitution-reactions", "Nitration of benzene uses a mixture of nitric and sulfuric acid.", True,
        "The mixture generates the nitronium ion NO2+.", "medium"),
    _short("substitution-reactions", "Name the electrophile in the nitration of benzene.",
           ["nitronium ion", "no2+"], "Nitric and sulfuric acid produce NO2+.", "hard"),
    _mcq("substitution-reactions", "What catalyst is used to brominate benzene?",
         [("a", "FeBr3"), ("b", "H2SO4"), ("c", "Ni"), ("d", "Pt")], "a",
         "FeBr3 polarises Br2 to make a strong electrophile.", "hard"),
]

# Exams reference QUESTIONS by index.
EXAMS = [
    {
        "title": "Quiz 1: Alkanes and Alkenes",
        "description": "Short quiz on alkanes, alkenes and naming.",
        "duration_minutes": 20,
        "max_attempts": 2,
        "proctoring_enabled": False,
        "passing_score": None,
        "publish": True,
        "questions": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    },
    {
        "title": "Midterm: Aromatic compounds",
        "description": "Midterm on benzene, aromaticity and substitution.",
        "duration_minutes": 30,
        "max_attempts": 1,
        "proctoring_enabled": True,
        "passing_score": "60.00",
        "publish": True,
        "questions": [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
    },
    {
        "title": "Draft exam",
        "description": "Left as a draft so publishing can be tested by hand.",
        "duration_minutes": 15,
        "max_attempts": 1,
        "proctoring_enabled": False,
        "passing_score": None,
        "publish": False,
        "questions": [0, 1, 2],
    },
]