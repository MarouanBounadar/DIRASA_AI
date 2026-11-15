import os
import sys
import json
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import webbrowser

# Local imports
from config import load_config, save_config
from downloader import download_audio
from ai_transcription import process_recording, ask_professor_question, get_demo_course_data
from pdf_generator import generate_course_pdf, generate_eco_course_pdf
from tools import export_anki_csv
from recorder import AudioRecorder
from exam_service import generate_mock_exam, grade_mock_exam
from library_service import load_courses_library, add_course_to_library, delete_course_from_library, get_unique_modules, filter_courses, group_courses_by_module, get_sessions_for_module, get_course_short_label
from stats_service import calculate_dashboard_metrics, record_quiz_result, record_exam_result, load_stats
from cheat_sheet_service import generate_module_cheat_sheet
from slides_service import extract_text_from_slides
from spaced_repetition_service import calculate_spaced_repetition_schedule
from voice_service import VoiceSpeaker, transcribe_vocal_question
from utils import open_file, open_directory, is_valid_url

# Configure appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class DirasaApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("DIRASA AI - Plateforme Universitaire & Révision Intelligente (100% Gratuit)")
        self.geometry("1150x780")
        self.minsize(980, 680)

        # App state
        self.config = load_config()
        self.is_processing = False
        
        # Load user's last saved course if exists, otherwise start completely clean (None)
        latest_json_path = os.path.join(self.config.get("output_dir", "exports"), "latest_course.json")
        self.latest_course_data = None
        if os.path.exists(latest_json_path):
            try:
                import json
                with open(latest_json_path, "r", encoding="utf-8") as f:
                    self.latest_course_data = json.load(f)
            except Exception as e:
                print(f"Note loading latest course: {e}")

        self.latest_pdf_path = None
        self.selected_local_file = None
        self.selected_slides_file = None

        # Voice & Speech Tutor State
        self.voice_speaker = VoiceSpeaker()
        self.is_vocal_recording = False
        self.vocal_recorder = AudioRecorder()
        self.latest_prof_reply = ""

        # Recorder State
        self.recorder = AudioRecorder()
        self.recorded_file_path = None
        self.record_timer_id = None

        # Mock Exam State
        self.exam_in_progress = False
        self.exam_questions = []
        self.exam_seconds_remaining = 0
        self.exam_timer_id = None
        self.exam_answer_boxes = {}

        # Quiz State
        self.current_quiz_index = 0
        self.quiz_score = 0
        self.quiz_selected_option = tk.IntVar(value=-1)
        self.quiz_answered = False

        # Flashcards State
        self.current_card_index = 0
        self.card_is_flipped = False

        # Library State
        self.library_courses = []
        self._top_sessions_map = {}
        self._suppress_top_sync = False

        # Build UI layout
        self._build_sidebar()
        self._build_main_container()

        # Show default tab
        self.select_tab("generator")

    # -------------------------------------------------------------
    # SIDEBAR BUILDER
    # -------------------------------------------------------------
    def _build_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color="#0F172A")
        self.sidebar_frame.pack(side="left", fill="y")
        self.sidebar_frame.pack_propagate(False)

        # Brand header
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="🎓 DIRASA AI", 
            font=ctk.CTkFont(size=23, weight="bold"),
            text_color="#38BDF8"
        )
        self.logo_label.pack(padx=20, pady=(22, 3))

        self.subtitle_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="Séance -> Cours PDF & Révision\n100% Gratuit (Faboor)", 
            font=ctk.CTkFont(size=11),
            text_color="#94A3B8"
        )
        self.subtitle_label.pack(padx=20, pady=(0, 20))

        # Nav Buttons
        self.nav_buttons = {}
        nav_items = [
            ("generator", "🚀 Nouveau Cours"),
            ("dashboard", "📊 Tableau de Bord (Stats)"),
            ("library", "📚 Bibliothèque des Cours"),
            ("record", "🎙️ Enregistreur d'Amphi"),
            ("exam", "📝 Examen Blanc (/20)"),
            ("quiz", "🎯 Quiz QCM Interactif"),
            ("chat", "💬 Sawel l'Prof (Chat)"),
            ("flashcards", "🧠 Flashcards & Anki"),
            ("preview", "📖 Aperçu & Mindmap"),
            ("transcript", "📝 Transcription Brute"),
            ("settings", "⚙️ Paramètres & Clés"),
            ("help", "💡 Guide & Astuces")
        ]

        for tab_id, text in nav_items:
            btn = ctk.CTkButton(
                self.sidebar_frame,
                text=text,
                height=38,
                corner_radius=8,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
                fg_color="transparent",
                text_color="#E2E8F0",
                hover_color="#1E293B",
                command=lambda tid=tab_id: self.select_tab(tid)
            )
            btn.pack(padx=12, pady=4, fill="x")
            self.nav_buttons[tab_id] = btn

        # Spacer
        self.sidebar_spacer = ctk.CTkLabel(self.sidebar_frame, text="")
        self.sidebar_spacer.pack(expand=True, fill="both")

        # Bottom Provider Status
        self.provider_badge = ctk.CTkFrame(self.sidebar_frame, fg_color="#1E293B", corner_radius=8)
        self.provider_badge.pack(padx=12, pady=12, fill="x")

        self.provider_status_label = ctk.CTkLabel(
            self.provider_badge,
            text=self._get_provider_status_text(),
            font=ctk.CTkFont(size=11),
            text_color="#38BDF8",
            justify="center"
        )
        self.provider_status_label.pack(padx=8, pady=8)

    def _get_provider_status_text(self):
        gemini_k = bool(self.config.get("gemini_api_key"))
        groq_k = bool(self.config.get("groq_api_key"))
        if gemini_k:
            return "● Gemini 3.5 Flash (Actif)"
        elif groq_k:
            return "● Groq Whisper (Actif)"
        else:
            return "● Mode Démo Gratuit"

    def _build_main_container(self):
        self.main_container = ctk.CTkFrame(self, fg_color="#090D16", corner_radius=0)
        self.main_container.pack(side="right", expand=True, fill="both")

        # Top Active Course Selector Bar (Pinned across all tabs)
        self._build_top_active_course_bar()

        self.tabs = {
            "generator": self._build_generator_tab(),
            "dashboard": self._build_dashboard_tab(),
            "library": self._build_library_tab(),
            "record": self._build_record_tab(),
            "exam": self._build_exam_tab(),
            "quiz": self._build_quiz_tab(),
            "chat": self._build_chat_tab(),
            "flashcards": self._build_flashcards_tab(),
            "preview": self._build_preview_tab(),
            "transcript": self._build_transcript_tab(),
            "settings": self._build_settings_tab(),
            "help": self._build_help_tab(),
        }

        # Initial synchronization of top bar with loaded course / library
        self._sync_top_active_bar()

    # -------------------------------------------------------------
    # TOP ACTIVE COURSE SELECTOR BAR
    # -------------------------------------------------------------
    def _build_top_active_course_bar(self):
        self.top_active_bar_frame = ctk.CTkFrame(
            self.main_container,
            fg_color="#0F172A",
            corner_radius=10,
            border_width=1,
            border_color="#1E293B",
            height=54
        )
        self.top_active_bar_frame.pack(side="top", fill="x", padx=22, pady=(12, 4))
        self.top_active_bar_frame.pack_propagate(False)

        bar_inner = ctk.CTkFrame(self.top_active_bar_frame, fg_color="transparent")
        bar_inner.pack(fill="both", expand=True, padx=12, pady=6)

        # Label: Cours Actif
        ctk.CTkLabel(
            bar_inner,
            text="🎯 Cours Actif :",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38BDF8"
        ).pack(side="left", padx=(4, 8))

        # Module Dropdown
        self.top_module_var = ctk.StringVar(value="-- Aucun module --")
        self.top_module_menu = ctk.CTkOptionMenu(
            bar_inner,
            variable=self.top_module_var,
            values=["-- Aucun module --"],
            height=32,
            width=180,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#1E293B",
            button_color="#2563EB",
            button_hover_color="#1D4ED8",
            command=self._on_top_module_changed
        )
        self.top_module_menu.pack(side="left", padx=(0, 8))

        # Session Dropdown
        self.top_session_var = ctk.StringVar(value="-- Aucune séance --")
        self.top_session_menu = ctk.CTkOptionMenu(
            bar_inner,
            variable=self.top_session_var,
            values=["-- Aucune séance --"],
            height=32,
            width=280,
            font=ctk.CTkFont(size=11),
            fg_color="#1E293B",
            button_color="#0EA5E9",
            button_hover_color="#0284C7",
            command=self._on_top_session_changed
        )
        self.top_session_menu.pack(side="left", padx=(0, 8))

        # Quick Navigation Shortcuts (Right side)
        # 1. PDF
        self.top_pdf_btn = ctk.CTkButton(
            bar_inner,
            text="📄 PDF",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=30,
            width=65,
            fg_color="#334155",
            hover_color="#475569",
            command=self._open_top_active_pdf
        )
        self.top_pdf_btn.pack(side="right", padx=(3, 2))

        # 1b. PDF Éco
        self.top_eco_btn = ctk.CTkButton(
            bar_inner,
            text="🖨️ Éco",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=30,
            width=62,
            fg_color="#475569",
            hover_color="#64748B",
            command=lambda: self._generate_eco_pdf_action(None)
        )
        self.top_eco_btn.pack(side="right", padx=(3, 2))

        # 2. Examen Blanc
        self.top_exam_btn = ctk.CTkButton(
            bar_inner,
            text="📝 Examen",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=30,
            width=78,
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            command=lambda: self.select_tab("exam")
        )
        self.top_exam_btn.pack(side="right", padx=(3, 2))

        # 3. Sawel l'Prof
        self.top_chat_btn = ctk.CTkButton(
            bar_inner,
            text="💬 Prof",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=30,
            width=70,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=lambda: self.select_tab("chat")
        )
        self.top_chat_btn.pack(side="right", padx=(3, 2))

        # 4. Quiz
        self.top_quiz_btn = ctk.CTkButton(
            bar_inner,
            text="🎯 Quiz",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=30,
            width=68,
            fg_color="#10B981",
            hover_color="#059669",
            command=lambda: self.select_tab("quiz")
        )
        self.top_quiz_btn.pack(side="right", padx=(3, 2))

    def _sync_top_active_bar(self):
        if getattr(self, "_suppress_top_sync", False):
            return

        out_dir = self.config.get("output_dir", os.path.join(os.path.dirname(__file__), "exports"))
        self.library_courses = load_courses_library(out_dir)

        if not self.library_courses:
            if hasattr(self, "top_module_menu"):
                self.top_module_menu.configure(values=["-- Aucun cours --"])
                self.top_module_var.set("-- Aucun cours --")
                self.top_session_menu.configure(values=["-- Aucune séance --"])
                self.top_session_var.set("-- Aucune séance --")
                self.top_pdf_btn.configure(state="disabled")
            return

        if hasattr(self, "top_pdf_btn"):
            self.top_pdf_btn.configure(state="normal")

        grouped = group_courses_by_module(self.library_courses)
        module_names = list(grouped.keys())

        if not module_names:
            return

        # Determine current module
        current_mod = self.latest_course_data.get("module") if self.latest_course_data else None
        if not current_mod or current_mod not in module_names:
            current_mod = module_names[0]

        if hasattr(self, "top_module_menu"):
            self.top_module_menu.configure(values=module_names)
            self.top_module_var.set(current_mod)
            self._populate_top_sessions_for_module(current_mod)

    def _populate_top_sessions_for_module(self, mod_name: str, select_course_id: str = None):
        sessions = get_sessions_for_module(self.library_courses, mod_name)
        if not sessions:
            self.top_session_menu.configure(values=["-- Aucune séance --"])
            self.top_session_var.set("-- Aucune séance --")
            return

        self._top_sessions_map.clear()
        labels = []
        target_label = None

        curr_title = self.latest_course_data.get("title") if self.latest_course_data else None

        for idx, s in enumerate(sessions, 1):
            lbl = get_course_short_label(s, session_idx=idx)
            self._top_sessions_map[lbl] = s
            labels.append(lbl)

            if select_course_id and s.get("id") == select_course_id:
                target_label = lbl
            elif not target_label and curr_title and s.get("title") == curr_title:
                target_label = lbl

        if not target_label:
            target_label = labels[-1]

        self.top_session_menu.configure(values=labels)
        self.top_session_var.set(target_label)

    def _on_top_module_changed(self, chosen_mod: str):
        if not chosen_mod or chosen_mod.startswith("--"):
            return
        self._populate_top_sessions_for_module(chosen_mod)
        selected_label = self.top_session_var.get()
        course = self._top_sessions_map.get(selected_label)
        if course:
            self._load_course_into_app(course, notify=False, target_tab=None)

    def _on_top_session_changed(self, chosen_session_lbl: str):
        if not chosen_session_lbl or chosen_session_lbl.startswith("--"):
            return
        course = self._top_sessions_map.get(chosen_session_lbl)
        if course:
            self._load_course_into_app(course, notify=False, target_tab=None)

    def _open_top_active_pdf(self):
        if self.latest_pdf_path and os.path.exists(self.latest_pdf_path):
            open_file(self.latest_pdf_path)
        else:
            messagebox.showwarning(
                "Fichier PDF non trouvé",
                "Le fichier PDF de cette séance est introuvable ou n'a pas encore été généré."
            )

    def select_tab(self, tab_id):
        for tid, btn in self.nav_buttons.items():
            if tid == tab_id:
                btn.configure(fg_color="#2563EB", text_color="#FFFFFF")
            else:
                btn.configure(fg_color="transparent", text_color="#E2E8F0")

        if tab_id == "dashboard" and hasattr(self, "_refresh_dashboard_view"):
            self._refresh_dashboard_view()
        elif tab_id == "library" and hasattr(self, "_reload_library_data"):
            self._reload_library_data()

        for tid, frame in self.tabs.items():
            if tid == tab_id:
                frame.pack(fill="both", expand=True, padx=22, pady=(6, 18))
            else:
                frame.pack_forget()

    # -------------------------------------------------------------
    # TAB 1: GENERATOR
    # -------------------------------------------------------------
    def _build_generator_tab(self):
        frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")

        title_lbl = ctk.CTkLabel(
            frame, 
            text="Générateur de Cours PDF & Outils de Révision", 
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#F8FAFC"
        )
        title_lbl.pack(anchor="w", pady=(0, 4))

        desc_lbl = ctk.CTkLabel(
            frame, 
            text="Collez le lien de votre séance (BigBlueButton, YouTube, Drive, Zoom) ou importez un fichier local.", 
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8"
        )
        desc_lbl.pack(anchor="w", pady=(0, 14))

        # Live Amphi Recording Shortcut Banner
        live_banner = ctk.CTkFrame(frame, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        live_banner.pack(fill="x", pady=(0, 16))
        
        banner_inner = ctk.CTkFrame(live_banner, fg_color="transparent")
        banner_inner.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(
            banner_inner,
            text="🎙️ Vous êtes en plein amphi ? Capturez la séance en direct via le micro de votre PC !",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38BDF8"
        ).pack(side="left")
        
        ctk.CTkButton(
            banner_inner,
            text="🔴 Ouvrir le Live Recorder ➔",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32,
            fg_color="#DC2626",
            hover_color="#B91C1C",
            command=lambda: self.select_tab("record")
        ).pack(side="right")

        # CARD 1: SOURCE
        card_source = ctk.CTkFrame(frame, fg_color="#131D31", corner_radius=12, border_width=1, border_color="#1E293B")
        card_source.pack(fill="x", pady=(0, 16), ipady=8)

        source_title = ctk.CTkLabel(
            card_source, 
            text="1. Source de la séance enregistrée", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#38BDF8"
        )
        source_title.pack(anchor="w", padx=18, pady=(8, 8))

        self.source_mode_var = ctk.StringVar(value="url")
        mode_frame = ctk.CTkFrame(card_source, fg_color="transparent")
        mode_frame.pack(fill="x", padx=18, pady=(0, 8))

        rb_url = ctk.CTkRadioButton(
            mode_frame, text="Lien Web (BigBlueButton, YouTube, Drive, Zoom...)", 
            variable=self.source_mode_var, value="url", 
            command=self._on_source_mode_change
        )
        rb_url.pack(side="left", padx=(0, 20))

        rb_file = ctk.CTkRadioButton(
            mode_frame, text="Fichier Local (MP3, MP4, WAV, M4A...)", 
            variable=self.source_mode_var, value="file",
            command=self._on_source_mode_change
        )
        rb_file.pack(side="left")

        # URL Input
        self.url_container = ctk.CTkFrame(card_source, fg_color="transparent")
        self.url_container.pack(fill="x", padx=18, pady=4)

        self.url_entry = ctk.CTkEntry(
            self.url_container, 
            placeholder_text="Collez le lien : http://visioconference... ou https://www.youtube.com/...", 
            height=42,
            font=ctk.CTkFont(size=12)
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        paste_btn = ctk.CTkButton(
            self.url_container, 
            text="📋 Coller", 
            width=85, 
            height=42,
            fg_color="#334155",
            hover_color="#475569",
            command=self._paste_clipboard
        )
        paste_btn.pack(side="right")

        # Local File Input
        self.file_container = ctk.CTkFrame(card_source, fg_color="transparent")
        self.file_path_label = ctk.CTkLabel(
            self.file_container, 
            text="Aucun fichier sélectionné", 
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color="#94A3B8"
        )
        self.file_path_label.pack(side="left", fill="x", expand=True, padx=(0, 10))

        browse_btn = ctk.CTkButton(
            self.file_container, 
            text="📁 Parcourir...", 
            width=110, 
            height=42,
            command=self._browse_local_file
        )
        browse_btn.pack(side="right")

        # CARD 2: SLIDES & DIAPOSITIVES DU PROFESSEUR (OPTIONNEL)
        card_slides = ctk.CTkFrame(frame, fg_color="#131D31", corner_radius=12, border_width=1, border_color="#1E293B")
        card_slides.pack(fill="x", pady=(0, 16), ipady=8)

        slides_title_frame = ctk.CTkFrame(card_slides, fg_color="transparent")
        slides_title_frame.pack(fill="x", padx=18, pady=(8, 4))

        ctk.CTkLabel(
            slides_title_frame,
            text="2. Diapositives / Slides du Professeur (Optionnel)",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#38BDF8"
        ).pack(side="left")

        ctk.CTkLabel(
            slides_title_frame,
            text="  ✨ Fusion Audio + Diapos  ",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#1E3A8A",
            text_color="#93C5FD",
            corner_radius=4
        ).pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            card_slides,
            text="Joignez le fichier PDF des slides présentées en amphi. L'IA fusionnera les explications orales avec le code et les schémas exacts des diapositives.",
            font=ctk.CTkFont(size=11),
            text_color="#94A3B8"
        ).pack(anchor="w", padx=18, pady=(0, 8))

        slides_row = ctk.CTkFrame(card_slides, fg_color="transparent")
        slides_row.pack(fill="x", padx=18, pady=4)

        self.slides_path_label = ctk.CTkLabel(
            slides_row,
            text="Aucune diapositive attachée (Optionnel)",
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color="#64748B",
            anchor="w"
        )
        self.slides_path_label.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.slides_clear_btn = ctk.CTkButton(
            slides_row,
            text="✖️",
            width=36,
            height=38,
            fg_color="#7F1D1D",
            hover_color="#991B1B",
            command=self._clear_slides_file
        )

        ctk.CTkButton(
            slides_row,
            text="📎 Parcourir Slides (PDF)",
            font=ctk.CTkFont(size=11, weight="bold"),
            width=180,
            height=38,
            fg_color="#1E293B",
            hover_color="#334155",
            command=self._browse_slides_file
        ).pack(side="right", padx=(4, 0))

        # CARD 3: OPTIONS
        card_options = ctk.CTkFrame(frame, fg_color="#131D31", corner_radius=12, border_width=1, border_color="#1E293B")
        card_options.pack(fill="x", pady=(0, 18), ipady=8)

        options_title = ctk.CTkLabel(
            card_options, 
            text="3. Options pédagogiques & Matière", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#38BDF8"
        )
        options_title.pack(anchor="w", padx=18, pady=(8, 10))

        opts_row = ctk.CTkFrame(card_options, fg_color="transparent")
        opts_row.pack(fill="x", padx=18, pady=4)

        lbl_lang = ctk.CTkLabel(opts_row, text="Langue :", font=ctk.CTkFont(size=12))
        lbl_lang.pack(side="left", padx=(0, 8))

        self.lang_var = ctk.StringVar(value=self.config.get("output_language", "Français"))
        self.lang_dropdown = ctk.CTkOptionMenu(
            opts_row,
            values=["Français", "Darija / Arabe", "Mixte (Français/Darija)", "Anglais"],
            variable=self.lang_var,
            width=150
        )
        self.lang_dropdown.pack(side="left", padx=(0, 25))

        lbl_mod = ctk.CTkLabel(opts_row, text="Matière :", font=ctk.CTkFont(size=12))
        lbl_mod.pack(side="left", padx=(0, 8))

        self.module_entry = ctk.CTkEntry(
            opts_row, 
            placeholder_text="ex: Programmation client-serveur, Algorithmique...", 
            width=220,
            height=34
        )
        self.module_entry.pack(side="left", fill="x", expand=True)

        # BIG LAUNCH BUTTON
        self.launch_btn = ctk.CTkButton(
            frame,
            text="🚀 LANCER LA GÉNÉRATION (COURS PDF + QUIZ + FLASHCARDS)",
            height=52,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            corner_radius=10,
            command=self.start_processing
        )
        self.launch_btn.pack(fill="x", pady=(0, 18))

        # PROGRESS SECTION
        self.progress_frame = ctk.CTkFrame(frame, fg_color="#131D31", corner_radius=12, border_width=1, border_color="#1E293B")
        self.progress_frame.pack(fill="x", pady=(0, 18), ipady=8)

        self.progress_label = ctk.CTkLabel(
            self.progress_frame, 
            text="En attente de lancement...", 
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#CBD5E1"
        )
        self.progress_label.pack(anchor="w", padx=18, pady=(8, 6))

        self.progressbar = ctk.CTkProgressBar(self.progress_frame, height=10, corner_radius=5)
        self.progressbar.pack(fill="x", padx=18, pady=(0, 8))
        self.progressbar.set(0)

        # RESULT CARD
        self.result_frame = ctk.CTkFrame(frame, fg_color="#064E3B", corner_radius=12, border_width=1, border_color="#059669")
        
        self.result_label = ctk.CTkLabel(
            self.result_frame,
            text="✨ Cours PDF généré avec succès ! Le Quiz, les Flashcards et le Chat sont prêts !",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#A7F3D0"
        )
        self.result_label.pack(padx=18, pady=(12, 10))

        btn_row = ctk.CTkFrame(self.result_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=18, pady=(0, 12))

        self.open_pdf_btn = ctk.CTkButton(
            btn_row,
            text="📄 Ouvrir le PDF du Cours",
            height=38,
            fg_color="#10B981",
            hover_color="#059669",
            font=ctk.CTkFont(weight="bold"),
            command=self._open_generated_pdf
        )
        self.open_pdf_btn.pack(side="left", expand=True, fill="x", padx=(0, 8))

        self.eco_pdf_btn = ctk.CTkButton(
            btn_row,
            text="🖨️ PDF Éco (Photocopie)",
            height=38,
            fg_color="#475569",
            hover_color="#64748B",
            font=ctk.CTkFont(weight="bold"),
            command=lambda: self._generate_eco_pdf_action(None)
        )
        self.eco_pdf_btn.pack(side="left", expand=True, fill="x", padx=(0, 8))

        self.go_quiz_btn = ctk.CTkButton(
            btn_row,
            text="🎯 Faire le Quiz QCM",
            height=38,
            fg_color="#0284C7",
            hover_color="#0369A1",
            font=ctk.CTkFont(weight="bold"),
            command=lambda: self.select_tab("quiz")
        )
        self.go_quiz_btn.pack(side="left", expand=True, fill="x", padx=(0, 8))

        self.ask_prof_btn = ctk.CTkButton(
            btn_row,
            text="💬 Discuter avec le Prof",
            height=38,
            fg_color="#6366F1",
            hover_color="#4F46E5",
            font=ctk.CTkFont(weight="bold"),
            command=lambda: self.select_tab("chat")
        )
        self.ask_prof_btn.pack(side="left", expand=True, fill="x")

        return frame

    def _on_source_mode_change(self):
        if self.source_mode_var.get() == "url":
            self.file_container.pack_forget()
            self.url_container.pack(fill="x", padx=18, pady=4)
        else:
            self.url_container.pack_forget()
            self.file_container.pack(fill="x", padx=18, pady=4)

    def _paste_clipboard(self):
        try:
            text = self.clipboard_get()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, text.strip())
        except Exception:
            pass

    def _browse_local_file(self):
        filetypes = [
            ("Fichiers Audio & Vidéo", "*.mp3 *.mp4 *.wav *.m4a *.webm *.mkv *.ogg *.aac"),
            ("Tous les fichiers", "*.*")
        ]
        chosen = filedialog.askopenfilename(title="Sélectionner l'enregistrement", filetypes=filetypes)
        if chosen:
            self.selected_local_file = chosen
            base = os.path.basename(chosen)
            size = os.path.getsize(chosen) / (1024 * 1024)
            self.file_path_label.configure(text=f"{base} ({size:.1f} Mo)", text_color="#F8FAFC")

    def _browse_slides_file(self):
        chosen = filedialog.askopenfilename(
            title="Sélectionner les diapositives / slides du professeur",
            filetypes=[("Documents PDF (Slides)", "*.pdf")]
        )
        if chosen:
            self.selected_slides_file = os.path.normpath(chosen)
            base = os.path.basename(chosen)
            size = os.path.getsize(chosen) / (1024 * 1024)
            self.slides_path_label.configure(
                text=f"📄 {base} ({size:.1f} Mo)", 
                text_color="#38BDF8", 
                font=ctk.CTkFont(size=12, weight="bold")
            )
            self.slides_clear_btn.pack(side="right", padx=(0, 6))

    def _clear_slides_file(self):
        self.selected_slides_file = None
        self.slides_path_label.configure(
            text="Aucune diapositive attachée (Optionnel)", 
            text_color="#64748B", 
            font=ctk.CTkFont(size=12, slant="italic")
        )
        self.slides_clear_btn.pack_forget()

    # -------------------------------------------------------------
    # TAB: DASHBOARD & ANALYTICS (SUIVI DU NIVEAU & RECOMMANDATIONS)
    # -------------------------------------------------------------
    def _build_dashboard_tab(self):
        frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")

        # Top Header
        header_row = ctk.CTkFrame(frame, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 15))

        title_lbl = ctk.CTkLabel(
            header_row,
            text="📊 Tableau de Bord & Suivi de Progression",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#F8FAFC"
        )
        title_lbl.pack(side="left", anchor="w")

        btn_box = ctk.CTkFrame(header_row, fg_color="transparent")
        btn_box.pack(side="right")

        refresh_btn = ctk.CTkButton(
            btn_box,
            text="🔄 Actualiser",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            width=110,
            fg_color="#334155",
            hover_color="#475569",
            command=self._refresh_dashboard_view
        )
        refresh_btn.pack(side="left", padx=(0, 8))

        reset_btn = ctk.CTkButton(
            btn_box,
            text="🗑️ Vider l'Historique",
            font=ctk.CTkFont(size=12),
            height=34,
            width=135,
            fg_color="#7F1D1D",
            hover_color="#991B1B",
            command=self._reset_dashboard_stats
        )
        reset_btn.pack(side="left")

        sub_lbl = ctk.CTkLabel(
            frame,
            text="Analysez votre taux de réussite par module, mesurez vos progrès et suivez les conseils personnalisés du Coach IA.",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8"
        )
        sub_lbl.pack(anchor="w", pady=(0, 18))

        # KPI Metrics Row (4 Cards)
        self.kpi_cards_container = ctk.CTkFrame(frame, fg_color="transparent")
        self.kpi_cards_container.pack(fill="x", pady=(0, 18))

        # AI Recommendations Box
        self.ai_coach_frame = ctk.CTkFrame(frame, fg_color="#0F2942", corner_radius=12, border_width=1, border_color="#0284C7")
        self.ai_coach_frame.pack(fill="x", pady=(0, 18), ipady=8)

        ai_header = ctk.CTkLabel(
            self.ai_coach_frame,
            text="🤖 Recommandations Personnalisées du Coach IA DIRASA",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#38BDF8"
        )
        ai_header.pack(anchor="w", padx=16, pady=(10, 6))

        self.ai_coach_text_lbl = ctk.CTkLabel(
            self.ai_coach_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#E2E8F0",
            justify="left",
            wraplength=760
        )
        self.ai_coach_text_lbl.pack(anchor="w", padx=16, pady=(0, 10))

        # Spaced Repetition Card (Planning Intelligent de Révision)
        self.spaced_card = ctk.CTkFrame(frame, fg_color="#131D31", corner_radius=12, border_width=1, border_color="#1E293B")
        self.spaced_card.pack(fill="x", pady=(0, 18), ipady=6)

        spaced_head = ctk.CTkFrame(self.spaced_card, fg_color="transparent")
        spaced_head.pack(fill="x", padx=16, pady=(12, 6))

        ctk.CTkLabel(
            spaced_head,
            text="📅 Planning Intelligent de Révision (Répétition Espacée - Système Leitner)",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#F8FAFC"
        ).pack(side="left")

        ctk.CTkLabel(
            spaced_head,
            text="  ⚡ Cycles J+1, J+3, J+7, J+14  ",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#1E3A8A",
            text_color="#93C5FD",
            corner_radius=4
        ).pack(side="left", padx=(10, 0))

        ctk.CTkLabel(
            self.spaced_card,
            text="L'algorithme de révision espacée planifie vos sessions aux moments optimaux pour contrer la courbe d'oubli.",
            font=ctk.CTkFont(size=11),
            text_color="#94A3B8"
        ).pack(anchor="w", padx=16, pady=(0, 10))

        self.spaced_list_container = ctk.CTkFrame(self.spaced_card, fg_color="transparent")
        self.spaced_list_container.pack(fill="x", padx=16, pady=(0, 12))

        # Modules Breakdown Card
        self.modules_card = ctk.CTkFrame(frame, fg_color="#131D31", corner_radius=12, border_width=1, border_color="#1E293B")
        self.modules_card.pack(fill="x", pady=(0, 18), ipady=6)

        mod_card_head = ctk.CTkLabel(
            self.modules_card,
            text="🎯 Taux de Réussite & Maîtrise par Module",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#F8FAFC"
        )
        mod_card_head.pack(anchor="w", padx=16, pady=(12, 10))

        self.modules_list_container = ctk.CTkFrame(self.modules_card, fg_color="transparent")
        self.modules_list_container.pack(fill="x", padx=16, pady=(0, 12))

        # Recent Quiz History Card
        self.history_card = ctk.CTkFrame(frame, fg_color="#131D31", corner_radius=12, border_width=1, border_color="#1E293B")
        self.history_card.pack(fill="x", pady=(0, 10), ipady=6)

        hist_card_head = ctk.CTkLabel(
            self.history_card,
            text="🕒 Historique Récent des Quiz & Examens",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#F8FAFC"
        )
        hist_card_head.pack(anchor="w", padx=16, pady=(12, 10))

        self.history_list_container = ctk.CTkFrame(self.history_card, fg_color="transparent")
        self.history_list_container.pack(fill="x", padx=16, pady=(0, 12))

        self._refresh_dashboard_view()
        return frame

    def _refresh_dashboard_view(self):
        out_dir = self.config.get("output_dir", os.path.join(os.path.dirname(__file__), "exports"))
        courses = load_courses_library(out_dir)
        metrics = calculate_dashboard_metrics(out_dir, courses)

        # 1. Render 4 KPI Cards
        for w in self.kpi_cards_container.winfo_children():
            w.destroy()

        kpis = [
            ("📚 Cours Archivés", f"{metrics['courses_this_week']} cette semaine", f"Total : {metrics['total_courses']} cours", "#38BDF8"),
            ("🎯 Réussite QCM", f"{metrics['global_quiz_rate']}%", f"{metrics['total_quizzes']} quiz complétés", "#10B981" if metrics['global_quiz_rate'] >= 70 else ("#F59E0B" if metrics['global_quiz_rate'] > 0 else "#94A3B8")),
            ("📝 Moyenne Examens", f"{metrics['avg_exam_grade']}/20", f"{metrics['total_exams']} épreuves passées", "#818CF8"),
            ("🧠 Flashcards Actives", f"{metrics['total_flashcards']}", f"{metrics['total_quiz_q']} QCM prêts", "#F472B6")
        ]

        self.kpi_cards_container.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="kpi")
        for i, (label, val, sub, color) in enumerate(kpis):
            box = ctk.CTkFrame(self.kpi_cards_container, fg_color="#131D31", corner_radius=10, border_width=1, border_color="#1E293B")
            box.grid(row=0, column=i, padx=5, sticky="nsew", ipady=6)
            
            ctk.CTkLabel(box, text=label, font=ctk.CTkFont(size=11), text_color="#94A3B8").pack(anchor="w", padx=12, pady=(8, 2))
            ctk.CTkLabel(box, text=val, font=ctk.CTkFont(size=20, weight="bold"), text_color=color).pack(anchor="w", padx=12)
            ctk.CTkLabel(box, text=sub, font=ctk.CTkFont(size=10), text_color="#64748B").pack(anchor="w", padx=12, pady=(2, 6))

        # 2. Render AI Coach Advice
        advice_lines = metrics.get("ai_advice", [])
        self.ai_coach_text_lbl.configure(text="\n\n".join(advice_lines))

        # 2.5 Render Spaced Repetition Study Planner
        for w in self.spaced_list_container.winfo_children():
            w.destroy()

        stats_data = load_stats(out_dir)
        schedule = calculate_spaced_repetition_schedule(courses, stats_data)
        
        if not schedule:
            empty_msg = ctk.CTkFrame(self.spaced_list_container, fg_color="#090D16", corner_radius=8)
            empty_msg.pack(fill="x", pady=4, ipady=10)
            ctk.CTkLabel(
                empty_msg,
                text="ℹ️ Aucun cours archivé pour le moment. Vos séances générées apparaîtront ici avec un planning intelligent de révision (J+1, J+3, J+7, J+14).",
                font=ctk.CTkFont(size=12),
                text_color="#64748B"
            ).pack()
        else:
            for item in schedule[:6]:
                s_row = ctk.CTkFrame(self.spaced_list_container, fg_color="#090D16", corner_radius=8, border_width=1, border_color="#1E293B")
                s_row.pack(fill="x", pady=4, ipady=4)

                s_inner = ctk.CTkFrame(s_row, fg_color="transparent")
                s_inner.pack(fill="x", padx=12, pady=6)

                left_s = ctk.CTkFrame(s_inner, fg_color="transparent")
                left_s.pack(side="left", fill="both", expand=True)

                badge_c = "#EF4444" if item["status_level"] == "urgent" else ("#F59E0B" if item["status_level"] == "due_today" else ("#3B82F6" if item["status_level"] == "upcoming" else "#10B981"))
                badge_lbl = ctk.CTkLabel(
                    left_s,
                    text=f"  {item['badge_text']}  ",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    fg_color=badge_c,
                    text_color="#FFFFFF",
                    corner_radius=4
                )
                badge_lbl.pack(side="left", padx=(0, 10))

                mod_tag = f"[{item['module']}] " if item.get("module") else ""
                t_lbl = ctk.CTkLabel(
                    left_s,
                    text=f"{mod_tag}{item['title']}",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color="#F8FAFC",
                    anchor="w"
                )
                t_lbl.pack(side="left")

                rec_lbl = ctk.CTkLabel(
                    left_s,
                    text=f"  •  {item['recommendation']}",
                    font=ctk.CTkFont(size=11),
                    text_color="#94A3B8",
                    anchor="w"
                )
                rec_lbl.pack(side="left", padx=(8, 0))

                act = item["recommended_action"]
                act_text = "🎯 Réviser Flashcards (3 min)" if act == "flashcards" else ("📝 Repasser Quiz" if act == "quiz" else "📝 Examen Blanc")
                act_color = "#10B981" if act == "flashcards" else ("#2563EB" if act == "quiz" else "#7C3AED")

                ctk.CTkButton(
                    s_inner,
                    text=act_text,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    height=30,
                    fg_color=act_color,
                    command=lambda c=item["course"], t=act: self._load_course_into_app(c, notify=False, target_tab=t)
                ).pack(side="right")

        # 3. Render Modules Breakdown
        for w in self.modules_list_container.winfo_children():
            w.destroy()

        modules = metrics.get("modules", [])
        if not modules:
            ctk.CTkLabel(
                self.modules_list_container,
                text="Aucun module enregistré pour l'instant. Générez votre premier cours pour voir vos statistiques !",
                font=ctk.CTkFont(size=12),
                text_color="#94A3B8"
            ).pack(anchor="w", pady=6)
        else:
            for mod in modules:
                row = ctk.CTkFrame(self.modules_list_container, fg_color="#090D16", corner_radius=8)
                row.pack(fill="x", pady=4, ipady=4)

                inner_row = ctk.CTkFrame(row, fg_color="transparent")
                inner_row.pack(fill="x", padx=12, pady=6)

                # Left: Module name & courses count
                name_frame = ctk.CTkFrame(inner_row, fg_color="transparent", width=220)
                name_frame.pack(side="left", fill="y")
                ctk.CTkLabel(
                    name_frame,
                    text=f"📘 {mod['name']}",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color="#F8FAFC",
                    anchor="w"
                ).pack(anchor="w")
                ctk.CTkLabel(
                    name_frame,
                    text=f"{mod['courses_count']} cours archivé(s)",
                    font=ctk.CTkFont(size=10),
                    text_color="#64748B",
                    anchor="w"
                ).pack(anchor="w")

                # Center: Progress bar & percentage
                center_frame = ctk.CTkFrame(inner_row, fg_color="transparent")
                center_frame.pack(side="left", fill="both", expand=True, padx=20)

                rate = mod["success_rate"]
                bar_color = "#10B981" if rate >= 75 else ("#F59E0B" if rate >= 50 else "#EF4444")
                if mod["total"] == 0:
                    bar_color = "#334155"

                bar_val = (rate / 100.0) if mod["total"] > 0 else 0.0
                pbar = ctk.CTkProgressBar(center_frame, height=10, progress_color=bar_color, fg_color="#1E293B")
                pbar.pack(fill="x", pady=(4, 2))
                pbar.set(bar_val)

                txt_details = f"Taux : {rate}% ({mod['correct']}/{mod['total']} bonnes réponses)" if mod['total'] > 0 else "Aucun quiz complété sur ce module"
                ctk.CTkLabel(center_frame, text=txt_details, font=ctk.CTkFont(size=10), text_color="#94A3B8").pack(anchor="w")

                # Right: Status Badge & Quick practice button
                right_frame = ctk.CTkFrame(inner_row, fg_color="transparent")
                right_frame.pack(side="right")

                badge_color = "#064E3B" if mod["status"] == "Maîtrisé" else ("#78350F" if mod["status"] == "À consolider" else ("#7F1D1D" if mod["status"] == "À réviser en priorité" else "#1E293B"))
                text_col = "#6EE7B7" if mod["status"] == "Maîtrisé" else ("#FDE68A" if mod["status"] == "À consolider" else ("#FCA5A5" if mod["status"] == "À réviser en priorité" else "#94A3B8"))

                ctk.CTkLabel(
                    right_frame,
                    text=f" {mod['status']} ",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    fg_color=badge_color,
                    text_color=text_col,
                    corner_radius=4
                ).pack(side="left", padx=(0, 10))

                practice_btn = ctk.CTkButton(
                    right_frame,
                    text="🎯 S'entraîner",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    height=28,
                    width=95,
                    fg_color="#2563EB",
                    hover_color="#1D4ED8",
                    command=lambda m=mod['name']: self._start_module_training(m)
                )
                practice_btn.pack(side="left")

        # 4. Render Recent History
        for w in self.history_list_container.winfo_children():
            w.destroy()

        recent = metrics.get("recent_quizzes", [])
        if not recent:
            ctk.CTkLabel(
                self.history_list_container,
                text="Aucune session de quiz récente. Passez un quiz pour commencer à enregistrer vos résultats !",
                font=ctk.CTkFont(size=12),
                text_color="#94A3B8"
            ).pack(anchor="w", pady=4)
        else:
            for item in recent:
                h_row = ctk.CTkFrame(self.history_list_container, fg_color="transparent")
                h_row.pack(fill="x", pady=2)
                
                pct = item.get("percentage", 0)
                score_color = "#10B981" if pct >= 70 else ("#F59E0B" if pct >= 50 else "#EF4444")

                ctk.CTkLabel(h_row, text=f"• {item.get('date', '')} :", font=ctk.CTkFont(size=11), text_color="#64748B").pack(side="left", padx=(0, 8))
                ctk.CTkLabel(h_row, text=f"{item.get('course_title', '')} ({item.get('module', '')})", font=ctk.CTkFont(size=11, weight="bold"), text_color="#E2E8F0").pack(side="left")
                ctk.CTkLabel(h_row, text=f"Score : {item.get('score')}/{item.get('total')} ({pct}%)", font=ctk.CTkFont(size=11, weight="bold"), text_color=score_color).pack(side="right")

    def _start_module_training(self, module_name: str):
        out_dir = self.config.get("output_dir", os.path.join(os.path.dirname(__file__), "exports"))
        courses = load_courses_library(out_dir)
        matching = [c for c in courses if c.get("module", "").lower() == module_name.lower()]
        target = matching[0] if matching else (courses[0] if courses else None)
        
        if target:
            self._load_course_into_app(target)
        else:
            self.select_tab("quiz")

    def _reset_dashboard_stats(self):
        confirm = messagebox.askyesno(
            "Réinitialiser les Statistiques",
            "Voulez-vous réinitialiser l'historique de vos quiz et examens blancs ?"
        )
        if confirm:
            out_dir = self.config.get("output_dir", os.path.join(os.path.dirname(__file__), "exports"))
            from stats_service import save_stats
            save_stats({"quiz_history": [], "exam_history": []}, out_dir)
            self._refresh_dashboard_view()
            messagebox.showinfo("Réinitialisé", "Vos statistiques ont été remises à zéro avec succès !")

    # -------------------------------------------------------------
    # TAB: COURSES LIBRARY (HISTORIQUE & ORGANISATION)
    # -------------------------------------------------------------
    def _build_library_tab(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")

        # Header
        header_frame = ctk.CTkFrame(frame, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="📚 Bibliothèque & Historique des Cours",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#F8FAFC"
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            header_frame,
            text="Retrouvez tous vos cours archivés, classés par matière. Chargez un cours pour réviser son Quiz et ses Flashcards ou ouvrez son PDF.",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8"
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Filter & Search Bar
        filter_bar = ctk.CTkFrame(frame, fg_color="#131D31", corner_radius=12, border_width=1, border_color="#1E293B")
        filter_bar.pack(fill="x", pady=(0, 15), ipady=5)

        bar_inner = ctk.CTkFrame(filter_bar, fg_color="transparent")
        bar_inner.pack(fill="x", padx=15, pady=8)

        # Search Entry
        self.lib_search_var = tk.StringVar()
        self.lib_search_entry = ctk.CTkEntry(
            bar_inner,
            placeholder_text="🔍 Rechercher par titre, matière, concept d'examen...",
            textvariable=self.lib_search_var,
            font=ctk.CTkFont(size=13),
            height=40,
            width=360,
            fg_color="#090D16",
            border_color="#334155"
        )
        self.lib_search_entry.pack(side="left", padx=(0, 12))
        self.lib_search_entry.bind("<KeyRelease>", lambda e: self._filter_library_cards())

        # Module dropdown filter
        self.lib_module_var = ctk.StringVar(value="Tous les modules")
        self.lib_module_menu = ctk.CTkOptionMenu(
            bar_inner,
            values=["Tous les modules"],
            variable=self.lib_module_var,
            height=40,
            width=190,
            fg_color="#1E293B",
            button_color="#2563EB",
            button_hover_color="#1D4ED8",
            command=lambda _: self._filter_library_cards()
        )
        self.lib_module_menu.pack(side="left", padx=(0, 12))

        # Refresh button
        self.lib_refresh_btn = ctk.CTkButton(
            bar_inner,
            text="🔄 Actualiser",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=40,
            width=110,
            fg_color="#334155",
            hover_color="#475569",
            command=self._reload_library_data
        )
        self.lib_refresh_btn.pack(side="left")

        # Stats Counter badge
        self.lib_stats_lbl = ctk.CTkLabel(
            bar_inner,
            text="0 cours",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38BDF8"
        )
        self.lib_stats_lbl.pack(side="right", padx=(10, 0))

        # Scrollable Cards Area
        self.lib_scroll_frame = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        self.lib_scroll_frame.pack(fill="both", expand=True)

        # Initial data load
        self._reload_library_data()

        return frame

    def _reload_library_data(self):
        out_dir = self.config.get("output_dir", os.path.join(os.path.dirname(__file__), "exports"))
        self.library_courses = load_courses_library(out_dir)
        
        # Update modules dropdown
        unique_mods = get_unique_modules(self.library_courses)
        self.lib_module_menu.configure(values=unique_mods)
        if self.lib_module_var.get() not in unique_mods:
            self.lib_module_var.set("Tous les modules")

        self._filter_library_cards()

    def _filter_library_cards(self):
        query = self.lib_search_var.get()
        mod = self.lib_module_var.get()
        filtered = filter_courses(self.library_courses, query=query, module_filter=mod)
        self.lib_stats_lbl.configure(text=f"{len(filtered)} / {len(self.library_courses)} cours")
        self._render_library_cards(filtered)

    def _render_library_cards(self, courses: list):
        for w in self.lib_scroll_frame.winfo_children():
            w.destroy()

        if not courses:
            empty_card = ctk.CTkFrame(self.lib_scroll_frame, fg_color="#131D31", corner_radius=12)
            empty_card.pack(fill="x", pady=20, ipady=30)
            ctk.CTkLabel(
                empty_card,
                text="🔍 Aucun cours ne correspond à votre recherche.",
                font=ctk.CTkFont(size=15, weight="bold"),
                text_color="#94A3B8"
            ).pack(pady=(10, 5))
            ctk.CTkLabel(
                empty_card,
                text="Essayez un autre mot-clé ou générez un nouveau cours dans l'onglet 'Nouveau Cours'.",
                font=ctk.CTkFont(size=12),
                text_color="#64748B"
            ).pack()
            return

        # Group all courses by their academic module (f cote wehda)
        grouped = group_courses_by_module(courses)
        for mod_name, sessions in grouped.items():
            self._render_module_folder_card(mod_name, sessions)

    def _render_module_folder_card(self, mod_name: str, sessions: list):
        # Outer Module Folder Card
        mod_card = ctk.CTkFrame(
            self.lib_scroll_frame,
            fg_color="#131D31",
            corner_radius=12,
            border_width=1,
            border_color="#1E3A8A"
        )
        mod_card.pack(fill="x", pady=10, ipady=4)

        # Header of Module
        header = ctk.CTkFrame(mod_card, fg_color="#172554", corner_radius=10)
        header.pack(fill="x", padx=10, pady=(10, 6))

        h_inner = ctk.CTkFrame(header, fg_color="transparent")
        h_inner.pack(fill="x", padx=14, pady=10)

        # Left side: Module Name + Count Badge
        left_h = ctk.CTkFrame(h_inner, fg_color="transparent")
        left_h.pack(side="left")

        ctk.CTkLabel(
            left_h,
            text=f"📁 MODULE : {mod_name}",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#60A5FA"
        ).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            left_h,
            text=f"  📊 {len(sessions)} séance(s) enregistrée(s)  ",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#1E40AF",
            text_color="#BFDBFE",
            corner_radius=6
        ).pack(side="left")

        # Right side: Module Actions
        right_h = ctk.CTkFrame(h_inner, fg_color="transparent")
        right_h.pack(side="right")

        # Quick revise module button & Cheat Sheet
        if sessions:
            latest_sess = sessions[-1]
            ctk.CTkButton(
                right_h,
                text="🎯 Réviser ce Module",
                font=ctk.CTkFont(size=12, weight="bold"),
                height=32,
                fg_color="#2563EB",
                hover_color="#1D4ED8",
                command=lambda s=latest_sess: self._load_course_into_app(s, notify=False, target_tab="quiz")
            ).pack(side="left", padx=(0, 8))

            ctk.CTkButton(
                right_h,
                text="⚡ Synthèse Express (Contrôle)",
                font=ctk.CTkFont(size=12, weight="bold"),
                height=32,
                fg_color="#D97706",
                hover_color="#B45309",
                command=lambda m=mod_name, sess=sessions: self._generate_cheat_sheet_action(m, sess)
            ).pack(side="left", padx=(0, 8))

        first_pdf = sessions[0].get("pdf_path") if sessions else ""
        ctk.CTkButton(
            right_h,
            text="📂 Dossier",
            font=ctk.CTkFont(size=12),
            height=32,
            width=80,
            fg_color="#334155",
            hover_color="#475569",
            command=lambda p=first_pdf: open_directory(os.path.dirname(p) if p else "exports")
        ).pack(side="left")

        # Sessions Container
        sess_container = ctk.CTkFrame(mod_card, fg_color="transparent")
        sess_container.pack(fill="x", padx=10, pady=(4, 10))

        for idx, s in enumerate(sessions, 1):
            self._render_session_subcard(sess_container, s, idx)

    def _render_session_subcard(self, parent_frame, course: dict, session_idx: int):
        sub = ctk.CTkFrame(
            parent_frame,
            fg_color="#0B132B",
            corner_radius=8,
            border_width=1,
            border_color="#1E293B"
        )
        sub.pack(fill="x", pady=5, ipady=3)

        inner = ctk.CTkFrame(sub, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        # Top row: Session Badge + Date + Size + Counts
        top_row = ctk.CTkFrame(inner, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            top_row,
            text=f"  Séance {session_idx}  ",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2563EB",
            text_color="#FFFFFF",
            corner_radius=6
        ).pack(side="left", padx=(0, 10))

        date_str = course.get("date", "")
        if date_str:
            ctk.CTkLabel(
                top_row,
                text=f"🕒 {date_str}",
                font=ctk.CTkFont(size=11),
                text_color="#64748B"
            ).pack(side="left", padx=(0, 10))

        size_mb = course.get("pdf_size_mb", 0)
        ctk.CTkLabel(
            top_row,
            text=f"💾 {size_mb} Mo",
            font=ctk.CTkFont(size=11),
            text_color="#64748B"
        ).pack(side="left", padx=(0, 10))

        nb_chap = course.get("chapters_count", 0)
        nb_fc = course.get("flashcards_count", 0)
        nb_quiz = course.get("quiz_count", 0)

        if nb_chap > 0:
            ctk.CTkLabel(
                top_row,
                text=f"📑 {nb_chap} Chapitres",
                font=ctk.CTkFont(size=11),
                text_color="#CBD5E1",
                fg_color="#1E293B",
                corner_radius=4
            ).pack(side="left", padx=(0, 6))

        if nb_fc > 0:
            ctk.CTkLabel(
                top_row,
                text=f"🧠 {nb_fc} Flashcards",
                font=ctk.CTkFont(size=11),
                text_color="#CBD5E1",
                fg_color="#1E293B",
                corner_radius=4
            ).pack(side="left", padx=(0, 6))

        if nb_quiz > 0:
            ctk.CTkLabel(
                top_row,
                text=f"🎯 {nb_quiz} QCM",
                font=ctk.CTkFont(size=11),
                text_color="#CBD5E1",
                fg_color="#1E293B",
                corner_radius=4
            ).pack(side="left", padx=(0, 6))

        # Title
        ctk.CTkLabel(
            inner,
            text=course.get("title", f"Séance {session_idx}"),
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#F8FAFC",
            anchor="w",
            justify="left",
            wraplength=760
        ).pack(fill="x", pady=(2, 4))

        # Summary snippet
        summary_text = course.get("summary", "")
        if summary_text:
            clean_sum = summary_text.replace("\n", " ")
            if len(clean_sum) > 170:
                clean_sum = clean_sum[:170] + "..."
            ctk.CTkLabel(
                inner,
                text=clean_sum,
                font=ctk.CTkFont(size=11),
                text_color="#94A3B8",
                anchor="w",
                justify="left",
                wraplength=760
            ).pack(fill="x", pady=(0, 8))

        # Buttons row
        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x")

        # 1. Quiz & Flashcards
        ctk.CTkButton(
            btn_row,
            text="🎯 Quiz & Flashcards",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=30,
            fg_color="#10B981",
            hover_color="#059669",
            command=lambda s=course: self._load_course_into_app(s, notify=False, target_tab="quiz")
        ).pack(side="left", padx=(0, 8))

        # 2. Sawel l'Prof
        ctk.CTkButton(
            btn_row,
            text="💬 Sawel l'Prof",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=30,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=lambda s=course: self._load_course_into_app(s, notify=False, target_tab="chat")
        ).pack(side="left", padx=(0, 8))

        # 3. Examen Blanc
        ctk.CTkButton(
            btn_row,
            text="📝 Examen Blanc",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=30,
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            command=lambda s=course: self._load_course_into_app(s, notify=False, target_tab="exam")
        ).pack(side="left", padx=(0, 8))

        # 4. Ouvrir PDF
        pdf_path = course.get("pdf_path", "")
        if pdf_path and os.path.exists(pdf_path):
            ctk.CTkButton(
                btn_row,
                text="📄 PDF",
                font=ctk.CTkFont(size=11, weight="bold"),
                height=30,
                width=65,
                fg_color="#334155",
                hover_color="#475569",
                command=lambda p=pdf_path: open_file(p)
            ).pack(side="left", padx=(0, 8))

        # 4b. PDF Éco-Photocopie (Noir & Blanc)
        ctk.CTkButton(
            btn_row,
            text="🖨️ PDF Éco (N&B)",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=30,
            width=120,
            fg_color="#475569",
            hover_color="#64748B",
            command=lambda s=course: self._generate_eco_pdf_action(s)
        ).pack(side="left", padx=(0, 8))

        # 5. Supprimer
        ctk.CTkButton(
            btn_row,
            text="🗑️",
            font=ctk.CTkFont(size=11),
            height=30,
            width=36,
            fg_color="#7F1D1D",
            hover_color="#991B1B",
            command=lambda s=course: self._delete_course_from_lib(s)
        ).pack(side="right")

    def _load_course_into_app(self, course: dict, notify: bool = False, target_tab: str = None):
        json_p = course.get("json_path")
        course_data = None
        if json_p and os.path.exists(json_p):
            try:
                with open(json_p, "r", encoding="utf-8") as f:
                    course_data = json.load(f)
            except Exception as e:
                print(f"Error loading course json: {e}")

        if not course_data:
            course_data = {
                "title": course.get("title", "Cours"),
                "module": course.get("module", "Général"),
                "summary": course.get("summary", "Support extrait et disponible en PDF."),
                "table_of_contents": ["Introduction générale", "Concepts clés", "Conclusion & Révision"],
                "key_takeaways": ["Consultez le document PDF pour les définitions et explications complètes."],
                "raw_transcript": f"Transcription du cours : {course.get('title')}.\n\nPour lire le cours intégral, ouvrez le fichier PDF dans l'onglet Bibliothèque.",
                "flashcards": [
                    {"front": f"Quel est le sujet du cours '{course.get('title')}' ?", "back": f"Module : {course.get('module', 'Général')}"}
                ],
                "quiz": [
                    {
                        "question": f"Quel est le thème principal du cours '{course.get('title')}' ?",
                        "options": [course.get("title", "Sujet principal"), "Autre sujet non lié", "Introduction générale", "Rappels"],
                        "correct_index": 0,
                        "explanation": f"Ce cours traite de '{course.get('title')}' dans le cadre du module {course.get('module')}."
                    }
                ],
                "mindmap": [
                    {"topic": course.get("module", "Général"), "subtopics": [course.get("title", "Cours")]}
                ]
            }

        self.latest_course_data = course_data
        self.latest_pdf_path = course.get("pdf_path")

        # Refresh all tabs
        self._refresh_preview_text()
        raw_t = course_data.get("raw_transcript", "Aucune transcription disponible.")
        self.transcript_textbox.delete("1.0", "end")
        self.transcript_textbox.insert("1.0", raw_t)
        self.current_quiz_index = 0
        self.quiz_score = 0
        self._load_current_quiz_question()
        self.current_card_index = 0
        self.card_is_flipped = False
        self._load_flashcard()

        # Update top bar to reflect this course
        self._suppress_top_sync = True
        try:
            mod = course.get("module", "Général")
            if hasattr(self, "top_module_menu"):
                current_top_mod = self.top_module_var.get()
                if current_top_mod != mod:
                    grouped = group_courses_by_module(self.library_courses)
                    module_names = list(grouped.keys())
                    self.top_module_menu.configure(values=module_names)
                    self.top_module_var.set(mod)
                self._populate_top_sessions_for_module(mod, select_course_id=course.get("id"))
                self.top_pdf_btn.configure(state="normal")
        except Exception as e:
            print(f"Error syncing top bar: {e}")
        finally:
            self._suppress_top_sync = False

        if notify:
            messagebox.showinfo(
                "Cours Chargé avec Succès !",
                f"Le cours '{course.get('title')}' a été chargé dans DIRASA AI !\n\n"
                "Vous pouvez dès maintenant réviser son Quiz QCM, ses Flashcards Anki ou interroger le prof virtuel dans le Chatbot."
            )

        if target_tab:
            self.select_tab(target_tab)

    def _delete_course_from_lib(self, course: dict):
        title = course.get("title", "ce cours")
        confirm = messagebox.askyesno(
            "Supprimer le cours",
            f"Voulez-vous vraiment retirer '{title}' de votre bibliothèque ?"
        )
        if confirm:
            out_dir = self.config.get("output_dir", os.path.join(os.path.dirname(__file__), "exports"))
            delete_course_from_library(course.get("id"), out_dir, delete_files=False)
            self._reload_library_data()
            self._sync_top_active_bar()

    def _generate_cheat_sheet_action(self, mod_name: str, sessions: list):
        if not sessions:
            messagebox.showwarning("Aucune séance", f"Aucune séance n'est enregistrée pour le module {mod_name}.")
            return

        out_dir = self.config.get("output_dir", os.path.join(os.path.dirname(__file__), "exports"))
        
        messagebox.showinfo(
            "Synthèse Express en cours",
            f"Création de la Fiche de Synthèse Express pour le module '{mod_name}' ({len(sessions)} séances) !\n\n"
            "Le document PDF condensé va s'ouvrir automatiquement dans quelques instants."
        )

        def _worker():
            try:
                pdf_p = generate_module_cheat_sheet(mod_name, sessions, out_dir, self.config)
                self.after(0, lambda: self._on_cheat_sheet_success(mod_name, pdf_p))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: messagebox.showerror("Erreur Synthèse", f"Impossible de générer la synthèse : {err}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_cheat_sheet_success(self, mod_name: str, pdf_p: str):
        if pdf_p and os.path.exists(pdf_p):
            open_file(pdf_p)

    def _load_course_data_from_entry(self, course: dict):
        json_p = course.get("json_path")
        if json_p and os.path.exists(json_p):
            try:
                with open(json_p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading course json: {e}")
        return None

    def _generate_eco_pdf_action(self, course: dict = None):
        """Generates an ink-saving black & white PDF for university photocopy printing."""
        course_data = self._load_course_data_from_entry(course) if course else self.latest_course_data
        if not course_data:
            messagebox.showwarning(
                "Données manquantes",
                "Les données complètes de ce cours sont introuvables (fichier JSON manquant).\n"
                "Le PDF Éco ne peut être généré que pour les cours créés avec DIRASA AI."
            )
            return

        out_dir = self.config.get("output_dir", os.path.join(os.path.dirname(__file__), "exports"))

        def _worker():
            try:
                pdf_p = generate_eco_course_pdf(course_data, out_dir)
                self.after(0, lambda: open_file(pdf_p))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: messagebox.showerror("Erreur PDF Éco", f"Impossible de générer le PDF Éco : {err}"))

        threading.Thread(target=_worker, daemon=True).start()

    # -------------------------------------------------------------
    # TAB: LIVE AMPHI RECORDER
    # -------------------------------------------------------------
    def _build_record_tab(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")

        title_lbl = ctk.CTkLabel(
            frame, 
            text="🎙️ Enregistreur d'Amphi Direct (Microphone)", 
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#F8FAFC"
        )
        title_lbl.pack(anchor="w", pady=(0, 4))

        sub_lbl = ctk.CTkLabel(
            frame, 
            text="Posez votre PC sur la table de l'amphi. Enregistrez la séance en direct et transformez-la en cours PDF dès la fin du cours !", 
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8"
        )
        sub_lbl.pack(anchor="w", pady=(0, 20))

        # Big Central Recorder Card
        card = ctk.CTkFrame(frame, fg_color="#131D31", corner_radius=15, border_width=1, border_color="#1E293B")
        card.pack(fill="both", expand=True, padx=20, pady=10, ipady=20)

        # Pulsing Status Indicator
        self.rec_status_lbl = ctk.CTkLabel(
            card,
            text="⚪ Micro prêt à enregistrer",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#94A3B8"
        )
        self.rec_status_lbl.pack(pady=(25, 10))

        # Digital Timer Display
        self.rec_timer_lbl = ctk.CTkLabel(
            card,
            text="00:00:00",
            font=ctk.CTkFont(size=56, weight="bold", family="Consolas"),
            text_color="#FFFFFF"
        )
        self.rec_timer_lbl.pack(pady=(10, 15))

        # Meta info row (Module / Subject)
        meta_row = ctk.CTkFrame(card, fg_color="transparent")
        meta_row.pack(pady=(0, 20))

        ctk.CTkLabel(
            meta_row,
            text="Matière / Module :",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#94A3B8"
        ).pack(side="left", padx=(0, 8))

        self.rec_module_entry = ctk.CTkEntry(
            meta_row,
            placeholder_text="ex: Programmation Réseau C, Algorithmique, Droit...",
            font=ctk.CTkFont(size=12),
            height=36,
            width=280,
            fg_color="#090D16",
            border_color="#334155"
        )
        self.rec_module_entry.pack(side="left")

        # Controls Row
        ctrl_row = ctk.CTkFrame(card, fg_color="transparent")
        ctrl_row.pack(pady=(0, 20))

        self.rec_start_btn = ctk.CTkButton(
            ctrl_row,
            text="🔴 Démarrer l'Enregistrement",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=220,
            height=48,
            fg_color="#DC2626",
            hover_color="#B91C1C",
            command=self._start_recording
        )
        self.rec_start_btn.pack(side="left", padx=10)

        self.rec_stop_btn = ctk.CTkButton(
            ctrl_row,
            text="⏹️ Arrêter l'Enregistrement",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=220,
            height=48,
            fg_color="#334155",
            hover_color="#475569",
            state="disabled",
            command=self._stop_recording
        )
        self.rec_stop_btn.pack(side="left", padx=10)

        # Output notification & direct convert
        self.rec_output_frame = ctk.CTkFrame(card, fg_color="#064E3B", corner_radius=12, border_width=1, border_color="#10B981")
        
        self.rec_saved_lbl = ctk.CTkLabel(
            self.rec_output_frame,
            text="Fichier audio sauvegardé !",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#A7F3D0"
        )
        self.rec_saved_lbl.pack(padx=20, pady=(12, 6))

        self.rec_convert_btn = ctk.CTkButton(
            self.rec_output_frame,
            text="⚡ GÉNÉRER LE COURS PDF DIRECTEMENT (1-CLIC) ➔",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=46,
            fg_color="#10B981",
            hover_color="#059669",
            command=self._convert_recorded_audio
        )
        self.rec_convert_btn.pack(padx=20, pady=(6, 14))

        return frame

    def _start_recording(self):
        try:
            self.recorded_file_path = self.recorder.start()
            self.rec_status_lbl.configure(text="🔴 ENREGISTREMENT EN COURS (MICRO AMPHI ACTIF)", text_color="#EF4444")
            self.rec_start_btn.configure(state="disabled")
            self.rec_stop_btn.configure(state="normal", fg_color="#DC2626", hover_color="#B91C1C")
            self.rec_output_frame.pack_forget()
            self._update_rec_timer()
        except Exception as e:
            messagebox.showerror("Erreur Micro", f"Impossible de démarrer l'enregistrement : {e}")

    def _update_rec_timer(self):
        if self.recorder.is_recording:
            elapsed = self.recorder.get_elapsed_seconds()
            h = elapsed // 3600
            m = (elapsed % 3600) // 60
            s = elapsed % 60
            self.rec_timer_lbl.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
            self.record_timer_id = self.after(1000, self._update_rec_timer)

    def _stop_recording(self):
        if self.record_timer_id:
            self.after_cancel(self.record_timer_id)
        saved_path = self.recorder.stop()
        self.recorded_file_path = saved_path
        self.rec_status_lbl.configure(text="⚪ Enregistrement terminé avec succès", text_color="#10B981")
        self.rec_start_btn.configure(state="normal")
        self.rec_stop_btn.configure(state="disabled", fg_color="#334155")
        
        size = os.path.getsize(saved_path) / (1024 * 1024) if os.path.exists(saved_path) else 0
        self.rec_saved_lbl.configure(text=f"✅ Audio prêt : {os.path.basename(saved_path)} ({size:.1f} Mo)")
        self.rec_output_frame.pack(fill="x", padx=40, pady=(10, 0))

    def _convert_recorded_audio(self):
        if self.recorded_file_path and os.path.exists(self.recorded_file_path):
            self.selected_local_file = self.recorded_file_path
            self.source_mode_var.set("file")
            self._on_source_mode_change()
            self.file_path_label.configure(
                text=f"{os.path.basename(self.recorded_file_path)} ({os.path.getsize(self.recorded_file_path)/(1024*1024):.1f} Mo)",
                text_color="#F8FAFC"
            )
            # Transfer module if typed
            if hasattr(self, "rec_module_entry"):
                mod = self.rec_module_entry.get().strip()
                if mod:
                    self.module_entry.delete(0, "end")
                    self.module_entry.insert(0, mod)

            self.select_tab("generator")
            self.start_processing()

    # -------------------------------------------------------------
    # TAB: TIMED MOCK EXAM (NOTATION SUR 20 & IA)
    # -------------------------------------------------------------
    def _build_exam_tab(self):
        frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")

        title_lbl = ctk.CTkLabel(
            frame, 
            text="📝 Examen Blanc Chronométré (Notation sur 20 & Correction IA)", 
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#F8FAFC"
        )
        title_lbl.pack(anchor="w", pady=(0, 4))

        sub_lbl = ctk.CTkLabel(
            frame, 
            text="Évaluez votre niveau en conditions réelles d'examen avec un sujet officiel généré par IA et corrigé avec barème.", 
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8"
        )
        sub_lbl.pack(anchor="w", pady=(0, 18))

        # 1. SETUP CARD (Before start)
        self.exam_setup_card = ctk.CTkFrame(frame, fg_color="#131D31", corner_radius=12, border_width=1, border_color="#1E293B")
        self.exam_setup_card.pack(fill="x", pady=(0, 15), ipady=10)

        lbl_s = ctk.CTkLabel(
            self.exam_setup_card, 
            text="Configuration de l'Épreuve", 
            font=ctk.CTkFont(size=14, weight="bold"), 
            text_color="#38BDF8"
        )
        lbl_s.pack(anchor="w", padx=18, pady=(8, 10))

        row = ctk.CTkFrame(self.exam_setup_card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=5)

        lbl_dur = ctk.CTkLabel(row, text="Durée de l'épreuve :", font=ctk.CTkFont(size=12))
        lbl_dur.pack(side="left", padx=(0, 10))

        self.exam_dur_var = ctk.StringVar(value="30 minutes")
        self.exam_dur_menu = ctk.CTkOptionMenu(
            row,
            values=["15 minutes", "20 minutes", "30 minutes", "45 minutes", "60 minutes"],
            variable=self.exam_dur_var,
            width=140
        )
        self.exam_dur_menu.pack(side="left", padx=(0, 20))

        self.exam_launch_btn = ctk.CTkButton(
            row,
            text="🚀 Commencer l'Examen Chronométré",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=38,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self._start_mock_exam
        )
        self.exam_launch_btn.pack(side="left")

        # 2. ACTIVE EXAM VIEW (Hidden initially)
        self.exam_active_card = ctk.CTkFrame(frame, fg_color="#131D31", corner_radius=12, border_width=1, border_color="#2563EB")
        
        # Countdown banner
        self.exam_timer_banner = ctk.CTkFrame(self.exam_active_card, fg_color="#1E293B", corner_radius=8)
        self.exam_timer_banner.pack(fill="x", padx=15, pady=12)

        self.exam_timer_lbl = ctk.CTkLabel(
            self.exam_timer_banner,
            text="⏱️ Temps Restant : 30:00",
            font=ctk.CTkFont(size=18, weight="bold", family="Consolas"),
            text_color="#FBBF24"
        )
        self.exam_timer_lbl.pack(pady=8)

        # Questions container
        self.exam_questions_container = ctk.CTkFrame(self.exam_active_card, fg_color="transparent")
        self.exam_questions_container.pack(fill="both", expand=True, padx=15, pady=5)

        self.exam_submit_btn = ctk.CTkButton(
            self.exam_active_card,
            text="🏁 Rendre la Copie & Obtenir ma Note (/20)",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=44,
            fg_color="#10B981",
            hover_color="#059669",
            command=self._submit_mock_exam
        )
        self.exam_submit_btn.pack(fill="x", padx=15, pady=(15, 15))

        # 3. RESULTS & CORRECTION CARD (Hidden initially)
        self.exam_results_card = ctk.CTkFrame(frame, fg_color="#0F172A", corner_radius=12, border_width=2, border_color="#10B981")
        
        self.exam_score_banner = ctk.CTkLabel(
            self.exam_results_card,
            text="🏆 Note : 16.5 / 20  •  Mention Très Bien",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#86EFAC"
        )
        self.exam_score_banner.pack(pady=(15, 5))

        self.exam_appreciation_lbl = ctk.CTkLabel(
            self.exam_results_card,
            text="",
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color="#CBD5E1",
            wraplength=780,
            justify="center"
        )
        self.exam_appreciation_lbl.pack(padx=20, pady=(0, 15))

        self.exam_correction_box = ctk.CTkTextbox(
            self.exam_results_card,
            font=ctk.CTkFont(size=12, family="Consolas"),
            height=280,
            fg_color="#131D31",
            text_color="#E2E8F0"
        )
        self.exam_correction_box.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.exam_retry_btn = ctk.CTkButton(
            self.exam_results_card,
            text="🔄 Faire un Autre Examen Blanc",
            font=ctk.CTkFont(weight="bold"),
            height=38,
            fg_color="#334155",
            hover_color="#475569",
            command=self._reset_mock_exam
        )
        self.exam_retry_btn.pack(pady=(0, 15))

        return frame

    def _start_mock_exam(self):
        if not self.latest_course_data:
            messagebox.showwarning("Cours manquant", "Veuillez d'abord générer un cours dans l'onglet 'Nouveau Cours'.")
            return

        dur_str = self.exam_dur_var.get()
        mins = int(dur_str.split()[0])
        self.exam_seconds_remaining = mins * 60

        self.exam_launch_btn.configure(state="disabled", text="Génération du sujet d'examen...")
        
        # Background generate questions
        def fetch_exam():
            questions = generate_mock_exam(self.latest_course_data, self.config)
            self.after(0, lambda: self._on_mock_exam_ready(questions))

        threading.Thread(target=fetch_exam, daemon=True).start()

    def _on_mock_exam_ready(self, questions):
        self.exam_questions = questions
        self.exam_launch_btn.configure(state="normal", text="🚀 Commencer l'Examen Chronométré")
        self.exam_setup_card.pack_forget()
        self.exam_results_card.pack_forget()

        # Build question UI widgets
        for widget in self.exam_questions_container.winfo_children():
            widget.destroy()
        self.exam_answer_boxes = {}

        for q in self.exam_questions:
            q_box = ctk.CTkFrame(self.exam_questions_container, fg_color="#1E293B", corner_radius=8)
            q_box.pack(fill="x", pady=8, padx=5, ipady=8)

            header = f"{q.get('title', 'Exercice')} ({q.get('points', 5)} points)"
            q_title = ctk.CTkLabel(q_box, text=header, font=ctk.CTkFont(size=13, weight="bold"), text_color="#38BDF8")
            q_title.pack(anchor="w", padx=12, pady=(6, 4))

            q_text = ctk.CTkLabel(q_box, text=q.get("question", ""), font=ctk.CTkFont(size=12), text_color="#FFFFFF", wraplength=760, justify="left")
            q_text.pack(anchor="w", padx=12, pady=(0, 8))

            ans_box = ctk.CTkTextbox(q_box, height=90, font=ctk.CTkFont(size=12), fg_color="#0F172A", text_color="#E2E8F0")
            ans_box.pack(fill="x", padx=12, pady=(0, 6))
            self.exam_answer_boxes[q.get("id", 1)] = ans_box

        self.exam_active_card.pack(fill="both", expand=True, pady=(0, 15))
        self.exam_in_progress = True
        self._update_exam_countdown()

    def _update_exam_countdown(self):
        if not self.exam_in_progress:
            return

        if self.exam_seconds_remaining <= 0:
            messagebox.showinfo("Temps Écoulé !", "Le chronomètre a expiré ! Votre copie va être soumise automatiquement.")
            self._submit_mock_exam()
            return

        m = self.exam_seconds_remaining // 60
        s = self.exam_seconds_remaining % 60
        self.exam_timer_lbl.configure(text=f"⏱️ Temps Restant : {m:02d}:{s:02d}")

        if self.exam_seconds_remaining <= 180:
            self.exam_timer_lbl.configure(text_color="#EF4444")
        elif self.exam_seconds_remaining <= 600:
            self.exam_timer_lbl.configure(text_color="#FBBF24")
        else:
            self.exam_timer_lbl.configure(text_color="#38BDF8")

        self.exam_seconds_remaining -= 1
        self.exam_timer_id = self.after(1000, self._update_exam_countdown)

    def _submit_mock_exam(self):
        self.exam_in_progress = False
        if self.exam_timer_id:
            self.after_cancel(self.exam_timer_id)

        self.exam_submit_btn.configure(state="disabled", text="⏳ Correction de votre copie par l'IA...")

        # Collect student answers
        answers = {}
        for qid, tb in self.exam_answer_boxes.items():
            answers[qid] = tb.get("1.0", "end").strip()

        def do_grade():
            grading_result = grade_mock_exam(self.exam_questions, answers, self.config)
            self.after(0, lambda: self._on_mock_exam_graded(grading_result))

        threading.Thread(target=do_grade, daemon=True).start()

    def _on_mock_exam_graded(self, res):
        self.exam_active_card.pack_forget()
        self.exam_submit_btn.configure(state="normal", text="🏁 Rendre la Copie & Obtenir ma Note (/20)")

        score = res.get("total_score", 0)
        max_s = res.get("max_score", 20)
        mention = res.get("mention", "")
        appreciation = res.get("appreciation", "")

        color = "#86EFAC" if score >= 14 else ("#FDE047" if score >= 10 else "#FCA5A5")
        self.exam_score_banner.configure(
            text=f"🏆 Note Finale : {score:.1f} / {max_s}  •  Mention {mention}",
            text_color=color
        )
        self.exam_appreciation_lbl.configure(text=f"Appréciation du Professeur : {appreciation}")

        # Details
        lines = []
        for c in res.get("corrections", []):
            lines.append(f"== EXERCICE {c.get('question_id')} : {c.get('score')}/{c.get('max_score')} pts ==")
            lines.append(f"Feedback : {c.get('feedback')}")
            lines.append(f"Solution modèle attendue :\n{c.get('model_solution')}\n")
            lines.append("-" * 65 + "\n")

        self.exam_correction_box.delete("1.0", "end")
        self.exam_correction_box.insert("1.0", "\n".join(lines))

        # Record in study_stats.json for Dashboard
        try:
            out_dir = self.config.get("output_dir", os.path.join(os.path.dirname(__file__), "exports"))
            mod = self.latest_course_data.get("module", "Général") if self.latest_course_data else "Général"
            title = self.latest_course_data.get("title", "Cours") if self.latest_course_data else "Cours"
            record_exam_result(out_dir, mod, title, score, max_s)
        except Exception as e:
            print(f"Error recording exam stats: {e}")

        self.exam_results_card.pack(fill="both", expand=True, pady=(0, 15))

    def _reset_mock_exam(self):
        self.exam_results_card.pack_forget()
        self.exam_setup_card.pack(fill="x", pady=(0, 15), ipady=10)

    # -------------------------------------------------------------
    # TAB 2: INTERACTIVE QUIZ (QCM)
    # -------------------------------------------------------------
    def _build_quiz_tab(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")

        title_lbl = ctk.CTkLabel(
            frame, 
            text="🎯 Quiz Interactif (QCM d'Auto-Évaluation)", 
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#F8FAFC"
        )
        title_lbl.pack(anchor="w", pady=(0, 4))

        self.quiz_sub_lbl = ctk.CTkLabel(
            frame, 
            text="Testez immédiatement votre compréhension de la séance enregistrée.", 
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8"
        )
        self.quiz_sub_lbl.pack(anchor="w", pady=(0, 15))

        # Main Quiz Card
        self.quiz_card = ctk.CTkFrame(frame, fg_color="#131D31", corner_radius=12, border_width=1, border_color="#1E293B")
        self.quiz_card.pack(fill="both", expand=True, padx=5, pady=5, ipady=15)

        # Header Question Progress
        self.quiz_counter_lbl = ctk.CTkLabel(
            self.quiz_card, 
            text="Question 1 sur 4", 
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38BDF8"
        )
        self.quiz_counter_lbl.pack(anchor="w", padx=20, pady=(15, 8))

        # Question Text
        self.quiz_q_lbl = ctk.CTkLabel(
            self.quiz_card, 
            text="Chargement de la question...", 
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#F8FAFC",
            wraplength=780,
            justify="left"
        )
        self.quiz_q_lbl.pack(anchor="w", padx=20, pady=(0, 15))

        # Options Container
        self.quiz_options_container = ctk.CTkFrame(self.quiz_card, fg_color="transparent")
        self.quiz_options_container.pack(fill="x", padx=20, pady=5)

        self.quiz_radio_buttons = []
        for i in range(4):
            rb = ctk.CTkRadioButton(
                self.quiz_options_container,
                text=f"Option {i+1}",
                variable=self.quiz_selected_option,
                value=i,
                font=ctk.CTkFont(size=13),
                radiobutton_height=18,
                radiobutton_width=18,
                border_width_unchecked=2
            )
            rb.pack(anchor="w", pady=8)
            self.quiz_radio_buttons.append(rb)

        # Explanation Card (Hidden initially)
        self.quiz_exp_frame = ctk.CTkFrame(self.quiz_card, fg_color="#1E293B", corner_radius=8)
        self.quiz_exp_lbl = ctk.CTkLabel(
            self.quiz_exp_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#CBD5E1",
            wraplength=760,
            justify="left"
        )
        self.quiz_exp_lbl.pack(padx=15, pady=10)

        # Actions Row
        actions_row = ctk.CTkFrame(self.quiz_card, fg_color="transparent")
        actions_row.pack(fill="x", padx=20, pady=(15, 10))

        self.quiz_validate_btn = ctk.CTkButton(
            actions_row,
            text="✅ Valider la Réponse",
            font=ctk.CTkFont(weight="bold"),
            width=160,
            height=38,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self._validate_quiz_answer
        )
        self.quiz_validate_btn.pack(side="left", padx=(0, 10))

        self.quiz_next_btn = ctk.CTkButton(
            actions_row,
            text="Question Suivante ➔",
            font=ctk.CTkFont(weight="bold"),
            width=160,
            height=38,
            fg_color="#334155",
            hover_color="#475569",
            state="disabled",
            command=self._next_quiz_question
        )
        self.quiz_next_btn.pack(side="left", padx=(0, 10))

        self.quiz_restart_btn = ctk.CTkButton(
            actions_row,
            text="🔄 Recommencer",
            width=120,
            height=38,
            fg_color="#475569",
            hover_color="#64748B",
            command=self._restart_quiz
        )
        self.quiz_restart_btn.pack(side="right")

        # Load first question
        self._load_current_quiz_question()
        return frame

    def _load_current_quiz_question(self):
        if not self.latest_course_data or not self.latest_course_data.get("quiz"):
            self.quiz_counter_lbl.configure(text="Quiz en attente de cours...")
            self.quiz_q_lbl.configure(text="Aucun cours chargé pour le moment.\nCollez le lien de votre séance dans l'onglet 'Nouveau Cours' et lancez la génération pour créer votre Quiz personnalisé !")
            for rb in self.quiz_radio_buttons:
                rb.configure(text="", state="disabled")
            self.quiz_validate_btn.configure(state="disabled")
            self.quiz_next_btn.configure(state="disabled")
            return

        quiz_list = self.latest_course_data.get("quiz", [])

        q = quiz_list[self.current_quiz_index]
        self.quiz_counter_lbl.configure(text=f"Question {self.current_quiz_index + 1} sur {len(quiz_list)}  (Score : {self.quiz_score})")
        self.quiz_q_lbl.configure(text=q.get("question", ""))

        options = q.get("options", [])
        for i, opt in enumerate(options):
            if i < len(self.quiz_radio_buttons):
                self.quiz_radio_buttons[i].configure(text=opt, state="normal", text_color="#E2E8F0")

        self.quiz_selected_option.set(-1)
        self.quiz_exp_frame.pack_forget()
        self.quiz_answered = False
        self.quiz_validate_btn.configure(state="normal")
        self.quiz_next_btn.configure(state="disabled")

    def _validate_quiz_answer(self):
        sel = self.quiz_selected_option.get()
        if sel == -1:
            messagebox.showwarning("Sélection", "Veuillez choisir une option avant de valider.")
            return

        quiz_list = self.latest_course_data.get("quiz", [])
        q = quiz_list[self.current_quiz_index]
        correct = q.get("correct_index", 0)
        explanation = q.get("explanation", "")

        self.quiz_answered = True
        self.quiz_validate_btn.configure(state="disabled")
        self.quiz_next_btn.configure(state="normal")

        if sel == correct:
            self.quiz_score += 1
            self.quiz_exp_lbl.configure(
                text=f"🎉 BRAVO, BONNE RÉPONSE !\n\n{explanation}",
                text_color="#86EFAC"
            )
        else:
            correct_text = q.get("options", [""])[correct] if correct < len(q.get("options", [])) else ""
            self.quiz_exp_lbl.configure(
                text=f"❌ RÉPONSE INCORRECTE.\nBonne réponse : {correct_text}\n\n{explanation}",
                text_color="#FCA5A5"
            )

        self.quiz_exp_frame.pack(fill="x", padx=20, pady=(5, 10))

    def _next_quiz_question(self):
        quiz_list = self.latest_course_data.get("quiz", [])
        if self.current_quiz_index + 1 < len(quiz_list):
            self.current_quiz_index += 1
            self._load_current_quiz_question()
        else:
            total = len(quiz_list)
            score_msg = f"Quiz Terminé !\n\nVotre Score Final : {self.quiz_score} / {total}\n"
            if self.quiz_score == total:
                score_msg += "🏆 Excellent travail ! Maîtrise parfaite du cours."
            elif self.quiz_score >= total / 2:
                score_msg += "👍 Bon travail ! Revoyez les points clés dans le PDF."
            else:
                score_msg += "📖 Pensez à relire la fiche de révision et le cours."

            # Record in study_stats.json for Dashboard
            try:
                out_dir = self.config.get("output_dir", os.path.join(os.path.dirname(__file__), "exports"))
                mod = self.latest_course_data.get("module", "Général") if self.latest_course_data else "Général"
                title = self.latest_course_data.get("title", "Cours") if self.latest_course_data else "Cours"
                record_quiz_result(out_dir, mod, title, self.quiz_score, total)
            except Exception as e:
                print(f"Error recording quiz stats: {e}")

            messagebox.showinfo("Résultat du Quiz", score_msg)
            self._restart_quiz()

    def _restart_quiz(self):
        self.current_quiz_index = 0
        self.quiz_score = 0
        self._load_current_quiz_question()

    # -------------------------------------------------------------
    # TAB 3: CHATBOT "SAWEL L'PROF"
    # -------------------------------------------------------------
    def _build_chat_tab(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")

        # Header Row with Voice Output Toggle
        h_row = ctk.CTkFrame(frame, fg_color="transparent")
        h_row.pack(fill="x", pady=(0, 4))

        title_lbl = ctk.CTkLabel(
            h_row, 
            text="💬 Sawel l'Prof (Tuteur Vocal & Chat Interactif)", 
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#F8FAFC"
        )
        title_lbl.pack(side="left", anchor="w")

        # Listen Button (Text-to-Speech)
        self.chat_listen_btn = ctk.CTkButton(
            h_row,
            text="🔊 Écouter l'explication",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=32,
            width=175,
            fg_color="#334155",
            hover_color="#475569",
            command=self._toggle_listen_reply
        )
        self.chat_listen_btn.pack(side="right")

        sub_lbl = ctk.CTkLabel(
            frame, 
            text="Posez n'importe quelle question sur ce cours par texte ou au micro (en Français ou en Darija). L'IA répond et peut vous expliquer à voix haute !", 
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8"
        )
        sub_lbl.pack(anchor="w", pady=(0, 15))

        # Chat history container
        self.chat_history_box = ctk.CTkTextbox(
            frame, 
            font=ctk.CTkFont(size=13),
            fg_color="#131D31",
            text_color="#E2E8F0"
        )
        self.chat_history_box.pack(fill="both", expand=True, pady=(0, 12))

        # Welcome initial message
        welcome = (
            "👨‍🏫 Professeur Virtuel : Salam ! Je suis votre professeur pour cette séance. "
            "Avez-vous une question sur les concepts abordés, un bout de code à éclaircir, ou un piège d'examen ? "
            "Vous pouvez écrire ci-dessous ou utiliser le micro pour parler !"
        )
        self.chat_history_box.insert("end", welcome + "\n\n")

        # Input Row
        input_row = ctk.CTkFrame(frame, fg_color="transparent")
        input_row.pack(fill="x")

        # Mic Vocal Input Button
        self.chat_mic_btn = ctk.CTkButton(
            input_row,
            text="🎙️ Parler au micro",
            width=150,
            height=44,
            fg_color="#10B981",
            hover_color="#059669",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._toggle_vocal_question
        )
        self.chat_mic_btn.pack(side="left", padx=(0, 10))

        self.chat_entry = ctk.CTkEntry(
            input_row,
            placeholder_text="Posez votre question (ou cliquez sur le micro pour parler)...",
            height=44,
            font=ctk.CTkFont(size=13)
        )
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.chat_entry.bind("<Return>", lambda e: self._send_chat_message())

        self.chat_send_btn = ctk.CTkButton(
            input_row,
            text="Envoyer ➔",
            width=100,
            height=44,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            font=ctk.CTkFont(weight="bold"),
            command=self._send_chat_message
        )
        self.chat_send_btn.pack(side="right")

        return frame

    def _toggle_vocal_question(self):
        if not self.is_vocal_recording:
            # Start vocal recording
            self.vocal_recorder.start("question_vocal.mp3")
            self.is_vocal_recording = True
            self.chat_mic_btn.configure(
                text="🔴 Stop & Envoyer",
                fg_color="#DC2626",
                hover_color="#B91C1C"
            )
        else:
            # Stop recording and transcribe
            self.is_vocal_recording = False
            self.chat_mic_btn.configure(
                text="⌛ Transcription...",
                fg_color="#D97706",
                hover_color="#B45309"
            )
            audio_p = self.vocal_recorder.stop()

            def _transcribe_worker():
                transcription = transcribe_vocal_question(audio_p, self.config)
                self.after(0, lambda: self._on_vocal_question_ready(transcription))

            threading.Thread(target=_transcribe_worker, daemon=True).start()

    def _on_vocal_question_ready(self, question_text: str):
        self.chat_mic_btn.configure(
            text="🎙️ Parler au micro",
            fg_color="#10B981",
            hover_color="#059669"
        )
        if question_text:
            self.chat_entry.delete(0, "end")
            self.chat_entry.insert(0, question_text)
            self._send_chat_message()

    def _toggle_listen_reply(self):
        if self.voice_speaker.is_speaking():
            self.voice_speaker.stop()
            self.chat_listen_btn.configure(text="🔊 Écouter l'explication", fg_color="#334155")
        else:
            to_speak = self.latest_prof_reply
            if not to_speak:
                # Fallback to last text from chat
                all_text = self.chat_history_box.get("1.0", "end")
                parts = all_text.split("👨‍🏫 Professeur :")
                if len(parts) > 1:
                    to_speak = parts[-1].split("-----------------------------------------------------------------")[0].strip()

            if to_speak:
                self.chat_listen_btn.configure(text="⏹️ Arrêter l'audio", fg_color="#DC2626")
                self.voice_speaker.speak_async(to_speak, on_done=lambda: self.after(0, self._on_tts_done))
            else:
                messagebox.showinfo("Aucune réponse", "Posez d'abord une question au professeur pour écouter son explication.")

    def _on_tts_done(self):
        self.chat_listen_btn.configure(text="🔊 Écouter l'explication", fg_color="#334155")

    def _send_chat_message(self):
        q = self.chat_entry.get().strip()
        if not q:
            return

        self.chat_entry.delete(0, "end")
        self.chat_history_box.insert("end", f"👤 Vous : {q}\n\n")
        self.chat_history_box.insert("end", "👨‍🏫 Professeur : En train de réfléchir...\n")
        self.chat_history_box.see("end")

        self.chat_send_btn.configure(state="disabled")

        # Run API call in background thread
        def call_ai():
            answer = ask_professor_question(q, self.latest_course_data, self.config)
            self.after(0, lambda: self._on_chat_response(answer))

        threading.Thread(target=call_ai, daemon=True).start()

    def _on_chat_response(self, answer: str):
        # Remove placeholder line
        text = self.chat_history_box.get("1.0", "end")
        if "👨‍🏫 Professeur : En train de réfléchir...\n" in text:
            text = text.replace("👨‍🏫 Professeur : En train de réfléchir...\n", "")
            self.chat_history_box.delete("1.0", "end")
            self.chat_history_box.insert("1.0", text)

        self.latest_prof_reply = answer
        self.chat_history_box.insert("end", f"👨‍🏫 Professeur : {answer}\n\n" + "-"*65 + "\n\n")
        self.chat_history_box.see("end")
        self.chat_send_btn.configure(state="normal")
        self.chat_listen_btn.configure(state="normal", text="🔊 Écouter l'explication", fg_color="#334155")

    # -------------------------------------------------------------
    # TAB 4: FLASHCARDS & ANKI
    # -------------------------------------------------------------
    def _build_flashcards_tab(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")

        title_lbl = ctk.CTkLabel(
            frame, 
            text="🧠 Flashcards & Export Anki / Quizlet", 
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#F8FAFC"
        )
        title_lbl.pack(anchor="w", pady=(0, 4))

        sub_lbl = ctk.CTkLabel(
            frame, 
            text="Révisez activement les définitions clés et exportez-les directement vers Anki.", 
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8"
        )
        sub_lbl.pack(anchor="w", pady=(0, 15))

        # Flashcard Flip Box
        self.flashcard_box = ctk.CTkFrame(frame, fg_color="#131D31", corner_radius=15, border_width=2, border_color="#2563EB")
        self.flashcard_box.pack(fill="both", expand=True, padx=20, pady=10)

        self.card_header_lbl = ctk.CTkLabel(
            self.flashcard_box,
            text="CARTE 1 SUR 5  •  RECTO (QUESTION)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38BDF8"
        )
        self.card_header_lbl.pack(pady=(20, 10))

        self.card_content_lbl = ctk.CTkLabel(
            self.flashcard_box,
            text="Chargement...",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#FFFFFF",
            wraplength=700,
            justify="center"
        )
        self.card_content_lbl.pack(expand=True, padx=30, pady=20)

        self.flip_btn = ctk.CTkButton(
            self.flashcard_box,
            text="🔄 Retourner la Carte (Voir Réponse)",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
            fg_color="#334155",
            hover_color="#475569",
            command=self._flip_card
        )
        self.flip_btn.pack(pady=(0, 25))

        # Navigation row
        nav_row = ctk.CTkFrame(frame, fg_color="transparent")
        nav_row.pack(fill="x", padx=20, pady=(5, 15))

        self.prev_card_btn = ctk.CTkButton(
            nav_row,
            text="◀ Précédente",
            width=130,
            height=38,
            command=self._prev_card
        )
        self.prev_card_btn.pack(side="left")

        self.next_card_btn = ctk.CTkButton(
            nav_row,
            text="Suivante ▶",
            width=130,
            height=38,
            command=self._next_card
        )
        self.next_card_btn.pack(side="left", padx=10)

        self.export_anki_btn = ctk.CTkButton(
            nav_row,
            text="📥 Exporter vers Anki / Quizlet (.csv)",
            font=ctk.CTkFont(weight="bold"),
            height=38,
            fg_color="#10B981",
            hover_color="#059669",
            command=self._export_anki
        )
        self.export_anki_btn.pack(side="right")

        self._load_flashcard()
        return frame

    def _load_flashcard(self):
        if not self.latest_course_data or not self.latest_course_data.get("flashcards"):
            self.card_header_lbl.configure(
                text="FLASHCARDS EN ATTENTE",
                text_color="#94A3B8"
            )
            self.card_content_lbl.configure(
                text="Aucune flashcard disponible pour le moment.\nCollez le lien de votre séance dans l'onglet 'Nouveau Cours' et lancez la génération !",
                text_color="#CBD5E1"
            )
            self.flip_btn.configure(state="disabled", text="🔄 Retourner la Carte")
            self.prev_card_btn.configure(state="disabled")
            self.next_card_btn.configure(state="disabled")
            self.export_anki_btn.configure(state="disabled")
            return

        cards = self.latest_course_data.get("flashcards", [])
        if self.current_card_index >= len(cards):
            self.current_card_index = 0

        c = cards[self.current_card_index]
        self.card_is_flipped = False
        self.card_header_lbl.configure(
            text=f"CARTE {self.current_card_index + 1} SUR {len(cards)}  •  RECTO (CONCEPT)",
            text_color="#38BDF8"
        )
        self.card_content_lbl.configure(text=c.get("front", ""), text_color="#FFFFFF")
        self.flip_btn.configure(state="normal", text="🔄 Retourner la Carte (Voir Réponse)")
        self.prev_card_btn.configure(state="normal" if self.current_card_index > 0 else "disabled")
        self.next_card_btn.configure(state="normal" if self.current_card_index + 1 < len(cards) else "disabled")
        self.export_anki_btn.configure(state="normal")

    def _flip_card(self):
        if not self.latest_course_data:
            return
        cards = self.latest_course_data.get("flashcards", [])
        if not cards or self.current_card_index >= len(cards):
            return
        c = cards[self.current_card_index]

        if not self.card_is_flipped:
            self.card_is_flipped = True
            self.card_header_lbl.configure(
                text=f"CARTE {self.current_card_index + 1} SUR {len(cards)}  •  VERSO (DÉFINITION & RÉPONSE)",
                text_color="#A7F3D0"
            )
            self.card_content_lbl.configure(text=c.get("back", ""), text_color="#6EE7B7")
            self.flip_btn.configure(text="🔄 Retourner vers le Recto")
        else:
            self._load_flashcard()

    def _prev_card(self):
        if not self.latest_course_data:
            return
        cards = self.latest_course_data.get("flashcards", [])
        if self.current_card_index > 0:
            self.current_card_index -= 1
            self._load_flashcard()

    def _next_card(self):
        if not self.latest_course_data:
            return
        cards = self.latest_course_data.get("flashcards", [])
        if self.current_card_index + 1 < len(cards):
            self.current_card_index += 1
            self._load_flashcard()

    def _export_anki(self):
        if not self.latest_course_data:
            messagebox.showwarning("Vide", "Aucun cours chargé pour le moment.")
            return
        cards = self.latest_course_data.get("flashcards", [])
        if not cards:
            messagebox.showwarning("Vide", "Aucune flashcard à exporter.")
            return

        title = self.latest_course_data.get("title", "Cours_Dirasa")
        clean = "".join(c for c in title if c.isalnum() or c == "_")[:25]
        out_path = os.path.join(self.config.get("output_dir", "exports"), f"Anki_{clean}.csv")

        export_anki_csv(cards, out_path, course_title=title)
        open_directory(os.path.dirname(out_path))
        messagebox.showinfo("Export Anki Réussi", f"Fichier Anki (.csv) créé avec succès :\n{out_path}\n\nVous pouvez l'importer directement dans Anki ou Quizlet !")

    # -------------------------------------------------------------
    # TAB 5: PREVIEW & MINDMAP
    # -------------------------------------------------------------
    def _build_preview_tab(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")

        title_lbl = ctk.CTkLabel(
            frame, 
            text="Aperçu Pédagogique & Mindmap Visuelle", 
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#F8FAFC"
        )
        title_lbl.pack(anchor="w", pady=(0, 15))

        self.preview_textbox = ctk.CTkTextbox(
            frame, 
            font=ctk.CTkFont(size=13, family="Consolas"), 
            fg_color="#131D31",
            text_color="#E2E8F0"
        )
        self.preview_textbox.pack(fill="both", expand=True, pady=(0, 15))
        self._refresh_preview_text()

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x")

        copy_btn = ctk.CTkButton(
            btn_row,
            text="📋 Copier le Résumé & Mindmap",
            width=200,
            command=self._copy_preview
        )
        copy_btn.pack(side="left", padx=(0, 10))

        return frame

    def _refresh_preview_text(self):
        if not self.latest_course_data:
            self.preview_textbox.delete("1.0", "end")
            self.preview_textbox.insert(
                "1.0",
                "Aucun cours n'est chargé pour le moment.\n\n"
                "Pour commencer :\n"
                "1. Allez dans l'onglet 'Nouveau Cours'.\n"
                "2. Collez le lien de votre séance (BigBlueButton, YouTube, Google Drive...) ou sélectionnez un enregistrement audio/vidéo.\n"
                "3. Cliquez sur 'LANCER LA GÉNÉRATION DU COURS PDF'.\n\n"
                "L'application va extraire le cours structuré, la Mindmap visuelle, les Flashcards, le Quiz et la fiche Aide-Mémoire !"
            )
            return
        summary = self.latest_course_data.get("summary", "")
        title = self.latest_course_data.get("title", "")
        module = self.latest_course_data.get("module", "")
        toc = "\n".join([f"  • {item}" for item in self.latest_course_data.get("table_of_contents", [])])
        takeaways = "\n".join([f"  ✓ {item}" for item in self.latest_course_data.get("key_takeaways", [])])

        # Mindmap
        mindmap_lines = []
        for branch in self.latest_course_data.get("mindmap", []):
            mindmap_lines.append(f"  ├── {branch.get('topic', '')}")
            for sub in branch.get("subtopics", []):
                mindmap_lines.append(f"  │    └── {sub}")
        mindmap_str = "\n".join(mindmap_lines) if mindmap_lines else "Non disponible."

        preview_str = f"TITRE : {title}\nMODULE : {module}\n\n"
        preview_str += f"RÉSUMÉ :\n{summary}\n\n"
        preview_str += f"CARTE MENTALE (MINDMAP) :\n{mindmap_str}\n\n"
        preview_str += f"PLAN DU COURS :\n{toc}\n\n"
        preview_str += f"POINTS CLÉS D'EXAMEN :\n{takeaways}\n\n"

        self.preview_textbox.delete("1.0", "end")
        self.preview_textbox.insert("1.0", preview_str)

    def _copy_preview(self):
        text = self.preview_textbox.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copié", "Contenu copié dans le presse-papier !")

    # -------------------------------------------------------------
    # TAB 6: TRANSCRIPT
    # -------------------------------------------------------------
    def _build_transcript_tab(self):
        frame = ctk.CTkFrame(self.main_container, fg_color="transparent")

        title_lbl = ctk.CTkLabel(
            frame, 
            text="Transcription Intégrale de la Séance (Speech-to-Text)", 
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#F8FAFC"
        )
        title_lbl.pack(anchor="w", pady=(0, 15))

        self.transcript_textbox = ctk.CTkTextbox(
            frame, 
            font=ctk.CTkFont(size=13), 
            fg_color="#131D31",
            text_color="#E2E8F0"
        )
        self.transcript_textbox.pack(fill="both", expand=True, pady=(0, 15))
        init_transcript = self.latest_course_data.get("raw_transcript", "") if self.latest_course_data else "Aucune transcription pour le moment.\n\nLancez la génération d'un cours pour afficher la transcription audio complète ici."
        self.transcript_textbox.insert("1.0", init_transcript)

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x")

        copy_btn = ctk.CTkButton(
            btn_row,
            text="📋 Copier la Transcription",
            width=180,
            command=self._copy_transcript
        )
        copy_btn.pack(side="left", padx=(0, 10))

        save_txt_btn = ctk.CTkButton(
            btn_row,
            text="💾 Enregistrer en .TXT",
            width=180,
            fg_color="#334155",
            hover_color="#475569",
            command=self._save_transcript_file
        )
        save_txt_btn.pack(side="left")

        return frame

    def _copy_transcript(self):
        text = self.transcript_textbox.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copié", "La transcription a été copiée dans le presse-papier !")

    def _save_transcript_file(self):
        text = self.transcript_textbox.get("1.0", "end").strip()
        if not text:
            return
        dest = filedialog.asksaveasfilename(
            defaultextension=".txt", 
            filetypes=[("Fichier texte", "*.txt")],
            title="Enregistrer la transcription"
        )
        if dest:
            with open(dest, "w", encoding="utf-8") as f:
                f.write(text)
            messagebox.showinfo("Enregistré", f"Fichier enregistré sous :\n{dest}")

    # -------------------------------------------------------------
    # TAB 7: SETTINGS
    # -------------------------------------------------------------
    def _build_settings_tab(self):
        frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")

        title_lbl = ctk.CTkLabel(
            frame, 
            text="Paramètres & Clés IA 100% Gratuites (Faboor)", 
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#F8FAFC"
        )
        title_lbl.pack(anchor="w", pady=(0, 15))

        banner = ctk.CTkFrame(frame, fg_color="#1E293B", corner_radius=10, border_width=1, border_color="#334155")
        banner.pack(fill="x", pady=(0, 20), ipady=10)

        banner_title = ctk.CTkLabel(
            banner, 
            text="💡 Clé Google Gemini Flash Gratuite (Sans Carte Bancaire)", 
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#38BDF8"
        )
        banner_title.pack(anchor="w", padx=15, pady=(5, 5))

        banner_text = ctk.CTkLabel(
            banner, 
            text="Google AI Studio offre un accès gratuit (Gemini 3.5 Flash) SANS carte bancaire.\n"
                 "Votre clé est sauvegardée localement et permet de transcrire et structurer vos cours à volonté.",
            font=ctk.CTkFont(size=12),
            text_color="#CBD5E1",
            justify="left"
        )
        banner_text.pack(anchor="w", padx=15, pady=(0, 10))

        get_key_btn = ctk.CTkButton(
            banner,
            text="🔗 Ouvrir Google AI Studio pour obtenir une clé",
            height=36,
            fg_color="#0284C7",
            hover_color="#0369A1",
            command=lambda: webbrowser.open("https://aistudio.google.com/apikey")
        )
        get_key_btn.pack(anchor="w", padx=15, pady=(0, 5))

        gemini_box = ctk.CTkFrame(frame, fg_color="#131D31", corner_radius=10)
        gemini_box.pack(fill="x", pady=(0, 15), ipady=10)

        gem_lbl = ctk.CTkLabel(gemini_box, text="Google Gemini API Key :", font=ctk.CTkFont(weight="bold"))
        gem_lbl.pack(anchor="w", padx=15, pady=(10, 5))

        self.gemini_key_entry = ctk.CTkEntry(
            gemini_box, 
            placeholder_text="Collez votre clé Gemini (ex: AIzaSy... ou AQ...)",
            height=40,
            show="*"
        )
        self.gemini_key_entry.pack(fill="x", padx=15, pady=(0, 10))
        if self.config.get("gemini_api_key"):
            self.gemini_key_entry.insert(0, self.config["gemini_api_key"])

        out_box = ctk.CTkFrame(frame, fg_color="#131D31", corner_radius=10)
        out_box.pack(fill="x", pady=(0, 20), ipady=10)

        out_lbl = ctk.CTkLabel(out_box, text="Dossier d'exportation des PDF & Anki :", font=ctk.CTkFont(weight="bold"))
        out_lbl.pack(anchor="w", padx=15, pady=(10, 5))

        out_row = ctk.CTkFrame(out_box, fg_color="transparent")
        out_row.pack(fill="x", padx=15, pady=(0, 10))

        self.out_dir_entry = ctk.CTkEntry(out_row, height=36)
        self.out_dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.out_dir_entry.insert(0, self.config.get("output_dir", ""))

        browse_out_btn = ctk.CTkButton(
            out_row, 
            text="Changer...", 
            width=90, 
            command=self._choose_output_dir
        )
        browse_out_btn.pack(side="right")

        save_btn = ctk.CTkButton(
            frame,
            text="💾 Enregistrer les Paramètres",
            height=44,
            fg_color="#10B981",
            hover_color="#059669",
            font=ctk.CTkFont(weight="bold"),
            command=self._save_settings
        )
        save_btn.pack(fill="x", pady=(0, 20))

        return frame

    def _choose_output_dir(self):
        chosen = filedialog.askdirectory(title="Choisir le dossier d'export")
        if chosen:
            self.out_dir_entry.delete(0, "end")
            self.out_dir_entry.insert(0, chosen)

    def _save_settings(self):
        self.config["gemini_api_key"] = self.gemini_key_entry.get().strip()
        self.config["output_dir"] = self.out_dir_entry.get().strip()
        save_config(self.config)
        self.provider_status_label.configure(text=self._get_provider_status_text())
        messagebox.showinfo("Succès", "Paramètres sauvegardés avec succès !")

    # -------------------------------------------------------------
    # TAB 8: HELP
    # -------------------------------------------------------------
    def _build_help_tab(self):
        frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")

        title_lbl = ctk.CTkLabel(
            frame, 
            text="Guide des Nouvelles Fonctionnalités 🚀", 
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#F8FAFC"
        )
        title_lbl.pack(anchor="w", pady=(0, 15))

        help_content = (
            "🎯 1. LE QUIZ QCM INTERACTIF :\n"
            "--------------------------------------------------\n"
            "• Après chaque séance générée, ouvrez l'onglet 'Quiz QCM'.\n"
            "• Répondez aux questions pour tester votre compréhension.\n"
            "• L'application vous donne une correction instantanée avec explications détaillées.\n\n"
            "🧠 2. LES FLASHCARDS & EXPORT ANKI (.CSV) :\n"
            "--------------------------------------------------\n"
            "• Parcourez les cartes mémo dans l'onglet 'Flashcards'.\n"
            "• Cliquez sur 'Exporter vers Anki' : un fichier .csv compatible Anki et Quizlet est créé automatiquement !\n\n"
            "💬 3. SAWEL L'PROF (CHAT AVEC LA SÉANCE) :\n"
            "--------------------------------------------------\n"
            "• Posez vos questions au professeur virtuel en Français ou en Darija.\n"
            "• Il connaît le contenu exact de l'enregistrement et vous répond avec pédagogie !\n\n"
            "🖼️ 4. EXTRACTION DES SLIDES DU PROFESSEUR :\n"
            "--------------------------------------------------\n"
            "• Pour les séances BigBlueButton et vidéos, les diapositives clés sont automatiquement capturées et intégrées en fin de PDF !\n\n"
            "📄 5. FICHE AIDE-MÉMOIRE (1 PAGE) :\n"
            "--------------------------------------------------\n"
            "• Chaque PDF généré contient une page finale 'Fiche Aide-Mémoire Express' avec définitions, formules et pièges d'examen pour réviser 15 minutes avant le contrôle !"
        )

        help_box = ctk.CTkTextbox(
            frame, 
            font=ctk.CTkFont(size=13, family="Segoe UI"), 
            fg_color="#131D31",
            text_color="#E2E8F0"
        )
        help_box.pack(fill="both", expand=True, ipady=150)
        help_box.insert("1.0", help_content)
        help_box.configure(state="disabled")

        return frame

    # -------------------------------------------------------------
    # BACKGROUND WORKER PIPELINE
    # -------------------------------------------------------------
    def start_processing(self):
        if self.is_processing:
            messagebox.showwarning("En cours", "Un traitement est déjà en cours...")
            return

        mode = self.source_mode_var.get()
        source = ""
        if mode == "url":
            source = self.url_entry.get().strip()
            if not source:
                messagebox.showerror("Lien Manquant", "Veuillez coller le lien de l'enregistrement.")
                return
        else:
            if not self.selected_local_file or not os.path.isfile(self.selected_local_file):
                messagebox.showerror("Fichier Manquant", "Veuillez sélectionner un fichier audio ou vidéo local.")
                return
            source = self.selected_local_file

        self.is_processing = True
        self.launch_btn.configure(state="disabled", text="⏳ TRAITEMENT EN COURS...")
        self.result_frame.pack_forget()
        self.progressbar.set(0.05)
        self.progress_label.configure(text="Démarrage du traitement...")

        thread = threading.Thread(target=self._run_pipeline, args=(source,), daemon=True)
        thread.start()

    def _update_progress(self, percent: float, message: str):
        self.after(0, lambda: self._apply_progress(percent, message))

    def _apply_progress(self, percent: float, message: str):
        self.progressbar.set(percent)
        self.progress_label.configure(text=message)

    def _run_pipeline(self, source: str):
        try:
            # STEP 1: DOWNLOAD & EXTRACT SLIDES
            self._update_progress(0.1, "Étape 1/4 : Téléchargement & Extraction des slides...")
            audio_info = download_audio(source, progress_callback=self._update_progress)
            audio_path = audio_info["audio_path"]
            title_hint = audio_info.get("title", "Séance de Cours")
            slides = audio_info.get("slides", [])

            # STEP 2: TRANSCRIPTION & GENERATION VIA GEMINI 3.5 FLASH
            self._update_progress(0.4, "Étape 2/4 : Transcription & Structuration pédagogique IA...")
            
            exec_config = self.config.copy()
            exec_config["output_language"] = self.lang_var.get()
            
            course_data = process_recording(
                audio_path, 
                exec_config, 
                progress_callback=self._update_progress,
                slides_pdf_path=self.selected_slides_file
            )
            
            user_module = self.module_entry.get().strip()
            if user_module:
                course_data["module"] = user_module
            if not course_data.get("title") or course_data["title"] == "Séance de Cours":
                course_data["title"] = title_hint

            # Attach slides
            if slides:
                course_data["slides"] = slides

            self.latest_course_data = course_data
            out_dir = self.config.get("output_dir", os.path.join(os.path.dirname(__file__), "exports"))
            os.makedirs(out_dir, exist_ok=True)
            try:
                latest_json_path = os.path.join(out_dir, "latest_course.json")
                with open(latest_json_path, "w", encoding="utf-8") as f:
                    json.dump(course_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Note saving latest course json: {e}")

            # STEP 3: GENERATE PDF
            self._update_progress(0.85, "Étape 3/4 : Génération du PDF avec Mindmap, Aide-Mémoire & Slides...")
            
            clean_title = "".join(c for c in course_data["title"] if c.isalnum() or c in (' ', '_', '-')).strip()
            if not clean_title:
                clean_title = "Cours_Dirasa"
            clean_title = clean_title.replace(" ", "_")[:40]
            
            timestamp = int(time.time())
            pdf_filename = f"{clean_title}_{timestamp}.pdf"
            pdf_path = os.path.join(out_dir, pdf_filename)

            generate_course_pdf(course_data, pdf_path)
            self.latest_pdf_path = pdf_path

            # Register in Library & save individual course JSON
            try:
                add_course_to_library(course_data, pdf_path, out_dir)
            except Exception as e:
                print(f"Note saving to library: {e}")

            # STEP 4: POPULATE TABS
            self.after(0, self._on_pipeline_success)

        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: self._on_pipeline_error(err_msg))

    def _on_pipeline_success(self):
        self.is_processing = False
        self.launch_btn.configure(state="normal", text="🚀 LANCER LA GÉNÉRATION (COURS PDF + QUIZ + FLASHCARDS)")
        self.progressbar.set(1.0)
        self.progress_label.configure(text="✅ Cours PDF généré avec succès !")

        # Refresh Preview Text
        self._refresh_preview_text()

        # Refresh Transcript
        raw_t = self.latest_course_data.get("raw_transcript", "Aucune transcription disponible.")
        self.transcript_textbox.delete("1.0", "end")
        self.transcript_textbox.insert("1.0", raw_t)

        # Reload Quiz & Flashcards
        self._restart_quiz()
        self._load_flashcard()

        # Reload Library
        if hasattr(self, "_reload_library_data"):
            self._reload_library_data()

        # Show result card
        self.result_frame.pack(fill="x", pady=(0, 18))
        messagebox.showinfo(
            "Génération Réussie !", 
            f"Félicitations !\nLe cours PDF est prêt : {os.path.basename(self.latest_pdf_path)}\n\n"
            "Le Quiz QCM, les Flashcards Anki et le Chat Professeur sont maintenant disponibles dans les onglets à gauche !"
        )

    def _on_pipeline_error(self, err_msg: str):
        self.is_processing = False
        self.launch_btn.configure(state="normal", text="🚀 LANCER LA GÉNÉRATION (COURS PDF + QUIZ + FLASHCARDS)")
        self.progressbar.set(0)
        self.progress_label.configure(text=f"❌ Erreur : {err_msg[:60]}...")
        messagebox.showerror("Erreur de traitement", f"Une erreur est survenue :\n\n{err_msg}")

    def _open_generated_pdf(self):
        if self.latest_pdf_path and os.path.exists(self.latest_pdf_path):
            open_file(self.latest_pdf_path)

if __name__ == "__main__":
    app = DirasaApp()
    app.mainloop()
