import os
import json
import time
from typing import List, Dict, Optional
from fpdf import FPDF

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

class CheatSheetPDF(FPDF):
    def __init__(self, module_name: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.module_name = module_name
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(100, 116, 139)
        self.cell(0, 6, f"DIRASA AI  |  FICHE DE SYNTHÈSE EXPRESS (CHEAT SHEET)  |  MODULE : {self.module_name.upper()}", border="B", ln=1, align="L")
        self.ln(3)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 6, f"Page {self.page_no()}/{{nb}}  -  DIRASA AI : Préparation aux Examens Universitaires", border="T", align="C")

def generate_module_cheat_sheet(module_name: str, sessions: List[Dict], output_dir: str, config: Dict) -> str:
    """
    Synthesizes all sessions of a module into a compact executive Cheat Sheet PDF (2-3 pages).
    Returns the absolute path to the generated PDF.
    """
    os.makedirs(output_dir, exist_ok=True)
    clean_mod_filename = "".join([c if c.isalnum() or c in " _-" else "_" for c in module_name]).strip()
    pdf_filename = f"Synthese_Express_{clean_mod_filename}.pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)

    # 1. Gather all session data
    sessions_data = []
    for s in sessions:
        json_p = s.get("json_path", "")
        if json_p and os.path.exists(json_p):
            try:
                with open(json_p, "r", encoding="utf-8") as f:
                    c_data = json.load(f)
                    sessions_data.append({
                        "title": c_data.get("title", s.get("title", "Séance")),
                        "summary": c_data.get("summary", ""),
                        "takeaways": c_data.get("key_takeaways", []),
                        "toc": c_data.get("table_of_contents", []),
                        "date": s.get("date", "")
                    })
            except Exception as e:
                print(f"Error loading session json for cheat sheet: {e}")
        else:
            sessions_data.append({
                "title": s.get("title", "Séance"),
                "summary": s.get("summary", ""),
                "takeaways": [s.get("summary", "")],
                "toc": [],
                "date": s.get("date", "")
            })

    # 2. Synthesize using AI if Gemini Key is available, else fallback
    gemini_key = config.get("gemini_api_key", "").strip()
    cheat_sheet_data = None

    if gemini_key and genai:
        try:
            client = genai.Client(api_key=gemini_key)
            prompt = f"""Tu es un professeur d'université d'élite.
Génère une 'Fiche de Synthèse Express / Cheat Sheet' pour la veille du contrôle pour le module suivant :
MODULE : {module_name}
NOMBRE DE SÉANCES : {len(sessions_data)}

DONNÉES DES SÉANCES ENREGISTRÉES :
{json.dumps(sessions_data, ensure_ascii=False, indent=2)}

Consignes impératives :
1. Sois ultra-synthétique, dense, direct et pratique pour un étudiant la veille de l'examen.
2. Structure ta réponse UNIQUEMENT en JSON valide suivant ce schéma :
{{
  "quick_overview": "Résumé global en 2-3 phrases des enjeux du module.",
  "essential_rules": [
    "Règle ou définition n°1 (ex: formule, principe clé)",
    "Règle ou définition n°2...",
    "Règle ou définition n°3..."
  ],
  "sessions_synthesis": [
    {{
      "session_name": "Titre séance",
      "core_concept": "Concept central expliqué en 1 phrase",
      "must_remember": ["Point clé A", "Point clé B"]
    }}
  ],
  "exam_traps": [
    {{
      "trap": "Piège classique d'examen posé par les professeurs",
      "solution": "Ce qu'il faut écrire pour avoir tous les points"
    }}
  ],
  "express_qa": [
    {{
      "q": "Question type d'examen fréquente",
      "a": "Réponse modèle concise et précise"
    }}
  ]
}}
"""
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            cheat_sheet_data = json.loads(response.text)
        except Exception as e:
            print(f"Gemini cheat sheet note: {e}")

    # Fallback algorithmic synthesis if AI call fails or key is missing
    if not cheat_sheet_data:
        all_takeaways = []
        for s in sessions_data:
            all_takeaways.extend(s.get("takeaways", []))

        cheat_sheet_data = {
            "quick_overview": f"Synthèse générale du module {module_name} compilée à partir de {len(sessions_data)} séance(s) enregistrée(s).",
            "essential_rules": all_takeaways[:6] if all_takeaways else [
                "Maîtriser les définitions fondamentales introduites en séance 1.",
                "Savoir appliquer les règles et formules aux cas pratiques de travaux dirigés.",
                "Faire attention aux conditions aux limites lors des exercices d'application."
            ],
            "sessions_synthesis": [
                {
                    "session_name": s.get("title", f"Séance {i+1}"),
                    "core_concept": (s.get("summary", "")[:120] + "...") if s.get("summary") else "Concepts clés et travaux dirigés.",
                    "must_remember": s.get("takeaways", [])[:3]
                }
                for i, s in enumerate(sessions_data)
            ],
            "exam_traps": [
                {
                    "trap": "Confondre les syntaxes ou les définitions voisines.",
                    "solution": "Toujours préciser le contexte et justifier chaque étape du raisonnement."
                },
                {
                    "trap": "Oublier de vérifier les conditions préalables avant d'appliquer une formule.",
                    "solution": "Commencer chaque réponse par énoncer les hypothèses de départ."
                }
            ],
            "express_qa": [
                {
                    "q": f"Quel est l'objectif majeur du module {module_name} ?",
                    "a": "Comprendre les principes théoriques fondamentaux et savoir les appliquer rigoureusement en situation d'examen."
                }
            ]
        }

    # 3. Build PDF
    _build_cheat_sheet_pdf(module_name, len(sessions), cheat_sheet_data, pdf_path)
    return pdf_path

def _build_cheat_sheet_pdf(module_name: str, total_sessions: int, data: Dict, pdf_path: str):
    pdf = CheatSheetPDF(module_name)
    pdf.alias_nb_pages()
    pdf.add_page()

    # Title Banner
    pdf.set_fill_color(15, 23, 42) # Dark Slate #0F172A
    pdf.rect(10, 18, 190, 24, style="F")

    pdf.set_xy(14, 21)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(248, 250, 252)
    pdf.cell(140, 7, f"FICHE DE SYNTHÈSE EXPRESS : {module_name.upper()}", ln=0)

    # Sessions Pill
    pdf.set_fill_color(37, 99, 235)
    pdf.set_xy(156, 21)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(40, 7, f"{total_sessions} SÉANCES", align="C", fill=True)

    pdf.set_xy(14, 28)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(180, 6, "Guide condensé de révision pour la veille du contrôle  -  Formules, Règles d'Or & Pièges d'Examen", ln=1)

    pdf.ln(12)

    # 1. Vue d'ensemble rapide
    overview = data.get("quick_overview", "")
    if overview:
        pdf.set_fill_color(241, 245, 249)
        pdf.set_text_color(30, 41, 59)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(190, 6, "  1. EN BREF (VUE D'ENSEMBLE) :", fill=True, ln=1)
        pdf.set_font("Helvetica", "", 9)
        pdf.ln(1)
        pdf.multi_cell(190, 5, overview)
        pdf.ln(3)

    # 2. Règles d'or & Formules Essentielles
    rules = data.get("essential_rules", [])
    if rules:
        pdf.set_fill_color(219, 234, 254) # Light Blue
        pdf.set_text_color(30, 58, 138)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(190, 6, "  2. RÈGLES D'OR, FORMULES & DÉFINITIONS INCONTOURNABLES :", fill=True, ln=1)
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(15, 23, 42)
        for r in rules:
            pdf.cell(6, 5, " * ", align="C")
            pdf.multi_cell(184, 5, r)
        pdf.ln(3)

    # 3. Synthèse par Séance
    sessions_synth = data.get("sessions_synthesis", [])
    if sessions_synth:
        pdf.set_fill_color(241, 245, 249)
        pdf.set_text_color(30, 41, 59)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(190, 6, "  3. CE QU'IL FAUT RETENIR PAR SÉANCE :", fill=True, ln=1)
        pdf.ln(2)

        for i, s in enumerate(sessions_synth, 1):
            s_name = s.get("session_name", f"Séance {i}")
            core = s.get("core_concept", "")
            must = s.get("must_remember", [])

            pdf.set_fill_color(248, 250, 252)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(37, 99, 235)
            pdf.cell(190, 5, f"  [Séance {i}] : {s_name}", fill=True, ln=1)

            if core:
                pdf.set_font("Helvetica", "I", 8.5)
                pdf.set_text_color(71, 85, 105)
                pdf.cell(8, 4, "")
                pdf.multi_cell(182, 4, f"Concept clé : {core}")

            if must:
                pdf.set_font("Helvetica", "", 8.5)
                pdf.set_text_color(15, 23, 42)
                for m in must:
                    pdf.cell(10, 4, "")
                    pdf.cell(4, 4, "-")
                    pdf.multi_cell(176, 4, m)
            pdf.ln(1)
        pdf.ln(2)

    # 4. Pièges d'Examen Classiques (High-Yield Exam Traps)
    traps = data.get("exam_traps", [])
    if traps:
        pdf.set_fill_color(254, 226, 226) # Light Red
        pdf.set_text_color(153, 27, 27)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(190, 6, "  4. ATTENTION : LES PIÈGES CLASSIQUES D'EXAMEN & CONTRÔLE :", fill=True, ln=1)
        pdf.ln(2)

        for t in traps:
            trap_desc = t.get("trap", "")
            sol = t.get("solution", "")

            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(185, 28, 28)
            pdf.cell(6, 4, "[!]")
            pdf.multi_cell(184, 4, f"Piège : {trap_desc}")

            pdf.set_font("Helvetica", "", 8.5)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(6, 4, "")
            pdf.multi_cell(184, 4, f"Conseil pour l'examen : {sol}")
            pdf.ln(1)
        pdf.ln(2)

    # 5. Questions Express Types d'Examen
    qa = data.get("express_qa", [])
    if qa:
        pdf.set_fill_color(220, 252, 231) # Light Green
        pdf.set_text_color(22, 101, 52)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(190, 6, "  5. QUESTIONS EXPRESS TYPES DE CONTRÔLE :", fill=True, ln=1)
        pdf.ln(2)

        for item in qa:
            q = item.get("q", "")
            a = item.get("a", "")

            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(6, 4, "Q :")
            pdf.multi_cell(184, 4, q)

            pdf.set_font("Helvetica", "I", 8.5)
            pdf.set_text_color(30, 41, 59)
            pdf.cell(6, 4, "R :")
            pdf.multi_cell(184, 4, a)
            pdf.ln(1)

    pdf.output(pdf_path)
