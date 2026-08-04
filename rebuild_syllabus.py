import csv, re, json, datetime, os

csv_path = r"c:\Users\sboopathi\projects\CryoSoftWare\syllabuls.csv"
json_output_path = r"c:\Users\sboopathi\projects\CryoSoftWare\syllabus.json"

# ─── Calculus & Optimization entries to add ───────────────────────────────────
CALC_ENTRIES = [
    ("L01: Limit Laws, Epsilon-Delta Definitions, and Continuity Verification for Single-Variable Functions", 1, 30),
    ("L02: Differentiability Rules: Product, Quotient, and Chain Rule Derivations from First Principles", 1, 35),
    ("L03: Taylor and Maclaurin Polynomial Approximations and Remainder Error Bound Estimations", 2, 40),
    ("L04: First and Second Derivative Tests for Local Maxima and Minima in Single-Variable Functions", 2, 45),
    ("L05: Convex Function Properties: Jensen Inequality and Sub-Gradient Descent Formulations", 3, 50),
    ("L06: Gradient Descent Algorithm: Step-Size Selection and Convergence Rate Proofs", 3, 55),
    ("L07: Stochastic Gradient Descent Variance Reduction and Mini-Batch Mechanics", 4, 60),
    ("L08: Lagrange Multipliers for Equality-Constrained Optimization Problems", 4, 65),
    ("L09: KKT Conditions for Inequality-Constrained Convex Programming", 5, 70),
    ("L10: Numerical Differentiation: Forward, Backward, and Central Finite Difference Approximations", 5, 65),
    ("L11: Newton-Raphson Root Finding and Quasi-Newton BFGS Optimization Algorithms", 6, 75),
    ("L12: Partial Derivatives, Gradient Vectors, and Jacobian Matrix Computations", 6, 80),
    ("L13: Hessian Matrix Definiteness Tests for Multi-Variable Saddle Point Detection", 7, 85),
    ("L14: Coordinate Descent and Alternating Minimization for Block-Separable Objectives", 7, 90),
    ("L15: Automatic Differentiation via Forward and Reverse Mode Computational Graph Passes", 8, 95),
    ("L16: Proximal Gradient Methods and ISTA/FISTA Accelerated Composite Minimizers", 9, 100),
    ("CAT: GATE Calculus and Optimization Assessment: Derivative Analysis and Gradient Descent", 5, 500),
    ("DA: End-to-End Gradient Descent Implementation with Convergence Analysis Production Engine", 8, 800),
]

# Check if already added
with open(csv_path, "r", encoding="utf-8") as f:
    content = f.read()

if "Calculus_Optimization" not in content:
    with open(csv_path, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for module, lvl, xp in CALC_ENTRIES:
            writer.writerow([module, f"Level {lvl}", xp, "Calculus_Optimization"])
    print(f"Added {len(CALC_ENTRIES)} Calculus_Optimization entries to CSV")
else:
    print("Calculus_Optimization already exists in CSV, skipping append")

# ─── Week titles for all 12 courses ──────────────────────────────────────────
WEEK_TITLES = {
    "Python_Data_Science": {
        1: "Fundamentals of NumPy, Slicing & Broadcasting",
        2: "SciPy Interpolation & Figure Canvas Layouts",
        3: "Non-Linear Minimization & Numerical Solvers",
        4: "Data Slicing, Exceptions & Final Project"
    },
    "Linear_Algebra": {
        1: "NumPy Matrix Formats, Hadamard & Determinants",
        2: "Characteristic Polynomials & Eigen-Decomposition",
        3: "Systems of Linear Equations & Forward Elimination",
        4: "Matrix Inversion Singularity & LU/Cholesky/QR Decompositions",
        5: "Vector Spaces, Dimensions & Spectral Decomposition",
        6: "Least Squares regression, Ridge & Final Project"
    },
    "Probability_Stats": {
        1: "Sample Space Formulations & Addition/Multiplication Laws",
        2: "Conditional Probability Bounds & Bayes Theorem",
        3: "Probability Mass & Joint Cumulative Distributions",
        4: "Continuous Distributions: Normal, Poisson & waiting-time",
        5: "Central Limit Theorem, Hypothesis Testing & Final Inference"
    },
    "Statistical_Inference": {
        1: "Population Parameter Estimations & Cramer-Rao Bounds",
        2: "Maximum Likelihood Estimation & Wald Intervals",
        3: "Hypothesis Testing alpha/beta & Large/Small Sample Tests",
        4: "Chi-Square Independence Tests & Wald Correlation",
        5: "Non-Parametric Inferences, Rank Dominance & Final Pipeline"
    },
    "EDA": {
        1: "Vectorization Mechanics, Pandas Alignments & Time-Series",
        2: "Row-Wise Locality Cleansing, Box-Cox & MCAR/MAR Diagnoses",
        3: "Bayesian Estimations & Multivariate Imputations via MICE",
        4: "Covariance, Skewness, Histograms & Andrews Plots",
        5: "Extreme Value fitting, Modified Z-score & LOF",
        6: "Information Gain, WCSS Elbow Convergence & PCA",
        7: "Target Leakage Diagnoses, Manifold Projection & Final Pipeline"
    },
    "Database_Systems": {
        1: "Evolution of Storage, ER Graphs & EER Union Categories",
        2: "Integrity Constraints & Relational Algebra Join Operators",
        3: "Predicate Calculus & SQL domain check constraints",
        4: "Subquery Declarative Formulations & Functional Dependencies",
        5: "Armstrong Axioms, Normal Forms (1NF-5NF) & Slotted Records",
        6: "B+ Tree Indexing, ACID Transaction Concurrency & Final Engine"
    },
    "Data_Mining_Forecasting": {
        1: "OLAP Cube slicing & Minkowski Jaccard Dissimilarity",
        2: "Nominal Ordinal Distance Metrics & PCA SVD",
        3: "Information Gain, Decision Trees & Cost-Complexity pruning",
        4: "Bagging, Random Forests & KNN KD-Trees",
        5: "MAP Classification, Newton-Raphson & Regularized Weights",
        6: "SVM Dual Space Lagrangians, Apriori & Final Forecasting"
    },
    "Advanced_Forecasting": {
        1: "Forecast Error profiles MSE/MAE & Prediction Intervals",
        2: "Holts Linear Smoothing & Ordinary Least Squares",
        3: "Cross-Validation prediction errors & Leverage Cook distance",
        4: "Multi-Variable Matrix Regression & Heteroscedasticity",
        5: "Autoregressive serial dependency & Box-Cox stabilizers",
        6: "Akaike/Schwarz Information Criteria & Generalized Linear Models"
    },
    "DSA_LeetCode": {
        1: "Asymptotic Notation Proofs & Vectorized Sliding Window",
        2: "Dynamic Singly Linked memory blocks & Infix-to-Postfix Stacks",
        3: "Double-Ended Queues & Linked List Structural Inversions",
        4: "Shell Sort interval gaps, Quick Sort Lomuto & Heap Arrays",
        5: "Binary Search boundary spaces & AVL Tree rotations",
        6: "Graph Adjacency Matrix DFS/BFS, MST Kruskal Prim & Shortest Paths",
        7: "Backtracking Sudoku Solvers, Dynamic Programming & Final project"
    },
    "AI_Agents": {
        1: "State-Space modeling & PEAS Framework properties",
        2: "Simple Reflex, Model-Based & Utility optimization agents",
        3: "Uninformed tree exploration BFS/DFS & A* heuristic consistency",
        4: "Adversarial Search, Alpha-Beta Pruning & CSP Backtracking",
        5: "Propositional Logic CNF resolution & First-Order Logic",
        6: "Robinson Unification, Bayesian Belief Networks & Neural calculus"
    },
    "Machine_Learning": {
        1: "Train/Test partition mechanics & Standardizing Rescaling",
        2: "Imputers KNN Iterative & Evaluation Metrics Loss landscapes",
        3: "Gradient Descent Optimizations & regularized Ridge/Lasso",
        4: "Logit Hyperplane calibration, SMOTE & Ensemble Bagging",
        5: "Gradient Boosting XGBoost LightGBM & Support Vector",
        6: "Gaussian Mixture Models EM, t-SNE UMAP & Explainers",
        7: "Online learning, Collaborative Filtering & Perceptrons",
        8: "CNN, LSTM, Transformers Self-Attention & Final System"
    },
    "Calculus_Optimization": {
        1: "Limits, Continuity, Differentiability & Taylor Series",
        2: "Maxima/Minima, Convexity & Gradient Descent Foundations",
        3: "Constrained Optimization: Lagrangians & KKT Conditions",
        4: "Numerical Methods & Automatic Differentiation"
    }
}

COURSE_DISPLAY_NAMES = {
    "DSA_LeetCode": "Data Structures and Algorithms",
    "EDA": "Exploratory Data Analysis",
    "Linear_Algebra": "Linear Algebra",
    "Probability_Stats": "Probability & Statistics",
    "Python_Data_Science": "Python Programming",
    "AI_Agents": "Artificial Intelligence",
    "Data_Mining_Forecasting": "Data Mining & Forecasting",
    "Database_Systems": "Database Management System",
    "Advanced_Forecasting": "Forecasting & Predictive Analytics",
    "Statistical_Inference": "Statistical Inference",
    "Machine_Learning": "Machine Learning",
    "Calculus_Optimization": "Calculus & Optimization (GATE)"
}

COURSE_ORDER = [
    "Calculus_Optimization",
    "Python_Data_Science",
    "Linear_Algebra",
    "Probability_Stats",
    "Statistical_Inference",
    "EDA",
    "Database_Systems",
    "Data_Mining_Forecasting",
    "Advanced_Forecasting",
    "DSA_LeetCode",
    "AI_Agents",
    "Machine_Learning"
]

# ─── Read CSV ─────────────────────────────────────────────────────────────────
course_items = {}
with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        c = row["Course"].strip()
        module = row["Course_Module"].strip().strip('"')
        lvl_str = row["Level_Required"].strip()
        m = re.search(r"\d+", lvl_str)
        lvl = int(m.group(0)) if m else 1
        xp = int(row["XP_Points_Earned"])
        course_items.setdefault(c, []).append({"module": module, "level": lvl, "xp": xp})

# ─── Sort items per course ───────────────────────────────────────────────────
for c in COURSE_ORDER:
    if c not in course_items:
        print(f"WARNING: {c} not found in CSV")
        course_items[c] = []
        continue
    items = course_items[c]
    level_groups = {i: [] for i in range(1, 13)}
    for it in items:
        lvl = min(it["level"], 12)
        level_groups[lvl].append(it)
    sorted_items = []
    for lvl in range(1, 13):
        group = level_groups[lvl]
        lectures, cat_items, da_items = [], [], []
        for it in group:
            mod_name = it["module"]
            if mod_name.startswith("CAT:"):
                cat_items.append(it)
            elif mod_name.startswith("DA:"):
                da_items.append(it)
            else:
                mm = re.match(r"^L(\d+):", mod_name)
                lectures.append((int(mm.group(1)) if mm else 999, it))
        lectures.sort(key=lambda x: x[0])
        sorted_items.extend([x[1] for x in lectures] + cat_items + da_items)
    course_items[c] = sorted_items

# ─── Schedule across year starting 2026-08-01 ─────────────────────────────────
queue = [(c, it) for c in COURSE_ORDER for it in course_items[c]]
current_date = datetime.date(2026, 8, 1)
scheduled_items = []

while queue:
    weekday = current_date.weekday()
    if weekday == 6:  # Sunday - only CAT/DA
        if queue and (queue[0][1]["module"].startswith("CAT:") or queue[0][1]["module"].startswith("DA:")):
            c, it = queue.pop(0)
            scheduled_items.append((current_date, c, it, "test"))
        current_date += datetime.timedelta(days=1)
        continue
    slots = 2 if weekday in (0, 1, 3, 4) else 1  # Mon/Tue/Thu/Fri=2, Wed/Sat=1
    for _ in range(slots):
        if not queue:
            break
        if queue[0][1]["module"].startswith("CAT:") or queue[0][1]["module"].startswith("DA:"):
            break
        c, it = queue.pop(0)
        scheduled_items.append((current_date, c, it, "lecture"))
    current_date += datetime.timedelta(days=1)

# ─── Group by course/week ─────────────────────────────────────────────────────
course_weeks = {}
for date, c, it, t in scheduled_items:
    yr, wk, _ = date.isocalendar()
    course_weeks.setdefault(c, {}).setdefault((yr, wk), []).append((date, it, t))

# ─── Build JSON ───────────────────────────────────────────────────────────────
syllabus_db = {"courses": {}}
for c in COURSE_ORDER:
    weeks_dict = course_weeks.get(c, {})
    weeks_list = []
    for w_idx, (w_key, items) in enumerate(sorted(weeks_dict.items()), start=1):
        start_d = min(x[0] for x in items)
        end_d   = max(x[0] for x in items)
        week_items_json = []
        v_idx, q_idx = 1, 1
        for date, it, t in items:
            mod_name = it["module"]
            if t == "lecture":
                item_id = f"{c}_w{w_idx}_v{v_idx}"; v_idx += 1; item_type = "video"
            else:
                item_id = f"{c}_midterm" if mod_name.startswith("CAT:") else f"{c}_da"; q_idx += 1; item_type = "quiz"
            week_items_json.append({
                "id": item_id, "name": mod_name, "type": item_type,
                "xp": it["xp"], "level": it["level"], "date": date.isoformat()
            })
        title_map = WEEK_TITLES.get(c, {})
        title = title_map.get(w_idx, f"Week {w_idx}: Advanced Topics & Practice")
        weeks_list.append({
            "week": w_idx, "title": title,
            "start_date": start_d.isoformat(), "end_date": end_d.isoformat(),
            "items": week_items_json
        })
    syllabus_db["courses"][c] = {
        "name": COURSE_DISPLAY_NAMES.get(c, c),
        "code": c, "weeks": weeks_list
    }

with open(json_output_path, "w", encoding="utf-8") as f:
    json.dump(syllabus_db, f, indent=2, ensure_ascii=False)

total_weeks = sum(len(v["weeks"]) for v in syllabus_db["courses"].values())
total_items = sum(len(w["items"]) for v in syllabus_db["courses"].values() for w in v["weeks"])
print(f"SUCCESS: Generated syllabus.json")
print(f"  Courses: {len(syllabus_db['courses'])}")
print(f"  Total weeks: {total_weeks}")
print(f"  Total items: {total_items}")
for c, cv in syllabus_db["courses"].items():
    print(f"  {COURSE_DISPLAY_NAMES.get(c,c)}: {len(cv['weeks'])} weeks")
