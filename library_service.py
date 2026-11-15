import os
import json
import time
from datetime import datetime
from typing import List, Dict, Optional

LIBRARY_INDEX_NAME = "courses_library.json"

def get_library_index_path(output_dir: str) -> str:
    return os.path.join(output_dir, LIBRARY_INDEX_NAME)

def load_courses_library(output_dir: str) -> List[Dict]:
    """
    Loads all courses from the library index.
    Also scans the exports directory for any standalone PDF files that may not yet be indexed.
    """
    os.makedirs(output_dir, exist_ok=True)
    index_path = get_library_index_path(output_dir)
    courses = []

    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    courses = data
        except Exception as e:
            print(f"Error loading course library index: {e}")

    # Synchronize with files in output_dir (deduplicating by filename)
    indexed_basenames = {os.path.basename(c.get("pdf_path", "")) for c in courses if c.get("pdf_path")}
    updated = False

    try:
        for file in os.listdir(output_dir):
            if file.endswith(".pdf") and not file.startswith("."):
                if file not in indexed_basenames:
                    pdf_path = os.path.normpath(os.path.join(output_dir, file))
                    base_name = os.path.splitext(file)[0]
                    json_path = os.path.join(output_dir, f"{base_name}.json")
                    course_info = _create_discovered_course_entry(pdf_path, json_path)
                    courses.append(course_info)
                    indexed_basenames.add(file)
                    updated = True
    except Exception as e:
        print(f"Error scanning exports folder: {e}")

    # Deduplicate and filter out entries whose PDF file no longer exists
    deduped = []
    seen = set()
    for c in courses:
        p = c.get("pdf_path", "")
        base = os.path.basename(p)
        full_exists = os.path.exists(p) or os.path.exists(os.path.join(output_dir, base))
        if base and base not in seen and full_exists:
            seen.add(base)
            # Ensure pdf_path is valid
            if not os.path.exists(p) and os.path.exists(os.path.join(output_dir, base)):
                c["pdf_path"] = os.path.normpath(os.path.join(output_dir, base))
            deduped.append(c)

    if len(deduped) != len(courses):
        courses = deduped
        updated = True
    else:
        courses = deduped

    # Sort newest first
    courses.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

    if updated:
        save_courses_library(courses, output_dir)

    return courses

def _create_discovered_course_entry(pdf_path: str, json_path: str) -> Dict:
    """Creates a library entry for a discovered PDF file."""
    mtime = os.path.getmtime(pdf_path) if os.path.exists(pdf_path) else time.time()
    date_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y à %H:%M")
    size_mb = round(os.path.getsize(pdf_path) / (1024 * 1024), 2) if os.path.exists(pdf_path) else 0.0
    
    # Try reading details from matching json
    title = ""
    module = "Général"
    summary = ""
    chapters_count = 0
    flashcards_count = 0
    quiz_count = 0

    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                title = data.get("title", "")
                module = data.get("module", "Général")
                summary = data.get("summary", "")
                chapters_count = len(data.get("chapters", []))
                flashcards_count = len(data.get("flashcards", []))
                quiz_count = len(data.get("quiz", []))
        except Exception:
            pass

    if not title:
        raw_name = os.path.splitext(os.path.basename(pdf_path))[0]
        clean = raw_name.replace("__", " - ").replace("_", " ")
        title = clean.title()

    if module == "Général":
        tl = title.lower()
        if "python" in tl or "poo" in tl:
            module = "Python POO"
        elif "réseau" in tl or "client" in tl or "serveur" in tl:
            module = "Programmation Réseau C"
        elif "algo" in tl or "tri" in tl or "arbre" in tl:
            module = "Algorithmique"
        elif "droit" in tl or "jurid" in tl:
            module = "Droit & Économie"
        elif "math" in tl or "algebre" in tl:
            module = "Mathématiques"

    course_id = f"course_{int(mtime)}"

    return {
        "id": course_id,
        "title": title,
        "module": module,
        "date": date_str,
        "timestamp": int(mtime),
        "pdf_path": pdf_path,
        "json_path": json_path if os.path.exists(json_path) else None,
        "pdf_size_mb": size_mb,
        "summary": summary or "Cours universitaire extrait et structuré par DIRASA AI.",
        "chapters_count": chapters_count,
        "flashcards_count": flashcards_count,
        "quiz_count": quiz_count
    }

def save_courses_library(courses: List[Dict], output_dir: str):
    """Saves the library index list to JSON."""
    index_path = get_library_index_path(output_dir)
    try:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(courses, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving course library index: {e}")

def add_course_to_library(course_data: dict, pdf_path: str, output_dir: str) -> Dict:
    """
    Saves course_data JSON to disk and adds/updates it in the library.
    """
    os.makedirs(output_dir, exist_ok=True)
    mtime = time.time()
    date_str = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y à %H:%M")
    
    clean_title = "".join(c for c in course_data.get("title", "Cours") if c.isalnum() or c in (' ', '_', '-')).strip()
    clean_title = clean_title.replace(" ", "_")[:35]
    timestamp = int(mtime)

    # Save individual course JSON
    json_path = os.path.join(output_dir, f"{clean_title}_{timestamp}.json")
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(course_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving individual course JSON: {e}")

    # Also update latest_course.json
    latest_json = os.path.join(output_dir, "latest_course.json")
    try:
        with open(latest_json, "w", encoding="utf-8") as f:
            json.dump(course_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving latest course JSON: {e}")

    size_mb = round(os.path.getsize(pdf_path) / (1024 * 1024), 2) if os.path.exists(pdf_path) else 0.0

    entry = {
        "id": f"course_{timestamp}",
        "title": course_data.get("title", "Séance de Cours"),
        "module": course_data.get("module", "Général"),
        "date": date_str,
        "timestamp": timestamp,
        "pdf_path": os.path.normpath(pdf_path),
        "json_path": os.path.normpath(json_path),
        "pdf_size_mb": size_mb,
        "summary": course_data.get("summary", ""),
        "chapters_count": len(course_data.get("chapters", [])),
        "flashcards_count": len(course_data.get("flashcards", [])),
        "quiz_count": len(course_data.get("quiz", []))
    }

    courses = load_courses_library(output_dir)
    # Remove existing with same pdf_path if any
    courses = [c for c in courses if os.path.normpath(c.get("pdf_path", "")) != os.path.normpath(pdf_path)]
    courses.insert(0, entry)
    save_courses_library(courses, output_dir)
    return entry

def delete_course_from_library(course_id: str, output_dir: str, delete_files: bool = False):
    """Removes a course from the library index, and optionally deletes the PDF & JSON files."""
    courses = load_courses_library(output_dir)
    target = next((c for c in courses if c.get("id") == course_id), None)
    
    if target and delete_files:
        pdf_p = target.get("pdf_path")
        json_p = target.get("json_path")
        if pdf_p and os.path.exists(pdf_p):
            try:
                os.remove(pdf_p)
            except Exception:
                pass
        if json_p and os.path.exists(json_p):
            try:
                os.remove(json_p)
            except Exception:
                pass

    courses = [c for c in courses if c.get("id") != course_id]
    save_courses_library(courses, output_dir)
    return courses

def group_courses_by_module(courses: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Groups courses by their module name.
    Returns: {"POO PYTHON": [course1, course2], "Programmation Réseau C": [course3], ...}
    Sorted chronologically so earlier sessions appear first (Séance 1, Séance 2...).
    """
    groups: Dict[str, List[Dict]] = {}
    for c in courses:
        mod = c.get("module", "Général").strip() or "Général"
        if mod not in groups:
            groups[mod] = []
        groups[mod].append(c)

    # Sort sessions inside each module (chronological: oldest to newest for logical syllabus order)
    for mod in groups:
        groups[mod].sort(key=lambda x: x.get("timestamp", 0))

    return groups

def get_sessions_for_module(courses: List[Dict], module_name: str) -> List[Dict]:
    """Returns all sessions belonging to a specific module, sorted chronologically."""
    grouped = group_courses_by_module(courses)
    return grouped.get(module_name, [])

def get_course_short_label(course: Dict, session_idx: Optional[int] = None) -> str:
    """Returns a clean compact label for dropdowns and selectors."""
    title = course.get("title", "Séance").strip()
    date_str = course.get("date", "").split(" à ")[0] if " à " in course.get("date", "") else course.get("date", "")
    prefix = f"Séance {session_idx} : " if session_idx is not None else ""
    if len(title) > 42:
        title = title[:39] + "..."
    if date_str:
        return f"{prefix}{title} ({date_str})"
    return f"{prefix}{title}"

def get_unique_modules(courses: List[Dict]) -> List[str]:
    """Returns sorted unique module names."""
    mods = set()
    for c in courses:
        m = c.get("module", "").strip()
        if m:
            mods.add(m)
    sorted_mods = sorted(list(mods))
    return ["Tous les modules"] + sorted_mods

def filter_courses(courses: List[Dict], query: str = "", module_filter: str = "Tous les modules") -> List[Dict]:
    """Filters courses by search string and module."""
    q = query.lower().strip()
    results = []

    for c in courses:
        # Module match
        if module_filter and module_filter != "Tous les modules":
            if c.get("module", "").strip().lower() != module_filter.strip().lower():
                continue

        # Text match
        if q:
            title = c.get("title", "").lower()
            mod = c.get("module", "").lower()
            summary = c.get("summary", "").lower()
            date = c.get("date", "").lower()
            if q not in title and q not in mod and q not in summary and q not in date:
                continue

        results.append(c)

    return results
