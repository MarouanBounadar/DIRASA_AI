import os
import re
from fpdf import FPDF

FONT_FAMILY = "Helvetica"
USE_WINDOWS_FONTS = False

def setup_fonts(pdf: FPDF):
    global FONT_FAMILY, USE_WINDOWS_FONTS
    regular = r"C:\Windows\Fonts\segoeui.ttf"
    bold = r"C:\Windows\Fonts\segoeuib.ttf"
    italic = r"C:\Windows\Fonts\segoeuii.ttf"

    if os.path.exists(regular) and os.path.exists(bold):
        try:
            pdf.add_font("SegoeUI", "", regular)
            pdf.add_font("SegoeUI", "B", bold)
            if os.path.exists(italic):
                pdf.add_font("SegoeUI", "I", italic)
            else:
                pdf.add_font("SegoeUI", "I", regular)
            FONT_FAMILY = "SegoeUI"
            USE_WINDOWS_FONTS = True
            return
        except Exception as e:
            print(f"Font loading fallback: {e}")
            
    FONT_FAMILY = "Helvetica"
    USE_WINDOWS_FONTS = False

class CoursePDF(FPDF):
    def __init__(self, course_title: str, module_name: str, eco_mode: bool = False):
        super().__init__()
        self.course_title = course_title
        self.module_name = module_name
        self.eco_mode = eco_mode
        self.set_auto_page_break(auto=True, margin=15)
        setup_fonts(self)

    def header(self):
        if self.page_no() > 1:
            self.set_font(FONT_FAMILY, "I", 8)
            self.set_text_color(100, 116, 139) # slate-500
            eco_tag = " [Édition Éco-Photocopie]" if self.eco_mode else ""
            header_text = f"{self.module_name} | {self.course_title}{eco_tag}"
            if len(header_text) > 85:
                header_text = header_text[:82] + "..."
            self.cell(0, 8, header_text, border="B", align="L", new_x="LMARGIN", new_y="NEXT")
            self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font(FONT_FAMILY, "", 8)
        self.set_text_color(148, 163, 184) # slate-400
        page_str = f"Page {self.page_no()} / {{nb}}"
        brand_str = "DIRASA AI - Plateforme Universitaire Intelligente"
        self.cell(120, 10, brand_str, align="L")
        self.cell(0, 10, page_str, align="R")

    def chapter_title(self, num: int, label: str):
        self.ln(6)
        if self.eco_mode:
            self.set_fill_color(255, 255, 255)
            self.set_draw_color(0, 0, 0)
            self.set_line_width(0.6)
            self.set_text_color(0, 0, 0)
            self.set_font(FONT_FAMILY, "B", 12)
            title_text = f"  CHAPITRE {num} : {label.upper()}"
            self.cell(0, 8, title_text, border="TB", fill=False, new_x="LMARGIN", new_y="NEXT")
        else:
            self.set_fill_color(30, 58, 138)  # Deep royal blue
            self.set_text_color(255, 255, 255)
            self.set_font(FONT_FAMILY, "B", 13)
            title_text = f"  CHAPITRE {num} : {label.upper()}"
            self.cell(0, 10, title_text, fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_text_color(30, 41, 59)

    def section_title(self, subtitle: str):
        self.ln(3)
        self.set_font(FONT_FAMILY, "B", 11)
        if self.eco_mode:
            self.set_text_color(0, 0, 0)
        else:
            self.set_text_color(37, 99, 235)  # Bright blue
        self.cell(0, 8, f">> {subtitle}", new_x="LMARGIN", new_y="NEXT")
        self.ln(1)
        self.set_text_color(51, 65, 85)

    def body_paragraph(self, text: str):
        self.set_font(FONT_FAMILY, "", 10)
        self.set_text_color(51, 65, 85)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def bullet_point(self, text: str):
        self.set_font(FONT_FAMILY, "", 9.5)
        self.set_text_color(71, 85, 105)
        bullet = "-"
        self.cell(6, 5, bullet, align="R")
        self.multi_cell(0, 5, f" {text}")
        self.ln(1)

    def callout_box(self, title: str, content: str, box_type: str = "definition"):
        """
        Renders a styled callout box with a colored border or clean ink-saver outline.
        box_type: 'definition' (blue), 'formula' (green), 'warning' (orange)
        """
        if self.eco_mode:
            self.ln(2)
            self.set_draw_color(0, 0, 0)
            self.set_line_width(0.5)
            self.set_font(FONT_FAMILY, "B", 9)
            self.set_text_color(0, 0, 0)
            self.cell(0, 6, f"[ {box_type.upper()} ]  {title}", border="TLR", fill=False, new_x="LMARGIN", new_y="NEXT")
            self.set_font(FONT_FAMILY, "", 9.5)
            self.set_text_color(20, 20, 20)
            self.multi_cell(0, 5, content, border="BLR", fill=False)
            self.ln(3)
            return

        if box_type == "definition":
            bg_r, bg_g, bg_b = 239, 246, 255 # Light blue
            border_r, border_g, border_b = 59, 130, 246 # Blue 500
            badge = "[ DÉFINITION CLÉ ]"
        elif box_type == "formula":
            bg_r, bg_g, bg_b = 240, 253, 244 # Light emerald
            border_r, border_g, border_b = 34, 197, 94 # Green 500
            badge = "[ RÈGLE / FORMULE ]"
        else: # warning / advice
            bg_r, bg_g, bg_b = 254, 243, 199 # Light amber
            border_r, border_g, border_b = 217, 119, 6 # Amber 600
            badge = "[ CONSEIL DU PROFESSEUR / PIÈGE D'EXAMEN ]"

        self.ln(2)
        # Background fill
        self.set_fill_color(bg_r, bg_g, bg_b)
        self.set_draw_color(border_r, border_g, border_b)
        self.set_line_width(0.6)

        # Print header
        self.set_font(FONT_FAMILY, "B", 9)
        self.set_text_color(border_r, border_g, border_b)
        self.cell(0, 6, f"{badge}  {title}", border="TLR", fill=True, new_x="LMARGIN", new_y="NEXT")
        
        # Print content
        self.set_font(FONT_FAMILY, "", 9.5)
        self.set_text_color(30, 41, 59)
        self.multi_cell(0, 5, content, border="BLR", fill=True)
        self.ln(3)

def sanitize_text(text: str) -> str:
    """Cleans text for PDF rendering."""
    if not text:
        return ""
    if not USE_WINDOWS_FONTS:
        replacements = {
            '’': "'", '‘': "'", '“': '"', '”': '"',
            '–': '-', '—': '-', '…': '...',
            'œ': 'oe', 'Œ': 'OE', '«': '"', '»': '"',
            '•': '-', '→': '->', '⇒': '==>', '⇔': '<=>',
            '≤': '<=', '≥': '>=', '≠': '!=', '±': '+/-',
            '²': '2', '³': '3', '\u202f': ' ', '\u00a0': ' ',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text.encode('latin-1', 'replace').decode('latin-1')
    return text

def generate_course_pdf(course_data: dict, output_filepath: str, eco_mode: bool = False) -> str:
    """
    Takes the structured course dict and produces a clean, high-grade university PDF.
    Supports eco_mode=True for ink-saving black & white university photocopy printing.
    """
    title = sanitize_text(course_data.get("title", "Séance de Cours"))
    module = sanitize_text(course_data.get("module", "Module Académique"))
    instructor = sanitize_text(course_data.get("instructor", "Enseignant / Professeur"))
    duration = sanitize_text(course_data.get("duration_summary", "Enregistrement de séance"))
    summary = sanitize_text(course_data.get("summary", ""))

    pdf = CoursePDF(course_title=title, module_name=module, eco_mode=eco_mode)
    pdf.alias_nb_pages()
    pdf.add_page()

    if eco_mode:
        # Minimalist white background with clean double borders
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.6)
        pdf.rect(10, 10, 190, 48, 'D')
        pdf.set_line_width(0.2)
        pdf.rect(11, 11, 188, 46, 'D')

        # Module badge
        pdf.set_xy(15, 14)
        pdf.set_font(FONT_FAMILY, "B", 9)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(0, 6, f"[ MODULE : {module.upper()} ]", new_x="LMARGIN", new_y="NEXT")

        # Course Main Title
        pdf.set_xy(15, 21)
        pdf.set_font(FONT_FAMILY, "B", 14)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(180, 6.5, title)

        # Metadata bar
        pdf.set_xy(15, 47)
        pdf.set_font(FONT_FAMILY, "I", 8.5)
        pdf.set_text_color(60, 60, 60)
        meta_str = f"Intervenant : {instructor}  |  Format : {duration}  |  DIRASA AI (Édition Éco-Photocopie)"
        if course_data.get("slides_used"):
            meta_str += f"  |  Slides ({course_data.get('slides_count', 0)} diapos)"
        pdf.cell(0, 5, meta_str)
    else:
        # --- COVER / HERO BANNER ---
        pdf.set_fill_color(15, 23, 42) # Dark Slate Blue 900
        pdf.rect(10, 10, 190, 50, 'F')
        
        # Module badge
        pdf.set_xy(15, 16)
        pdf.set_font(FONT_FAMILY, "B", 10)
        pdf.set_text_color(56, 189, 248) # Sky blue
        pdf.cell(0, 6, f"MODULE : {module.upper()}", new_x="LMARGIN", new_y="NEXT")

        # Course Main Title
        pdf.set_xy(15, 24)
        pdf.set_font(FONT_FAMILY, "B", 15)
        pdf.set_text_color(255, 255, 255)
        pdf.multi_cell(180, 7.5, title)

        # Metadata bar inside banner
        pdf.set_xy(15, 48)
        pdf.set_font(FONT_FAMILY, "I", 9)
        pdf.set_text_color(203, 213, 225)
        meta_str = f"Intervenant : {instructor}  |  Format : {duration}  |  Généré par DIRASA AI"
        if course_data.get("slides_used"):
            meta_str += f"  |  Slides Fusionnées ({course_data.get('slides_count', 0)} diapos)"
        pdf.cell(0, 6, meta_str)

    pdf.set_y(65)
    pdf.ln(2)

    # --- OBJECTIFS PÉDAGOGIQUES & PRÉREQUIS ---
    objectives = course_data.get("learning_objectives", [])
    prereqs = course_data.get("prerequisites", [])

    if objectives or prereqs:
        pdf.set_fill_color(248, 250, 252) # Slate 50
        pdf.set_draw_color(226, 232, 240)
        pdf.set_font(FONT_FAMILY, "B", 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 8, "OBJECTIFS DE LA SÉANCE & COMPÉTENCES VISÉES", border="B", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        for obj in objectives:
            pdf.bullet_point(f"[OK] {sanitize_text(obj)}")

        if prereqs:
            pdf.ln(2)
            pdf.set_font(FONT_FAMILY, "B", 9)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(0, 6, "Prérequis recommandés :", new_x="LMARGIN", new_y="NEXT")
            for req in prereqs:
                pdf.bullet_point(f"* {sanitize_text(req)}")
        pdf.ln(4)

    # --- RÉSUMÉ EXÉCUTIF ---
    if summary:
        pdf.set_font(FONT_FAMILY, "B", 11)
        pdf.set_text_color(30, 58, 138)
        pdf.cell(0, 8, "RÉSUMÉ SYNTHÉTIQUE DE LA SÉANCE", new_x="LMARGIN", new_y="NEXT")
        pdf.body_paragraph(summary)
        pdf.ln(2)

    # --- SOMMAIRE (TABLE OF CONTENTS) ---
    toc = course_data.get("table_of_contents", [])
    if toc:
        pdf.set_fill_color(241, 245, 249)
        pdf.set_font(FONT_FAMILY, "B", 10)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(0, 8, "PLAN DU COURS (SOMMAIRE)", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        for item in toc:
            pdf.bullet_point(sanitize_text(item))
        pdf.ln(4)

    # --- CARTE MENTALE / MINDMAP DU COURS ---
    mindmap = course_data.get("mindmap", [])
    if mindmap:
        pdf.ln(3)
        pdf.set_fill_color(99, 102, 241) # Indigo 500
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(FONT_FAMILY, "B", 11)
        pdf.cell(0, 8, "  CARTE CONCEPTUELLE & STRUCTURE VISUELLE (MINDMAP)", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        pdf.set_text_color(30, 41, 59)
        for branch in mindmap:
            topic = sanitize_text(branch.get("topic", ""))
            pdf.set_font(FONT_FAMILY, "B", 10)
            pdf.set_text_color(67, 56, 202) # Indigo 700
            pdf.cell(0, 6, f"+- {topic}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(FONT_FAMILY, "", 9)
            pdf.set_text_color(71, 85, 105)
            for sub in branch.get("subtopics", []):
                pdf.bullet_point(f"    |-- {sanitize_text(sub)}")
            pdf.ln(1)
        pdf.ln(3)

    # --- CHAPITRES DÉTAILLÉS ---
    chapters = course_data.get("chapters", [])
    for ch in chapters:
        ch_num = ch.get("number", 1)
        ch_title = sanitize_text(ch.get("title", f"Chapitre {ch_num}"))
        pdf.chapter_title(ch_num, ch_title)

        intro = sanitize_text(ch.get("introduction", ""))
        if intro:
            pdf.body_paragraph(intro)

        # Sections
        sections = ch.get("sections", [])
        for sec in sections:
            subtitle = sanitize_text(sec.get("subtitle", ""))
            if subtitle:
                pdf.section_title(subtitle)
            content = sanitize_text(sec.get("content", ""))
            if content:
                pdf.body_paragraph(content)
            bullets = sec.get("bullet_points", [])
            for bp in bullets:
                pdf.bullet_point(sanitize_text(bp))

        # Definitions Callout
        defs = ch.get("key_definitions", [])
        for d in defs:
            term = sanitize_text(d.get("term", ""))
            def_text = sanitize_text(d.get("definition", ""))
            pdf.callout_box(title=term, content=def_text, box_type="definition")

        # Formulas Callout
        formulas = ch.get("formulas_or_rules", [])
        for f in formulas:
            f_name = sanitize_text(f.get("name", ""))
            f_content = sanitize_text(f.get("content", ""))
            f_exp = sanitize_text(f.get("explanation", ""))
            full_box = f"{f_content}\n-> {f_exp}" if f_exp else f_content
            pdf.callout_box(title=f_name, content=full_box, box_type="formula")

        # Teacher advice Callout
        prof_notes = sanitize_text(ch.get("professor_notes", ""))
        if prof_notes:
            pdf.callout_box(title="Remarque d'Examen", content=prof_notes, box_type="warning")

    # --- POINTS ESSENTIELS À RETENIR (KEY TAKEAWAYS) ---
    takeaways = course_data.get("key_takeaways", [])
    if takeaways:
        pdf.ln(4)
        pdf.set_fill_color(16, 185, 129) # Emerald Green
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(FONT_FAMILY, "B", 12)
        pdf.cell(0, 9, "  FICHE DE RÉVISION RAPIDE : LES POINTS CLÉS POUR L'EXAMEN", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        pdf.set_text_color(30, 41, 59)
        for t in takeaways:
            pdf.bullet_point(f"[!] {sanitize_text(t)}")
        pdf.ln(4)

    # --- QUESTIONS / RÉPONSES D'EXAMEN ---
    exam_questions = course_data.get("exam_questions", [])
    if exam_questions:
        pdf.ln(4)
        pdf.set_fill_color(225, 29, 72) # Rose Red
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(FONT_FAMILY, "B", 12)
        pdf.cell(0, 9, "  AUTO-ÉVALUATION & QUESTIONS TYPE EXAMEN / CONCOURS", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
        pdf.set_text_color(30, 41, 59)

        for i, q in enumerate(exam_questions, 1):
            q_text = sanitize_text(q.get("question", ""))
            a_text = sanitize_text(q.get("answer", ""))
            
            pdf.set_font(FONT_FAMILY, "B", 10)
            pdf.set_text_color(190, 18, 60) # Rose 700
            pdf.cell(0, 6, f"Q{i} : {q_text}", new_x="LMARGIN", new_y="NEXT")
            
            pdf.set_font(FONT_FAMILY, "", 9.5)
            pdf.set_text_color(30, 41, 59)
            pdf.multi_cell(0, 5, f"Réponse attendue : {a_text}")
            pdf.ln(2)

    # --- FICHE AIDE-MÉMOIRE / CHEAT SHEET CONDENSÉE ---
    cs = course_data.get("cheat_sheet", {})
    if cs and any(cs.values()):
        pdf.add_page()
        pdf.set_fill_color(30, 41, 59) # Slate 800
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(FONT_FAMILY, "B", 13)
        pdf.cell(0, 10, "  FICHE AIDE-MÉMOIRE EXPRESS (RÉVISION ULTIME EN 1 PAGE)", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # Definitions flash
        core_defs = cs.get("core_definitions", [])
        if core_defs:
            pdf.set_font(FONT_FAMILY, "B", 10.5)
            pdf.set_text_color(37, 99, 235)
            pdf.cell(0, 7, ">> DÉFINITIONS ESSENTIELLES :", new_x="LMARGIN", new_y="NEXT")
            for cd in core_defs:
                pdf.bullet_point(sanitize_text(cd))
            pdf.ln(2)

        # Rules / formulas flash
        rules = cs.get("essential_rules", [])
        if rules:
            pdf.set_font(FONT_FAMILY, "B", 10.5)
            pdf.set_text_color(16, 185, 129)
            pdf.cell(0, 7, ">> RÈGLES D'OR & FORMULES À CONNAÎTRE :", new_x="LMARGIN", new_y="NEXT")
            for r in rules:
                pdf.bullet_point(sanitize_text(r))
            pdf.ln(2)

        # Pitfalls flash
        traps = cs.get("exam_pitfalls", [])
        if traps:
            pdf.set_font(FONT_FAMILY, "B", 10.5)
            pdf.set_text_color(225, 29, 72)
            pdf.cell(0, 7, ">> PIÈGES D'EXAMEN À NE PAS COMMETTRE :", new_x="LMARGIN", new_y="NEXT")
            for tr in traps:
                pdf.bullet_point(f"[PIEGE] {sanitize_text(tr)}")
            pdf.ln(3)

    # --- DIAPOSITIVES / SLIDES CAPTURÉES DE LA SÉANCE ---
    slides = course_data.get("slides", [])
    valid_slides = [s for s in slides if os.path.exists(s)]
    if valid_slides:
        pdf.add_page()
        pdf.set_fill_color(14, 165, 233) # Sky 500
        pdf.set_text_color(255, 255, 255)
        pdf.set_font(FONT_FAMILY, "B", 12)
        pdf.cell(0, 9, "  DIAPOSITIVES ET SCHÉMAS CLÉS DE LA SÉANCE", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

        for i, s_path in enumerate(valid_slides, 1):
            if pdf.get_y() > 210:
                pdf.add_page()
            pdf.set_font(FONT_FAMILY, "B", 9)
            pdf.set_text_color(71, 85, 105)
            pdf.cell(0, 6, f"Diapositive / Capture {i} :", new_x="LMARGIN", new_y="NEXT")
            # Image display: width 170mm
            pdf.image(s_path, x=20, w=170)
            pdf.ln(5)

    os.makedirs(os.path.dirname(os.path.abspath(output_filepath)), exist_ok=True)
    pdf.output(output_filepath)
    return output_filepath

def generate_eco_course_pdf(course_data: dict, output_dir: str) -> str:
    """
    Generates an eco-friendly photocopy black & white PDF version of the course.
    """
    os.makedirs(output_dir, exist_ok=True)
    clean_title = sanitize_text(course_data.get("title", "Cours")).replace(" ", "_")
    clean_title = "".join([c for c in clean_title if c.isalnum() or c in "_-"])[:40]
    out_path = os.path.join(output_dir, f"{clean_title}_Eco_Photocopie.pdf")
    return generate_course_pdf(course_data, out_path, eco_mode=True)
