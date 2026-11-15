import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any

STATS_FILE_NAME = "study_stats.json"

def get_stats_file_path(output_dir: str) -> str:
    return os.path.join(output_dir, STATS_FILE_NAME)

def load_stats(output_dir: str) -> Dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)
    stats_path = get_stats_file_path(output_dir)
    default_data = {
        "quiz_history": [],
        "exam_history": []
    }
    if os.path.exists(stats_path):
        try:
            with open(stats_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f"Error loading stats file: {e}")
    return default_data

def save_stats(stats: Dict[str, Any], output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    stats_path = get_stats_file_path(output_dir)
    try:
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving stats file: {e}")

def record_quiz_result(output_dir: str, module: str, course_title: str, score: int, total: int):
    """Records a completed quiz session."""
    stats = load_stats(output_dir)
    now = time.time()
    date_str = datetime.fromtimestamp(now).strftime("%d/%m/%Y à %H:%M")
    pct = round((score / total) * 100, 1) if total > 0 else 0.0

    entry = {
        "timestamp": int(now),
        "date": date_str,
        "module": module or "Général",
        "course_title": course_title or "Cours",
        "score": score,
        "total": total,
        "percentage": pct
    }
    stats["quiz_history"].append(entry)
    save_stats(stats, output_dir)
    return entry

def record_exam_result(output_dir: str, module: str, course_title: str, grade: float, out_of: float = 20.0):
    """Records a completed mock exam."""
    stats = load_stats(output_dir)
    now = time.time()
    date_str = datetime.fromtimestamp(now).strftime("%d/%m/%Y à %H:%M")

    entry = {
        "timestamp": int(now),
        "date": date_str,
        "module": module or "Général",
        "course_title": course_title or "Cours",
        "grade": round(grade, 1),
        "out_of": out_of
    }
    stats["exam_history"].append(entry)
    save_stats(stats, output_dir)
    return entry

def calculate_dashboard_metrics(output_dir: str, courses: List[Dict]) -> Dict[str, Any]:
    """
    Computes all analytical metrics for the user revision dashboard.
    """
    stats = load_stats(output_dir)
    now = time.time()
    one_week_ago = now - (7 * 86400)

    # Courses counts
    total_courses = len(courses)
    courses_this_week = sum(1 for c in courses if c.get("timestamp", 0) >= one_week_ago)
    total_flashcards = sum(c.get("flashcards_count", 0) for c in courses)
    total_quiz_q = sum(c.get("quiz_count", 0) for c in courses)

    # Quiz stats
    quiz_hist = stats.get("quiz_history", [])
    total_quizzes = len(quiz_hist)
    total_q_answered = sum(q.get("total", 0) for q in quiz_hist)
    total_q_correct = sum(q.get("score", 0) for q in quiz_hist)
    
    global_quiz_rate = round((total_q_correct / total_q_answered) * 100, 1) if total_q_answered > 0 else 0.0

    # Exam stats
    exam_hist = stats.get("exam_history", [])
    total_exams = len(exam_hist)
    avg_exam_grade = round(sum(e.get("grade", 0) for e in exam_hist) / total_exams, 1) if total_exams > 0 else 0.0

    # Per-module analytics
    modules_map = {}
    
    # 1. Initialize from existing courses
    for c in courses:
        mod = c.get("module", "Général").strip()
        if not mod:
            mod = "Général"
        if mod not in modules_map:
            modules_map[mod] = {
                "name": mod,
                "courses_count": 0,
                "quizzes_taken": 0,
                "correct": 0,
                "total": 0,
                "success_rate": 0.0,
                "status": "Non testé"
            }
        modules_map[mod]["courses_count"] += 1

    # 2. Accumulate quiz performance
    for q in quiz_hist:
        mod = q.get("module", "Général").strip()
        if not mod:
            mod = "Général"
        if mod not in modules_map:
            modules_map[mod] = {
                "name": mod,
                "courses_count": 0,
                "quizzes_taken": 0,
                "correct": 0,
                "total": 0,
                "success_rate": 0.0,
                "status": "Non testé"
            }
        modules_map[mod]["quizzes_taken"] += 1
        modules_map[mod]["correct"] += q.get("score", 0)
        modules_map[mod]["total"] += q.get("total", 0)

    # Compute rates and statuses
    module_list = []
    for mod_name, data in modules_map.items():
        if data["total"] > 0:
            rate = round((data["correct"] / data["total"]) * 100, 1)
            data["success_rate"] = rate
            if rate >= 75.0:
                data["status"] = "Maîtrisé"
            elif rate >= 50.0:
                data["status"] = "À consolider"
            else:
                data["status"] = "À réviser en priorité"
        else:
            data["success_rate"] = 0.0
            data["status"] = "Non testé"
        module_list.append(data)

    # Sort modules: lowest success rate first (needs attention)
    module_list.sort(key=lambda x: (x["total"] == 0, x["success_rate"]))

    # AI Coach Advice Generation
    ai_advice = []
    
    tested_modules = [m for m in module_list if m["total"] > 0]
    
    if tested_modules:
        weakest = min(tested_modules, key=lambda m: m["success_rate"])
        strongest = max(tested_modules, key=lambda m: m["success_rate"])

        if weakest["success_rate"] < 60.0:
            ai_advice.append(
                f"⚠️ Attention priorité examens : Votre taux de réussite en '{weakest['name']}' est de {weakest['success_rate']}%. "
                f"Prenez 15 minutes pour réviser les Flashcards et refaire les quiz de ce module avant vos prochains contrôles !"
            )
        
        if strongest["success_rate"] >= 75.0:
            ai_advice.append(
                f"🏆 Point fort : Excellente maîtrise de '{strongest['name']}' avec {strongest['success_rate']}% de bonnes réponses. "
                f"Vos bases sont solides pour aborder les épreuves finales de cette matière !"
            )
    else:
        ai_advice.append(
            "🚀 Bienvenue sur votre Tableau de Bord ! Vous n'avez pas encore passé de Quiz. "
            "Rendez-vous dans l'onglet 'Quiz QCM' pour tester votre niveau sur votre cours et obtenir vos premières statistiques !"
        )

    ai_advice.append(
        "💡 Conseil Pédagogique du Coach : Révisez 20 flashcards par jour en répétition espacée (Anki). "
        "Cette méthode augmente le taux de rétention de vos cours de plus de 80% avant les examens."
    )

    return {
        "total_courses": total_courses,
        "courses_this_week": courses_this_week,
        "total_flashcards": total_flashcards,
        "total_quiz_q": total_quiz_q,
        "total_quizzes": total_quizzes,
        "global_quiz_rate": global_quiz_rate,
        "total_exams": total_exams,
        "avg_exam_grade": avg_exam_grade,
        "modules": module_list,
        "ai_advice": ai_advice,
        "recent_quizzes": quiz_hist[-5:][::-1]
    }
