import os
import json
import time
import re
import requests
from google import genai
from google.genai import types

COURSE_EXTRACTION_PROMPT = """
Tu es un professeur d'université et un expert pédagogique. Tu as reçu l'enregistrement audio ou la transcription d'une séance de cours universitaire (qui peut comporter un mélange de Français, Arabe, Darija marocaine et termes techniques en Anglais).

Ta mission est double :
1. Transcrire fidèlement ce qui a été dit (champ "raw_transcript").
2. Transformer cette matière brute en un COURS MAGISTRAL UNIVERSITAIRE complet, structuré, clair, rigoureux et prêt pour réviser les examens.

RÉPONDS UNIQUEMENT SOUS FORME D'UN OBJET JSON VALIDE (sans texte avant ni après, pas de balises de code markdown superflues) respectant rigoureusement ce schéma :

{
  "title": "Titre exact et complet du cours",
  "module": "Matière ou Module académique",
  "instructor": "Nom du professeur (si mentionné, sinon 'Professeur')",
  "duration_summary": "Durée ou contexte de la séance",
  "summary": "Résumé global synthétique de la séance (1 à 2 paragraphes bien rédigés)",
  "prerequisites": ["Prérequis 1", "Prérequis 2"],
  "learning_objectives": [
    "Objectif pédagogique 1",
    "Objectif pédagogique 2",
    "Objectif pédagogique 3"
  ],
  "table_of_contents": [
    "1. Titre du premier chapitre",
    "2. Titre du deuxième chapitre",
    "3. ..."
  ],
  "chapters": [
    {
      "number": 1,
      "title": "Titre du chapitre",
      "introduction": "Courte introduction contextualisant cette partie",
      "sections": [
        {
          "subtitle": "Titre de la sous-partie",
          "content": "Explication détaillée, fluide, académique et approfondie.",
          "bullet_points": ["Point clé 1", "Point clé 2"]
        }
      ],
      "key_definitions": [
        {
          "term": "Terme ou Concept clé",
          "definition": "Définition précise et rigoureuse"
        }
      ],
      "formulas_or_rules": [
        {
          "name": "Nom de la formule ou principe fondamental",
          "content": "La formule mathématique / code / règle juridique / concept théorique",
          "explanation": "Explication de son application"
        }
      ],
      "professor_notes": "Conseil spécifique du professeur, piège d'examen fréquent ou remarque insistante entendue dans la séance."
    }
  ],
  "key_takeaways": [
    "Point essentiel à retenir pour l'examen 1",
    "Point essentiel 2",
    "Point essentiel 3",
    "Point essentiel 4"
  ],
  "exam_questions": [
    {
      "question": "Question type d'examen portant sur la séance ?",
      "answer": "Réponse modèle claire, structurée et argumentée."
    },
    {
      "question": "Deuxième question type ?",
      "answer": "Réponse détaillée."
    },
    {
      "question": "Troisième question type ?",
      "answer": "Réponse détaillée."
    }
  ],
  "quiz": [
    {
      "id": 1,
      "question": "Question QCM ?",
      "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
      "correct_index": 0,
      "explanation": "Explication pédagogique de la bonne réponse"
    }
  ],
  "flashcards": [
    {
      "front": "Terme / Question de révision",
      "back": "Définition ou formule à mémoriser"
    }
  ],
  "cheat_sheet": {
    "core_definitions": ["Terme clé : définition condensée", "Concept : explication flash"],
    "essential_rules": ["Règle / Formule / Syntaxe essentielle 1", "Règle 2"],
    "exam_pitfalls": ["Piège d'examen à éviter 1", "Piège 2"]
  },
  "mindmap": [
    {
      "topic": "Branche Principale 1",
      "subtopics": ["Sous-concept A", "Sous-concept B", "Sous-concept C"]
    },
    {
      "topic": "Branche Principale 2",
      "subtopics": ["Sous-concept D", "Sous-concept E"]
    }
  ],
  "raw_transcript": "Transcription fidèle et détaillée des points essentiels, explications orales, exemples concrets et échanges du professeur pendant la séance."
}

EXIGENCES STRICTES DE QUANTITÉ PÉDAGOGIQUE (TRÈS IMPORTANT) :
1. "quiz" : Génère OBLIGATOIREMENT AU MINIMUM 20 QUESTIONS À CHOIX MULTIPLES (QCM) (entre 20 et 25 questions variées, numérotées de 1 à 20+). Les questions doivent couvrir scrupuleusement l'ensemble de la séance : concepts fondamentaux, définitions, protocoles, syntaxe/code, calculs, cas pratiques et pièges d'examen fréquents. Chaque question DOIT comporter 4 options (A, B, C, D) et une explication pédagogique détaillée.
2. "flashcards" : Génère OBLIGATOIREMENT AU MINIMUM 20 FLASHCARDS (entre 20 et 25 cartes) avec pour chaque carte un recto ("front" : question, terme ou concept clé) et un verso ("back" : réponse précise, formule ou explication concise) pour une mémorisation active Anki maximale.

Langue de rédaction demandée pour le cours structuré : {target_language}.
Si la séance contient de la Darija marocaine ou du Français familier, traduis et formalise les explications dans un style académique impeccable, tout en conservant scrupuleusement le sens et les exemples concrets donnés par l'enseignant.
"""

def clean_json_response(raw_text: str) -> dict:
    """Extracts and parses JSON from model response."""
    text = raw_text.strip()
    
    # Remove markdown code fences if present
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to locate the outermost JSON object with regex
        match = re.search(r'(\{[\s\S]*\})', text)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
        raise ValueError(f"Impossible de décoder la réponse JSON de l'IA: {text[:200]}...")

def process_with_gemini(audio_path: str, api_key: str, model_name: str = "gemini-3.5-flash", language: str = "Français", progress_callback=None, slides_pdf_path: str = None) -> dict:
    """
    Uses Google Gemini Flash (100% Free Tier) to transcribe and structure the audio,
    optionally fusing official presentation slides PDF.
    """
    if progress_callback:
        progress_callback(0.2, "Connexion à Google Gemini AI...")

    client = genai.Client(api_key=api_key)

    if progress_callback:
        progress_callback(0.35, "Envoi de l'enregistrement audio à Gemini (Cloud Gratuit)...")

    # Upload file using Gemini File API (supports up to 2GB)
    file_ref = client.files.upload(file=audio_path)
    
    try:
        # Wait for file processing if needed
        time_waited = 0
        while file_ref.state.name == "PROCESSING" and time_waited < 180:
            if progress_callback:
                progress_callback(0.45, f"Traitement audio Gemini en cours ({time_waited}s)...")
            time.sleep(3)
            time_waited += 3
            file_ref = client.files.get(name=file_ref.name)

        if file_ref.state.name != "ACTIVE":
            raise RuntimeError(f"L'analyse de l'audio par Gemini a échoué (État: {file_ref.state.name})")

        if progress_callback:
            progress_callback(0.6, "Transcription & Structuration du cours avec Gemini 3.5 Flash...")

        prompt = COURSE_EXTRACTION_PROMPT.replace("{target_language}", language)

        # Slides integration if provided
        slides_info = None
        if slides_pdf_path and os.path.exists(slides_pdf_path):
            try:
                from slides_service import extract_text_from_slides
                slides_info = extract_text_from_slides(slides_pdf_path)
                if slides_info.get("total_slides", 0) > 0:
                    slides_text = slides_info.get("text", "")[:16000]
                    prompt += (
                        f"\n\n=== SUPPORT DIAPOSITIVES / SLIDES DU PROFESSEUR (PDF OFFICIEL) ===\n"
                        f"Nombre total de diapositives : {slides_info.get('total_slides')}\n"
                        f"Fichier : {slides_info.get('filename')}\n"
                        f"Contenu textuel extrait des diapositives :\n{slides_text}\n"
                        f"===================================================================\n"
                        f"CONSIGNES CRUCIALES DE FUSION SLIDES + AUDIO :\n"
                        f"1. Fusionne parfaitement les explications orales du professeur avec les diapositives officielles.\n"
                        f"2. Intègre les formules exactes, algorithmes, schémas textuels et codes affichés sur les slides.\n"
                        f"3. Dans les chapitres, ajoute des références précises aux slides (ex: '[Diapo 4 : Architecture]').\n"
                    )
            except Exception as e:
                print(f"Slides extraction note: {e}")
        
        # Priority order: gemini-3.5-flash (fast & active), then gemini-3.8-flash, then gemini-3.1-flash-lite
        candidate_models = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-3.1-flash-lite"]
        if model_name not in candidate_models:
            candidate_models.insert(0, model_name)

        last_err = None
        response = None
        for cand in candidate_models:
            try:
                if progress_callback:
                    progress_callback(0.65, f"Analyse et structuration pédagogique ({cand})...")
                response = client.models.generate_content(
                    model=cand,
                    contents=[file_ref, prompt]
                )
                if response and response.text:
                    break
            except Exception as m_err:
                last_err = m_err
                time.sleep(1)
                continue

        if not response or not response.text:
            raise RuntimeError(f"Erreur Gemini: {last_err}")

        if progress_callback:
            progress_callback(0.85, "Analyse et validation de la structure du cours...")

        course_data = clean_json_response(response.text)
        if slides_info and slides_info.get("total_slides", 0) > 0:
            course_data["slides_used"] = True
            course_data["slides_count"] = slides_info.get("total_slides", 0)
            course_data["slides_filename"] = slides_info.get("filename", "")
        return course_data

    finally:
        # Cleanup uploaded file from Gemini to save space
        try:
            client.files.delete(name=file_ref.name)
        except Exception:
            pass

def process_with_groq(audio_path: str, api_key: str, model_name: str = "llama-3.3-70b-versatile", language: str = "Français", progress_callback=None, slides_pdf_path: str = None) -> dict:
    """
    Uses Groq API (100% Free Tier):
    1. Whisper-large-v3 for ultra-fast audio transcription
    2. Llama-3.3-70b for course structuring
    """
    if progress_callback:
        progress_callback(0.25, "Transcription audio avec Groq Whisper-large-v3 (Gratuit)...")

    # Step 1: Transcription via Groq Whisper
    url_transcribe = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}

    with open(audio_path, "rb") as f:
        files = {
            "file": (os.path.basename(audio_path), f),
            "model": (None, "whisper-large-v3"),
            "response_format": (None, "json")
        }
        res = requests.post(url_transcribe, headers=headers, files=files, timeout=180)
        
    if res.status_code != 200:
        raise RuntimeError(f"Erreur Groq Whisper ({res.status_code}): {res.text}")

    raw_transcript = res.json().get("text", "")
    
    if progress_callback:
        progress_callback(0.6, "Transcription réussie ! Structuration du cours avec Llama-3...")

    # Step 2: Structuring via Groq Llama 3
    url_chat = "https://api.groq.com/openai/v1/chat/completions"
    headers_chat = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    prompt = COURSE_EXTRACTION_PROMPT.replace("{target_language}", language)
    slides_info = None
    if slides_pdf_path and os.path.exists(slides_pdf_path):
        try:
            from slides_service import extract_text_from_slides
            slides_info = extract_text_from_slides(slides_pdf_path)
            if slides_info.get("total_slides", 0) > 0:
                prompt += (
                    f"\n\n=== SUPPORT DIAPOSITIVES / SLIDES DU PROFESSEUR (PDF OFFICIEL) ===\n"
                    f"Nombre de diapos : {slides_info.get('total_slides')}\n"
                    f"Contenu des diapositives :\n{slides_info.get('text', '')[:10000]}\n"
                    f"===================================================================\n"
                )
        except Exception as e:
            print(f"Groq slides note: {e}")

    full_user_content = f"{prompt}\n\nVOICI LA TRANSCRIPTION BRUTE DE LA SÉANCE :\n\n{raw_transcript}"

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "Tu es un professeur universitaire de haut rang. Tu réponds UNIQUEMENT en JSON valide."},
            {"role": "user", "content": full_user_content}
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }

    res_chat = requests.post(url_chat, headers=headers_chat, json=payload, timeout=120)
    if res_chat.status_code != 200:
        raise RuntimeError(f"Erreur Groq Llama ({res_chat.status_code}): {res_chat.text}")

    result = res_chat.json()
    content = result["choices"][0]["message"]["content"]
    course_data = clean_json_response(content)
    
    if not course_data.get("raw_transcript"):
        course_data["raw_transcript"] = raw_transcript
        
    if slides_info and slides_info.get("total_slides", 0) > 0:
        course_data["slides_used"] = True
        course_data["slides_count"] = slides_info.get("total_slides", 0)
        course_data["slides_filename"] = slides_info.get("filename", "")

    return course_data

def get_demo_course_data(title: str = "Séance de Démonstration", language: str = "Français") -> dict:
    """
    Returns realistic structured university course data for testing without API keys.
    """
    return {
        "title": "Algorithmique Avancée & Complexité Algorithmique",
        "module": "Informatique Théorique & Génie Logiciel",
        "instructor": "Professeur Benjelloun",
        "duration_summary": "Séance magistrale de 1h30 enregistrée",
        "summary": "Cette séance fondamentale aborde l'analyse asymptotique de la complexité des algorithmes, les notations de Landau (Grand O, Omega, Theta), ainsi que les techniques de résolution des équations de récurrence pour les algorithmes diviser pour régner.",
        "prerequisites": [
            "Bases du langage C / Python",
            "Notions de mathématiques discrètes (suites, sommes)",
            "Structures de données élémentaires (tableaux, listes)"
        ],
        "learning_objectives": [
            "Maîtriser le calcul de complexité temporelle et spatiale",
            "Distinguer la complexité dans le pire, meilleur et moyen cas",
            "Appliquer le Master Theorem (Théorème Maître) pour résoudre les récurrences"
        ],
        "table_of_contents": [
            "1. Introduction à l'Efficacité Algorithmique",
            "2. Notations Asymptotiques (Grand O, Omega, Theta)",
            "3. Résolution des Récurrences & Master Theorem",
            "4. Étude de Cas : Tri Fusion vs Tri Rapide (Quicksort)"
        ],
        "chapters": [
            {
                "number": 1,
                "title": "Introduction à l'Efficacité Algorithmique",
                "introduction": "Pourquoi mesurer le temps d'exécution abstrait plutôt que les secondes réelles sur une machine spécifique.",
                "sections": [
                    {
                        "subtitle": "Indépendance matérielle",
                        "content": "Mesurer le temps d'exécution en secondes dépend du processeur, de la mémoire vive et de la charge système. L'analyse algorithmique s'intéresse au nombre d'opérations élémentaires en fonction de la taille n de l'entrée.",
                        "bullet_points": [
                            "Opérations élémentaires : affectation, comparaison, addition",
                            "Taille n : nombre d'éléments à traiter"
                        ]
                    }
                ],
                "key_definitions": [
                    {
                        "term": "Opération Élémentaire",
                        "definition": "Instruction qui s'exécute en un temps borné par une constante, indépendamment de la taille des données d'entrée."
                    }
                ],
                "formulas_or_rules": [
                    {
                        "name": "Principe de Dominance",
                        "content": "O(1) < O(log n) < O(n) < O(n log n) < O(n^2) < O(2^n) < O(n!)",
                        "explanation": "Les termes dominants l'emportent lorsque n tend vers l'infini."
                    }
                ],
                "professor_notes": "Le professeur insiste particulièrement sur le piège d'ignorer la complexité spatiale (mémoire) lors des concours et examens."
            },
            {
                "number": 2,
                "title": "Résolution des Récurrences & Master Theorem",
                "introduction": "Comment analyser la complexité d'un algorithme récursif de type Diviser pour Régner.",
                "sections": [
                    {
                        "subtitle": "Forme générale de la récurrence",
                        "content": "La forme canonique s'écrit T(n) = a * T(n/b) + f(n), où 'a' représente le nombre de sous-problèmes, 'b' le facteur de division de la taille, et 'f(n)' le coût de division et de fusion.",
                        "bullet_points": [
                            "Cas 1 : f(n) est dominé par n^(log_b a) -> T(n) = Theta(n^(log_b a))",
                            "Cas 2 : f(n) est du même ordre que n^(log_b a) -> T(n) = Theta(n^(log_b a) * log n)",
                            "Cas 3 : f(n) domine largement n^(log_b a) -> T(n) = Theta(f(n))"
                        ]
                    }
                ],
                "key_definitions": [
                    {
                        "term": "Master Theorem",
                        "definition": "Méthode systématique permettant de trouver directement la complexité asymptotique d'équations de récurrence courantes."
                    }
                ],
                "formulas_or_rules": [
                    {
                        "name": "Équation de Récurrence du Tri Fusion (Merge Sort)",
                        "content": "T(n) = 2 T(n/2) + O(n) ==> T(n) = Theta(n log n)",
                        "explanation": "Application directe du Cas 2 du Master Theorem avec a=2, b=2, et f(n)=O(n)."
                    }
                ],
                "professor_notes": "Attention : Le Master Theorem ne s'applique pas si a n'est pas constant ou si la réduction n'est pas par division (ex: T(n) = T(n-1) + 1)."
            }
        ],
        "key_takeaways": [
            "Toujours chercher le terme dominant pour n tendant vers l'infini.",
            "Ne jamais confondre le pire cas (Worst-case) avec la borne supérieure (Grand O).",
            "Le tri fusion garantit O(n log n) même dans le pire des cas, contrairement au tri rapide classique O(n^2).",
            "Mémoriser les 3 cas du Master Theorem pour l'examen final."
        ],
        "exam_questions": [
            {
                "question": "Quelle est la complexité asymptotique de l'équation T(n) = 4 T(n/2) + n ?",
                "answer": "Ici a = 4, b = 2. On calcule n^(log_2 4) = n^2. Comme f(n) = n = O(n^(2 - epsilon)), nous sommes dans le Cas 1 du Master Theorem. Donc T(n) = Theta(n^2)."
            },
            {
                "question": "Pourquoi préférer le tri fusion au tri rapide dans certains systèmes critiques ?",
                "answer": "Parce que le tri fusion est stable et possède un comportement prévisible avec une complexité garantie en Theta(n log n) dans le pire des cas, évitant les blocages système du pire cas de Quicksort en O(n^2)."
            }
        ],
        "quiz": [
            {
                "id": 1,
                "question": "Quelle est la notation asymptotique représentant la borne supérieure (pire des cas) ?",
                "options": ["A) Grand Theta (θ)", "B) Grand O (O)", "C) Grand Omega (Ω)", "D) Petit o (o)"],
                "correct_index": 1,
                "explanation": "Le Grand O désigne la borne supérieure asymptotique f(n) <= c * g(n), garantissant que l'algorithme ne fera pas pire que cette limite."
            },
            {
                "id": 2,
                "question": "Dans le Master Theorem, que représente la variable 'a' dans T(n) = a*T(n/b) + f(n) ?",
                "options": ["A) La taille de chaque sous-problème", "B) Le temps de fusion", "C) Le nombre de sous-problèmes récursifs", "D) Le nombre d'itérations d'une boucle"],
                "correct_index": 2,
                "explanation": "'a' est le nombre de sous-problèmes récursifs créés à chaque étape de division."
            },
            {
                "id": 3,
                "question": "Quelle est la complexité temporelle garantie dans le pire des cas pour le Tri Fusion (Merge Sort) ?",
                "options": ["A) O(n^2)", "B) O(n log n)", "C) O(n)", "D) O(log n)"],
                "correct_index": 1,
                "explanation": "Le tri fusion effectue toujours une division équilibrée et une fusion en temps linéaire, assurant O(n log n) en toutes circonstances."
            },
            {
                "id": 4,
                "question": "Si f(n) = n et n^(log_b a) = n^2, quel cas du Master Theorem s'applique ?",
                "options": ["A) Cas 1 (f(n) dominé polynomialement)", "B) Cas 2 (égalités d'ordres)", "C) Cas 3 (f(n) dominant)", "D) Le théorème ne s'applique pas"],
                "correct_index": 0,
                "explanation": "Puisque n est strictement inférieur à n^2 par une puissance polynomiale (epsilon = 1), le Cas 1 s'applique et T(n) = Theta(n^2)."
            },
            {
                "id": 5,
                "question": "Dans quel cas le Tri Rapide (QuickSort) atteint-il sa pire complexité en O(n^2) ?",
                "options": ["A) Lorsque le tableau contient uniquement des nombres négatifs", "B) Lorsque le tableau est déjà trié et le pivot choisi est le premier ou dernier élément", "C) Lorsque la taille n est une puissance de 2", "D) Lorsque la mémoire RAM est insuffisante"],
                "correct_index": 1,
                "explanation": "Si le tableau est déjà trié et le pivot est systématiquement un extrême, la partition est déséquilibrée (0 et n-1 éléments), produisant une récursion en chaîne de coût quadratique O(n^2)."
            },
            {
                "id": 6,
                "question": "Quelle est la complexité temporelle moyenne de la recherche dichotomique (Binary Search) dans un tableau trié ?",
                "options": ["A) O(1)", "B) O(log n)", "C) O(n)", "D) O(n log n)"],
                "correct_index": 1,
                "explanation": "À chaque comparaison, l'espace de recherche est divisé par 2, ce qui donne une complexité logarithmique en O(log n)."
            },
            {
                "id": 7,
                "question": "Quelle structure de données repose sur le principe LIFO (Last In, First Out) ?",
                "options": ["A) La Pile (Stack)", "B) La File (Queue)", "C) La Table de Hachage", "D) L'Arbre Binaire"],
                "correct_index": 0,
                "explanation": "La pile empile et dépile les données au sommet : le dernier élément inséré est le premier à sortir."
            },
            {
                "id": 8,
                "question": "Quelle structure de données repose sur le principe FIFO (First In, First Out) ?",
                "options": ["A) La Pile (Stack)", "B) La File (Queue)", "C) Le Tas Max", "D) L'Arbre AVL"],
                "correct_index": 1,
                "explanation": "La file traite les éléments dans leur ordre d'arrivée, comme une file d'attente réelle."
            },
            {
                "id": 9,
                "question": "Quel parcours d'un Arbre Binaire de Recherche (BST) permet de visiter les clés dans l'ordre croissant ?",
                "options": ["A) Parcours Préfixe", "B) Parcours Infixe (In-order)", "C) Parcours Postfixe", "D) Parcours par niveau (BFS)"],
                "correct_index": 1,
                "explanation": "Le parcours infixe visite d'abord le sous-arbre gauche (< racine), puis la racine, puis le sous-arbre droit (> racine), produisant un ordre strictement croissant."
            },
            {
                "id": 10,
                "question": "Quelle est la complexité temporelle d'insertion au début d'une liste simplement chaînée ?",
                "options": ["A) O(1)", "B) O(n)", "C) O(log n)", "D) O(n^2)"],
                "correct_index": 0,
                "explanation": "Insérer en tête de liste ne nécessite que la modification du pointeur head et du pointeur next du nouveau nœud, sans aucun décalage d'éléments, donc en O(1)."
            },
            {
                "id": 11,
                "question": "Quelle est la hauteur maximale d'un arbre binaire équilibré (AVL) à n nœuds ?",
                "options": ["A) O(n)", "B) O(log n)", "C) O(n log n)", "D) O(1)"],
                "correct_index": 1,
                "explanation": "Grâce aux rotations d'équilibrage garantissant que la différence de hauteur entre sous-arbres ne dépasse pas 1, la hauteur est bornée par O(log n)."
            },
            {
                "id": 12,
                "question": "Quelle structure de données est naturellement utilisée pour implémenter un parcours en largeur (BFS) d'un graphe ?",
                "options": ["A) Une Pile", "B) Une File (Queue)", "C) Un Arbre", "D) Un Tableau 2D"],
                "correct_index": 1,
                "explanation": "Le parcours en largeur explore niveau par niveau, nécessitant une file FIFO pour mémoriser les sommets voisins à traiter."
            },
            {
                "id": 13,
                "question": "Quelle technique consiste à stocker les résultats de sous-problèmes pour éviter des recalculs redondants en Programmation Dynamique ?",
                "options": ["A) La Mémoïsation (ou Tabulation)", "B) Le Partitionnement", "C) L'Hachage Ouvert", "D) L'Interpolation"],
                "correct_index": 0,
                "explanation": "La mémoïsation (top-down) ou la tabulation (bottom-up) stocke les sous-solutions dans un tableau ou dictionnaire pour réduire la complexité exponentielle à polynomiale."
            },
            {
                "id": 14,
                "question": "Quelle est l'hypothèse fondamentale nécessaire pour appliquer l'algorithme de Dijkstra sur un graphe orienté ?",
                "options": ["A) Le graphe doit être acyclique", "B) Tous les poids des arêtes doivent être positifs ou nuls", "C) Le graphe doit avoir moins de 100 sommets", "D) Les arêtes doivent avoir le même coût"],
                "correct_index": 1,
                "explanation": "Dijkstra repose sur un choix glouton irréversible ; la présence de poids négatifs invalide la certitude que la distance au sommet extrait est minimale."
            },
            {
                "id": 15,
                "question": "Quelle est la complexité temporelle moyenne de recherche d'une clé dans une table de hachage bien dimensionnée ?",
                "options": ["A) O(1)", "B) O(log n)", "C) O(n)", "D) O(n log n)"],
                "correct_index": 0,
                "explanation": "Avec une fonction de hachage uniforme et un facteur de charge modéré, l'accès se fait en temps constant O(1)."
            },
            {
                "id": 16,
                "question": "Quelle est la borne inférieure théorique de complexité pour tout algorithme de tri basé sur les comparaisons ?",
                "options": ["A) Omega(n)", "B) Omega(n log n)", "C) Omega(n^2)", "D) Omega(log n)"],
                "correct_index": 1,
                "explanation": "L'arbre de décision de n! permutations possibles a une hauteur minimale de log2(n!) = Omega(n log n) comparaisons."
            },
            {
                "id": 17,
                "question": "Dans un Tas Max (Max-Heap), quelle propriété relie chaque nœud parent à ses enfants ?",
                "options": ["A) Le parent est toujours strictement inférieur à ses enfants", "B) Le parent est supérieur ou égal à chacun de ses enfants", "C) L'enfant gauche est inférieur et l'enfant droit est supérieur", "D) La somme des enfants égale le parent"],
                "correct_index": 1,
                "explanation": "Dans un Max-Heap, chaque nœud a une valeur supérieure ou égale à ses descendants, garantissant la valeur maximale à la racine."
            },
            {
                "id": 18,
                "question": "Quelle est la complexité temporelle garantie du Tri par Tas (HeapSort) ?",
                "options": ["A) O(n^2)", "B) O(n log n)", "C) O(n)", "D) O(2^n)"],
                "correct_index": 1,
                "explanation": "La construction du tas prend O(n) et chaque extraction de racine prend O(log n), ce qui garantit O(n log n) dans le pire comme dans le meilleur des cas sans mémoire supplémentaire."
            },
            {
                "id": 19,
                "question": "Quelle est la principale limitation des algorithmes Gloutons (Greedy Algorithms) ?",
                "options": ["A) Ils sont impossibles à coder", "B) Ils font des choix localement optimaux qui ne garantissent pas toujours l'optimum global", "C) Ils nécessitent une mémoire infinie", "D) Ils ne fonctionnent qu'avec des chaînes de caractères"],
                "correct_index": 1,
                "explanation": "Un algorithme glouton prend la meilleure décision locale immédiate sans revenir en arrière, ce qui peut mener à une solution sous-optimale si le problème ne possède pas la propriété de choix glouton."
            },
            {
                "id": 20,
                "question": "Quelle est la complexité spatiale auxiliaire requise par le Tri Fusion (Merge Sort) standard ?",
                "options": ["A) O(1) en place", "B) O(n) mémoire supplémentaire", "C) O(n^2)", "D) O(log n)"],
                "correct_index": 1,
                "explanation": "L'étape de fusion linéaire standard alloue un tableau temporaire de taille n pour recombiner les deux moitiés triées."
            }
        ],
        "flashcards": [
            {
                "front": "Grand O (Notation O)",
                "back": "Borne supérieure asymptotique. Caractérise le comportement au pire des cas : f(n) <= c * g(n)."
            },
            {
                "front": "Grand Omega (Notation Ω)",
                "back": "Borne inférieure asymptotique. Caractérise le meilleur des cas possible : f(n) >= c * g(n)."
            },
            {
                "front": "Grand Theta (Notation θ)",
                "back": "Borne asymptotique serrée (encadrement exact de f(n) entre c1*g(n) et c2*g(n))."
            },
            {
                "front": "Master Theorem (Formule générale)",
                "back": "Résout les relations T(n) = a*T(n/b) + f(n) où 'a' est le nombre de sous-problèmes et 'b' le facteur de division."
            },
            {
                "front": "Master Theorem (Cas 1)",
                "back": "Si f(n) = O(n^(log_b a - epsilon)), alors T(n) = Theta(n^(log_b a))."
            },
            {
                "front": "Master Theorem (Cas 2)",
                "back": "Si f(n) = Theta(n^(log_b a)), alors T(n) = Theta(n^(log_b a) * log n)."
            },
            {
                "front": "Tri Fusion (Merge Sort)",
                "back": "Diviser pour régner, stable, complexité garantie en Theta(n log n), espace mémoire auxiliaire O(n)."
            },
            {
                "front": "Tri Rapide (QuickSort)",
                "back": "Partitionnement autour d'un pivot. Cas moyen O(n log n), pire cas O(n^2) si pivot extrême sur tableau trié."
            },
            {
                "front": "Recherche Dichotomique",
                "back": "Recherche par division successive par 2 dans un tableau trié. Complexité : O(log n)."
            },
            {
                "front": "Pile (Stack) & LIFO",
                "back": "Dernier entré, premier sorti (Last In First Out). Opérations Push/Pop au sommet en O(1)."
            },
            {
                "front": "File (Queue) & FIFO",
                "back": "Premier entré, premier sorti (First In First Out). Enfiler à la fin, défiler au début en O(1)."
            },
            {
                "front": "Liste Chaînée vs Tableau",
                "back": "Tableau : accès direct O(1) mais taille fixe. Liste : insertion/suppression en tête O(1) mais accès séquentiel O(n)."
            },
            {
                "front": "Arbre Binaire de Recherche (BST)",
                "back": "Tout nœud gauche < racine < tout nœud droit. Parcours infixe trié. Recherche moyenne O(log n), pire cas O(n)."
            },
            {
                "front": "Arbre AVL (Équilibré)",
                "back": "BST avec facteur d'équilibre dans {-1, 0, +1} maintenu par rotations. Hauteur garantie O(log n)."
            },
            {
                "front": "Parcours BFS vs DFS",
                "back": "BFS : parcours par niveau avec une File (Queue). DFS : parcours en profondeur avec une Pile ou récursion."
            },
            {
                "front": "Programmation Dynamique",
                "back": "Résolution de problèmes à sous-structures optimales et sous-problèmes chevauchants en mémorisant les solutions."
            },
            {
                "front": "Mémoïsation vs Tabulation",
                "back": "Mémoïsation : Top-Down avec cache. Tabulation : Bottom-Up avec itération dans un tableau."
            },
            {
                "front": "Algorithme de Dijkstra",
                "back": "Plus court chemin à source unique dans un graphe à poids strictement positifs. Complexité : O((V+E) log V)."
            },
            {
                "front": "Tas (Heap) & Heapsort",
                "back": "Arbre binaire presque complet. Max-Heap : racine = max. Heapsort trie en place en O(n log n)."
            },
            {
                "front": "Borne des Tris par Comparaison",
                "back": "Aucun algorithme de tri basé sur les comparaisons ne peut faire mieux que Omega(n log n) dans le pire des cas."
            }
        ],
        "cheat_sheet": {
            "core_definitions": [
                "Opération élémentaire : instruction dont le coût est constant O(1).",
                "Grand O : f(n) <= c * g(n) pour n >= n0 (Borne Supérieure).",
                "Master Theorem : T(n) = a*T(n/b) + f(n)."
            ],
            "essential_rules": [
                "Hiérarchie : O(1) < O(log n) < O(n) < O(n log n) < O(n^2) < O(2^n).",
                "MergeSort : T(n) = 2T(n/2) + O(n) -> Theta(n log n).",
                "QuickSort : Cas moyen O(n log n), mais Pire cas O(n^2) si pivot mal choisi."
            ],
            "exam_pitfalls": [
                "Ne jamais mesurer l'efficacité en secondes réelles (trop dépendant du CPU/charge).",
                "Le Master Theorem exige 'a >= 1' et 'b > 1' constants.",
                "Ne pas oublier la complexité spatiale mémoire (MergeSort nécessite O(n) de mémoire supplémentaire)."
            ]
        },
        "mindmap": [
            {
                "topic": "1. Notations Asymptotiques",
                "subtopics": ["Grand O (Pire cas)", "Grand Omega (Meilleur cas)", "Grand Theta (Encadrement exact)", "Hiérarchie de Landau"]
            },
            {
                "topic": "2. Algorithmes Diviser pour Régner",
                "subtopics": ["Étape de Division", "Appels Récursifs", "Étape de Fusion / Combinaison"]
            },
            {
                "topic": "3. Master Theorem",
                "subtopics": ["Forme canonique : a T(n/b) + f(n)", "Cas 1 : n^(log_b a) dominant", "Cas 2 : Équilibre (* log n)", "Cas 3 : f(n) dominant"]
            },
            {
                "topic": "4. Algorithmes de Tri",
                "subtopics": ["Tri Fusion : Garanti O(n log n)", "Tri Rapide : O(n log n) moyen / O(n^2) pire"]
            }
        ],
        "raw_transcript": "Professeur : Salam alaykoum jami3an, bienvenue dans cette nouvelle séance d'algorithmique avancée. Aujourd'hui on va attaquer un chapitre capital pour votre cursus : l'analyse de complexité asymptotique et le Master Theorem. Kima kat3erfou, ma ymkench n9iso l'algorithme b les secondes hit chaque machine 3ndha processeur f chkel. Donc ghadi nchoufo le nombre d'opérations fondamentales par rapport à la taille n..."
    }

def ask_professor_question(question: str, course_data: dict, config: dict) -> str:
    """
    Simulates a 1-on-1 tutoring session with the professor who delivered the course.
    """
    gemini_key = config.get("gemini_api_key", "").strip()
    if not gemini_key:
        return "Pour discuter avec le professeur, veuillez entrer votre clé Google Gemini gratuite dans l'onglet Paramètres."

    client = genai.Client(api_key=gemini_key)
    course_data = course_data or {}
    title = course_data.get("title", "la séance")
    module = course_data.get("module", "ce module")
    summary = course_data.get("summary", "")
    key_points = "\n".join([f"- {t}" for t in course_data.get("key_takeaways", [])])

    prompt = f"""Tu es le professeur d'université qui a animé la séance '{title}' (Module : {module}).
Voici le résumé et les points clés de ton cours :
{summary}

Points abordés :
{key_points}

Un étudiant vient te voir à la fin de la séance et te pose cette question :
"{question}"

Consignes pour ta réponse :
1. Réponds avec pédagogie, clarté, bienveillance et rigueur universitaire.
2. Si l'étudiant parle en Darija marocaine (mélange darija/français), réponds chaleureusement en Darija et Français comme on fait naturellement dans les amphis au Maroc. S'il parle en Français académique, réponds en Français soigné.
3. Donne un exemple concret si pertinent. Sois concis et direct (2 à 4 paragraphes maximum).
"""

    candidate_models = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.8-flash"]
    last_err = None

    for m in candidate_models:
        for attempt in range(2):
            try:
                res = client.models.generate_content(
                    model=m,
                    contents=prompt
                )
                if res and res.text:
                    return res.text.strip()
            except Exception as e:
                last_err = e
                time.sleep(1)

    return (
        "Salam ! Kayn un petit pic de charge temporaire 3la les serveurs gratuits de Google (Erreur 503 temporaire). "
        "3awed swlni f had la minute même, ghadi njawbek direct incha'Allah !"
    )

def process_recording(audio_path: str, config: dict, progress_callback=None, slides_pdf_path: str = None) -> dict:
    """
    Master dispatcher: selects Gemini, Groq, or Demo mode according to config,
    supporting optional slides PDF multi-source fusion.
    """
    gemini_key = config.get("gemini_api_key", "").strip()
    groq_key = config.get("groq_api_key", "").strip()
    preferred = config.get("preferred_provider", "gemini")
    language = config.get("output_language", "Français")

    # Priority 1: If preferred is gemini and key exists
    if preferred == "gemini" and gemini_key:
        model = config.get("gemini_model", "gemini-3.5-flash")
        return process_with_gemini(audio_path, gemini_key, model, language, progress_callback, slides_pdf_path=slides_pdf_path)

    # Priority 2: If preferred is groq and key exists
    if preferred == "groq" and groq_key:
        model = config.get("groq_model", "llama-3.3-70b-versatile")
        return process_with_groq(audio_path, groq_key, model, language, progress_callback, slides_pdf_path=slides_pdf_path)

    # Fallback to whichever key is provided
    if gemini_key:
        return process_with_gemini(audio_path, gemini_key, "gemini-3.5-flash", language, progress_callback, slides_pdf_path=slides_pdf_path)
    if groq_key:
        return process_with_groq(audio_path, groq_key, "llama-3.3-70b-versatile", language, progress_callback, slides_pdf_path=slides_pdf_path)

    # If NO key is provided: Run in Demo / Educational Mode
    if progress_callback:
        progress_callback(0.4, "Aucune clé API configurée - Activation du Mode Démo Pédagogique Gratuit...")
        time.sleep(1)
        progress_callback(0.7, "Génération d'une séance modèle complète et structurée...")
        time.sleep(1)
        progress_callback(1.0, "Prêt !")

    demo_data = get_demo_course_data(title="Séance de Cours Universitaire", language=language)
    if slides_pdf_path and os.path.exists(slides_pdf_path):
        from slides_service import extract_text_from_slides
        s_info = extract_text_from_slides(slides_pdf_path)
        demo_data["slides_used"] = True
        demo_data["slides_count"] = s_info.get("total_slides", 0)
        demo_data["slides_filename"] = s_info.get("filename", "")
    return demo_data
