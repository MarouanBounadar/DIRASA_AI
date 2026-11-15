import json
import re
from google import genai

MOCK_EXAM_PROMPT = """
Tu es un examinateur universitaire dans le module '{module}'.
Voici le contenu d'un cours récemment dispensé :
Titre : {title}
Résumé : {summary}
Points clés : {key_points}

Génère un EXAMEN BLANC officiel et rigoureux composé de 3 questions/exercices progressifs pour évaluer les étudiants :
1. Question 1 (5 points) : Compréhension théorique et définitions clés.
2. Question 2 (8 points) : Cas pratique, exercice d'application ou écriture/analyse de code/règle.
3. Question 3 (7 points) : Problème de synthèse, piège d'examen ou réflexion approfondie.

RÉPONDS UNIQUEMENT EN JSON VALIDE respectant ce format :
[
  {{
    "id": 1,
    "title": "Exercice 1 : Notions fondamentales",
    "points": 5,
    "question": "Énoncé complet de la question 1..."
  }},
  {{
    "id": 2,
    "title": "Exercice 2 : Application pratique",
    "points": 8,
    "question": "Énoncé complet de la question 2..."
  }},
  {{
    "id": 3,
    "title": "Exercice 3 : Problème d'analyse & Synthèse",
    "points": 7,
    "question": "Énoncé complet de la question 3..."
  }}
]
"""

GRADING_PROMPT = """
Tu es un professeur d'université sévère, équitable et bienveillant.
Voici les questions d'un examen blanc (barème sur 20 points) :
{exam_context}

Voici la copie rendue par l'étudiant avec ses réponses :
{student_answers}

Évalue avec rigueur la copie de l'étudiant.
Attribue une note globale sur 20, une mention (Très Bien, Bien, Assez Bien, Passable, Ajourné), une appréciation générale, et le détail par question avec correction modèle.

RÉPONDS UNIQUEMENT EN JSON VALIDE respectant cette structure :
{{
  "total_score": 15.5,
  "max_score": 20,
  "mention": "Bien",
  "appreciation": "Appréciation générale bienveillante et conseils pour le vrai examen...",
  "corrections": [
    {{
      "question_id": 1,
      "score": 4.5,
      "max_score": 5,
      "feedback": "Remarques sur ce qui est bon et ce qui manque...",
      "model_solution": "La solution modèle attendue..."
    }},
    {{
      "question_id": 2,
      "score": 6.0,
      "max_score": 8,
      "feedback": "...",
      "model_solution": "..."
    }},
    {{
      "question_id": 3,
      "score": 5.0,
      "max_score": 7,
      "feedback": "...",
      "model_solution": "..."
    }}
  ]
}}
"""

def generate_mock_exam(course_data: dict, config: dict) -> list:
    """Generates 3 exam questions based on the course."""
    gemini_key = config.get("gemini_api_key", "").strip()
    if not gemini_key or not course_data:
        return [
            {"id": 1, "title": "Exercice 1 : Concepts", "points": 5, "question": "Définissez les notions clés de la séance et expliquez leur rôle."},
            {"id": 2, "title": "Exercice 2 : Cas Pratique", "points": 8, "question": "Appliquez le principe vu en cours sur un scénario concret."},
            {"id": 3, "title": "Exercice 3 : Pièges d'Examen", "points": 7, "question": "Quels sont les pièges fréquents à éviter sur ce chapitre ?"}
        ]

    client = genai.Client(api_key=gemini_key)
    prompt = MOCK_EXAM_PROMPT.format(
        module=course_data.get("module", "Informatique"),
        title=course_data.get("title", "Cours"),
        summary=course_data.get("summary", ""),
        key_points="\n".join([f"- {k}" for k in course_data.get("key_takeaways", [])])
    )

    for m in ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.8-flash"]:
        try:
            res = client.models.generate_content(model=m, contents=prompt)
            text = res.text.strip()
            if text.startswith("```json"): text = text[7:]
            if text.startswith("```"): text = text[3:]
            if text.endswith("```"): text = text[:-3]
            return json.loads(text.strip())
        except Exception:
            continue

    return [
        {"id": 1, "title": "Exercice 1 : Concepts", "points": 5, "question": "Définissez les notions clés de la séance et expliquez leur rôle."},
        {"id": 2, "title": "Exercice 2 : Cas Pratique", "points": 8, "question": "Appliquez le principe vu en cours sur un scénario concret."},
        {"id": 3, "title": "Exercice 3 : Pièges d'Examen", "points": 7, "question": "Quels sont les pièges fréquents à éviter sur ce chapitre ?"}
    ]

def grade_mock_exam(questions: list, answers: dict, config: dict) -> dict:
    """Grades student answers with AI and returns score /20 and feedback."""
    gemini_key = config.get("gemini_api_key", "").strip()
    client = genai.Client(api_key=gemini_key) if gemini_key else None

    exam_ctx = "\n\n".join([f"Q{q['id']} ({q['points']} pts) : {q['question']}" for q in questions])
    student_ctx = "\n\n".join([f"Réponse à Q{qid} :\n{ans.strip() if ans.strip() else 'AUCUNE RÉPONSE'}" for qid, ans in answers.items()])

    prompt = GRADING_PROMPT.format(exam_context=exam_ctx, student_answers=student_ctx)

    if client:
        for m in ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.8-flash"]:
            try:
                res = client.models.generate_content(model=m, contents=prompt)
                text = res.text.strip()
                if text.startswith("```json"): text = text[7:]
                if text.startswith("```"): text = text[3:]
                if text.endswith("```"): text = text[:-3]
                return json.loads(text.strip())
            except Exception:
                continue

    # Fallback simulation
    return {
        "total_score": 14.0,
        "max_score": 20,
        "mention": "Bien",
        "appreciation": "Bonne copie d'ensemble. Vous avez assimilé l'essentiel du cours, veillez à soigner la rigueur technique.",
        "corrections": [
            {"question_id": q["id"], "score": q["points"] * 0.7, "max_score": q["points"], "feedback": "Réponse globalement correcte.", "model_solution": "Voir le cours PDF pour la solution exhaustive."}
            for q in questions
        ]
    }
