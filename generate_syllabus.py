import csv
import json
import re
import datetime

csv_path = r"c:\Users\sboopathi\projects\CryoSoftWare\syllabuls.csv"
json_output_path = r"c:\Users\sboopathi\projects\CryoSoftWare\syllabus.json"

# Detailed, logical week titles for each course
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
        2: "Conditional Probability Bounds & Bayes Theorem Naive Bayes",
        3: "Probability Mass & Joint Cumulative Distributions",
        4: "Continuous Distributions: Normal, Poisson & waiting-time",
        5: "Central Limit Theorem, Hypothesis Testing & Final Inference Engine"
    },
    "Statistical_Inference": {
        1: "Population Parameter Estimations & Cramér-Rao Bounds",
        2: "Maximum Likelihood Estimation L-BFGS-B & Wald Intervals",
        3: "Hypothesis Testing alpha/beta & Large/Small Sample Mean Tests",
        4: "Chi-Square Independence Tests & Wald Correlation",
        5: "Non-Parametric Inferences, Rank Dominance & Final Pipeline"
    },
    "EDA": {
        1: "Vectorization Mechanics, Pandas Alignments & Time-Series resampling",
        2: "Row-Wise Locality Cleansing, Box-Cox & MCAR/MAR Diagnoses",
        3: "Bayesian Estimations & Multivariate Imputations via MICE",
        4: "Covariance, Skewness, Scott's Rule Histograms & Andrews Plots",
        5: "Extreme Value fitting, Modified Z-score & Subspace Partitioning LOF",
        6: "Information Gain, WCSS Elbow Convergence & PCA Covariance",
        7: "Target Leakage Diagnoses, Manifold Projection & Final Pipeline"
    },
    "Database_Systems": {
        1: "Evolution of Storage, ER Graphs & EER Union Categories",
        2: "Integrity Constraints & Relational Algebra Join Operators",
        3: "Predicate Calculus Well-Formed Formula & SQL domain check constraints",
        4: "Subquery Declarative Formulations & Functional Dependency Discovery",
        5: "Armstrong's Axioms, Normal Forms (1NF-5NF) & Slotted Page Records",
        6: "B+ Tree Indexing, ACID Transaction Concurrency Recovery & Final Engine"
    },
    "Data_Mining_Forecasting": {
        1: "OLAP Cube multi-dimensional slicing & Minkowski Jaccard Dissimilarity",
        2: "Nominal Ordinal Distance Metrics & PCA SVD Variance Retention",
        3: "Information Gain, Decision Trees & Cost-Complexity tree pruning",
        4: "Bagging, Random Forests & KNN KD-Trees Ball-Trees",
        5: "MAP Classification, Newton-Raphson & Regularized Weight Penalty",
        6: "SVM Dual Space Lagrangians, Apriori Frequent Pattern & Final forecasting"
    },
    "Advanced_Forecasting": {
        1: "Forecast Error profiles MSE/MAE & Prediction Intervals",
        2: "Holt's Linear Smoothing & Ordinary Least Squares assumptions",
        3: "Cross-Validation prediction errors & Leverage Cook's distance",
        4: "Multi-Variable Matrix Regression & Heteroscedasticity defences",
        5: "Autoregressive serial dependency & Box-Cox stabilizer projections",
        6: "Akaike/Schwarz Information Criteria & Generalized Linear Models (GLMs)"
    },
    "DSA_LeetCode": {
        1: "Asymptotic Notation Proofs & Vectorized Sliding Window",
        2: "Dynamic Singly Linked memory blocks & Infix-to-Postfix Stacks",
        3: "Double-Ended Queues & Linked List Structural Inversions",
        4: "Shell Sort interval gaps, Quick Sort Lomuto & Heap Arrays",
        5: "Binary Search boundary spaces & AVL Tree rotations",
        6: "Graph Adjacency Matrix DFS/BFS, MST Kruskal Prim & Shortest Paths",
        7: "Backtracking Sudoku Solvers, Dynamic Programming Knapsack & Final project"
    },
    "AI_Agents": {
        1: "State-Space modeling & PEAS Framework properties",
        2: "Simple Reflex, Model-Based & Utility optimization agents",
        3: "Uninformed tree exploration BFS/DFS & A* heuristic consistency",
        4: "Adversarial Search, Alpha-Beta Pruning & CSP Backtracking",
        5: "Propositional Logic automated CNF resolution & First-Order Logic Modus Ponens",
        6: "Robinson Unification, Bayesian Belief Networks & Neural Activation calculus"
    },
    "Machine_Learning": {
        1: "Train/Test partition mechanics & Standardizing Rescaling",
        2: "Imputers KNN Iterative & Evaluation Metrics Loss landscapes",
        3: "Gradient Descent Optimizations & regularized Ridge/Lasso coordinates",
        4: "Logit Hyperplane calibration, SMOTE & Ensemble trees Bagging",
        5: "Gradient Boosting XGBoost LightGBM & Support Vector Classifications",
        6: "Gaussian Mixture Models EM, t-SNE UMAP & SHAP/LIME Explainers",
        7: "Online learning, Collaborative Filtering recommenders & Deep learning Perceptrons",
        8: "Convolutional CNN receptive fields, LSTM state, Transformers Self-Attention & Final System"
    }
}

# Display names mapping
COURSE_DISPLAY_NAMES = {
    "DSA_LeetCode": "Data Structures and Algorithms",
    "EDA": "Exploratory Data Analysis",
    "Linear_Algebra": "Linear Algebra",
    "Probability_Stats": "Probability and Distribution Model",
    "Python_Data_Science": "Python Programming",
    "AI_Agents": "Artificial Intelligence",
    "Data_Mining_Forecasting": "Data Mining",
    "Database_Systems": "Database Management System",
    "Advanced_Forecasting": "Forecasting and Predictive Analytics",
    "Statistical_Inference": "Statistical Inference",
    "Machine_Learning": "Machine Learning"
}

course_order = [
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

# Read CSV items
course_items = {}
with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        c = row["Course"].strip()
        module = row["Course_Module"].strip()
        lvl = int(re.search(r"\d+", row["Level_Required"]).group(0))
        xp = int(row["XP_Points_Earned"])
        course_items.setdefault(c, []).append({
            "module": module,
            "level": lvl,
            "xp": xp
        })

# Sort items within each course by Level (1 to 12) ascending, and then by lecture number, CAT, and DA
for c in course_order:
    items = course_items[c]
    
    # Group items of this course by level
    level_groups = {i: [] for i in range(1, 13)}
    for it in items:
        level_groups[it["level"]].append(it)
        
    sorted_items = []
    for lvl in range(1, 13):
        group = level_groups[lvl]
        lectures = []
        cat_items = []
        da_items = []
        for it in group:
            mod_name = it["module"].strip()
            if mod_name.startswith("CAT:"):
                cat_items.append(it)
            elif mod_name.startswith("DA:"):
                da_items.append(it)
            else:
                m = re.match(r"^L(\d+):", mod_name)
                if m:
                    lectures.append((int(m.group(1)), it))
                else:
                    lectures.append((999, it))
        lectures.sort(key=lambda x: x[0])
        sorted_items.extend([x[1] for x in lectures] + cat_items + da_items)
        
    course_items[c] = sorted_items

# Queue items to schedule
queue = []
for c in course_order:
    for it in course_items[c]:
        queue.append((c, it))

current_date = datetime.date(2026, 8, 1)
scheduled_items = []

# Perform daily scheduling
while queue:
    weekday = current_date.weekday()
    
    if weekday == 6: # Sunday
        if queue:
            next_c, next_it = queue[0]
            mod = next_it["module"].strip()
            if mod.startswith("CAT:") or mod.startswith("DA:"):
                c, it = queue.pop(0)
                scheduled_items.append((current_date, c, it, "test"))
                current_date += datetime.timedelta(days=1)
                continue
        current_date += datetime.timedelta(days=1)
        continue
        
    num_to_schedule = 0
    if weekday in (0, 1, 3, 4): # Monday, Tuesday, Thursday, Friday: 2 lectures/day
        num_to_schedule = 2
    elif weekday in (2, 5): # Wednesday, Saturday: 1 lecture/day
        num_to_schedule = 1
        
    for _ in range(num_to_schedule):
        if not queue:
            break
        next_c, next_it = queue[0]
        mod = next_it["module"].strip()
        if mod.startswith("CAT:") or mod.startswith("DA:"):
            break
            
        c, it = queue.pop(0)
        scheduled_items.append((current_date, c, it, "lecture"))
        
    current_date += datetime.timedelta(days=1)

# Group scheduled items by course, then by calendar week
# Calendar week = (year, week_number)
course_weeks = {}
for date, c, it, t in scheduled_items:
    year, week_num, _ = date.isocalendar()
    week_key = (year, week_num)
    course_weeks.setdefault(c, {}).setdefault(week_key, []).append((date, it, t))

# Construct final JSON database
syllabus_db = {"courses": {}}

for c in course_order:
    weeks_dict = course_weeks.get(c, {})
    weeks_list = []
    
    for w_idx, (w_key, items) in enumerate(sorted(weeks_dict.items()), start=1):
        start_d = min(x[0] for x in items)
        end_d = max(x[0] for x in items)
        
        week_items_json = []
        video_idx = 1
        quiz_idx = 1
        
        for date, it, t in items:
            mod_name = it["module"].strip()
            xp_val = it["xp"]
            date_str = date.isoformat()
            
            # Determine type and ID
            if t == "lecture":
                item_type = "video"
                item_id = f"{c}_w{w_idx}_v{video_idx}"
                video_idx += 1
            else:
                item_type = "quiz"
                if mod_name.startswith("CAT:"):
                    item_id = f"{c}_midterm"
                else:
                    item_id = f"{c}_digital_assignment"
                quiz_idx += 1
                
            week_items_json.append({
                "id": item_id,
                "name": mod_name,
                "type": item_type,
                "xp": xp_val,
                "date": date_str
            })
            
        week_title = WEEK_TITLES[c].get(w_idx, "Lectures & Assessments")
        
        weeks_list.append({
            "week": w_idx,
            "title": week_title,
            "start_date": start_d.isoformat(),
            "end_date": end_d.isoformat(),
            "items": week_items_json
        })
        
    syllabus_db["courses"][c] = {
        "name": COURSE_DISPLAY_NAMES[c],
        "code": c,
        "weeks": weeks_list
    }

# Save JSON file
with open(json_output_path, "w", encoding="utf-8") as f:
    json.dump(syllabus_db, f, indent=2, ensure_ascii=False)

print("Generated syllabus.json successfully with ascending learning curve sorting!")
