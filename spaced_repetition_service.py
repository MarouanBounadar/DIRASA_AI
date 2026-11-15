import time
from typing import List, Dict, Optional

def calculate_spaced_repetition_schedule(courses: List[Dict], stats_data: Optional[Dict] = None) -> List[Dict]:
    """
    Computes a personalized Spaced Repetition study plan (Ebbinghaus Leitner schedule)
    for all courses in the user's library.
    """
    now = time.time()
    schedule = []
    stats_data = stats_data or {}
    quiz_history = stats_data.get("quiz_history", [])

    # Map course titles to latest quiz score
    score_by_course = {}
    for qh in quiz_history:
        title = qh.get("course_title", "").strip().lower()
        if title:
            score = qh.get("score", 0)
            total = qh.get("total", 1)
            pct = round((score / total) * 100) if total > 0 else 0
            score_by_course[title] = pct

    for c in courses:
        timestamp = c.get("timestamp", 0)
        if not timestamp:
            timestamp = now
        
        seconds_elapsed = max(0, now - timestamp)
        days_elapsed = round(seconds_elapsed / 86400, 1)

        title = c.get("title", "Sans titre")
        title_lower = title.strip().lower()
        module = c.get("module", "Général")

        latest_pct = score_by_course.get(title_lower, None)

        # Determine Leitner Stage & Due status
        # Stages: J+1 (day 1), J+3 (day 3), J+7 (day 7), J+14 (day 14), J+30 (day 30)
        status_level = "upcoming"
        badge_text = ""
        recommendation = ""
        recommended_action = "flashcards"

        if latest_pct is not None and latest_pct < 60:
            status_level = "urgent"
            badge_text = "🔴 Révision Urgente"
            recommendation = f"Score QCM récent : {latest_pct}% ➔ Révisez les concepts fragiles et repassez le quiz !"
            recommended_action = "quiz"
        elif days_elapsed <= 1.5:
            # Stage J+1
            status_level = "due_today"
            badge_text = "⚡ Cycle J+1 (24h)"
            recommendation = "Séance récente vue hier ➔ 5 minutes de Flashcards pour ancrer la mémoire à court terme."
            recommended_action = "flashcards"
        elif 1.5 < days_elapsed <= 4.0:
            # Stage J+3
            status_level = "due_today"
            badge_text = "🧠 Cycle J+3"
            recommendation = f"Vue il y a {int(days_elapsed)} jours ➔ Révisez les 20 Flashcards pour consolider l'apprentissage."
            recommended_action = "flashcards"
        elif 4.0 < days_elapsed <= 8.0:
            # Stage J+7
            status_level = "due_today"
            badge_text = "🎯 Cycle J+7"
            recommendation = f"Vue il y a {int(days_elapsed)} jours ➔ Testez-vous sur le Quiz QCM pour valider la rétention."
            recommended_action = "quiz"
        elif 8.0 < days_elapsed <= 18.0:
            # Stage J+14
            status_level = "upcoming"
            badge_text = "📅 Cycle J+14"
            recommendation = f"Vue il y a {int(days_elapsed)} jours ➔ Révision globale recommandée cette semaine."
            recommended_action = "quiz"
        else:
            # Stage J+30+
            if latest_pct is not None and latest_pct >= 80:
                status_level = "mastered"
                badge_text = "🟢 Bien Mémorisé"
                recommendation = f"Maîtrise validée ({latest_pct}%) ➔ À revoir uniquement la veille du contrôle final."
                recommended_action = "exam"
            else:
                status_level = "urgent"
                badge_text = "⚠️ Cycle J+30"
                recommendation = f"Vue il y a plus de {int(days_elapsed)} jours ➔ Risque d'oubli élevé, repassez un Examen Blanc !"
                recommended_action = "exam"

        schedule.append({
            "course": c,
            "title": title,
            "module": module,
            "days_elapsed": days_elapsed,
            "score_pct": latest_pct,
            "status_level": status_level,
            "badge_text": badge_text,
            "recommendation": recommendation,
            "recommended_action": recommended_action
        })

    # Sort priority: urgent -> due_today -> upcoming -> mastered
    priority_order = {"urgent": 0, "due_today": 1, "upcoming": 2, "mastered": 3}
    schedule.sort(key=lambda x: (priority_order.get(x["status_level"], 99), -x["days_elapsed"]))

    return schedule
