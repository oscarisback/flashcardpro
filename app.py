import base64
import json
import os
import random
import re
import time
import urllib.parse
import zlib
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
from streamlit_drawable_canvas import st_canvas

# Must be the very first Streamlit command
st.set_page_config(
    page_title="HKDSE Flashcard Hub",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Relative path handling for cloud deployment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "flashcard_data.json")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")

st.markdown("""
<style>
    .stButton button {
        border-radius: 8px;
        font-weight: 600;
    }
    div[data-testid="stExpander"] {
        border-radius: 10px;
    }
    .highlighted-answer {
        background-color: #FFE66D;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 600;
        color: #000;
    }
    .wrong-answer-highlight {
        background-color: #FFD1D1;
        border: 2px solid #FF4D4D;
        color: #900C3F;
        padding: 8px 12px;
        border-radius: 6px;
        font-weight: bold;
        margin-top: 6px;
        margin-bottom: 6px;
    }
    .correct-answer-highlight {
        background-color: #D4EDDA;
        border: 2px solid #28A745;
        color: #155724;
        padding: 8px 12px;
        border-radius: 6px;
        font-weight: bold;
        margin-top: 6px;
        margin-bottom: 6px;
    }
    .mc-option {
        padding: 12px;
        border-radius: 8px;
        margin: 8px 0;
    }
    .mc-option-selected {
        background-color: #E3F2FD;
        border-left: 4px solid #2196F3;
    }
</style>
""", unsafe_allow_html=True)

# Data Management
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.setdefault("files", {})
                data.setdefault("unsorted_decks", {})
                return data
        except Exception:
            pass
    return {"files": {}, "unsorted_decks": {}}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        st.error(f"Failed to save data: {e}")

# Session State Initialization
if "data" not in st.session_state:
    st.session_state.data = load_data()
if "current_page" not in st.session_state:
    st.session_state.current_page = "home"
if "current_path" not in st.session_state:
    st.session_state.current_path = []
if "active_deck" not in st.session_state:
    st.session_state.active_deck = None
if "deck_location" not in st.session_state:
    st.session_state.deck_location = None
if "review_cards" not in st.session_state:
    st.session_state.review_cards = []
if "review_idx" not in st.session_state:
    st.session_state.review_idx = 0
if "show_ans" not in st.session_state:
    st.session_state.show_ans = False
if "show_srs" not in st.session_state:
    st.session_state.show_srs = False
if "reveal_blanks" not in st.session_state:
    st.session_state.reveal_blanks = False
if "blank_builder_question" not in st.session_state:
    st.session_state.blank_builder_question = ""
if "blank_builder_count" not in st.session_state:
    st.session_state.blank_builder_count = 1
if "review_mode" not in st.session_state:
    st.session_state.review_mode = "study"

# URL Parameter Import Handler
def check_and_handle_url_import():
    query_params = st.query_params
    if "deck" in query_params:
        try:
            encoded_code = query_params["deck"]
            success, message = import_any_code(encoded_code, "unsorted")
            if success:
                st.toast(f"🎉 {message}", icon="✅")
            else:
                st.toast(f"❌ Failed to import deck from link: {message}", icon="⚠️")
            st.query_params.clear()
        except Exception as e:
            st.toast(f"Failed to process link import: {str(e)}", icon="⚠️")
            st.query_params.clear()

# Helper Functions
def get_folder_dict(path):
    curr = st.session_state.data["files"]
    for p in path:
        if p in curr and "folders" in curr[p]:
            curr = curr[p]["folders"]
        else:
            return None
    return curr

def get_cards(deck_name, path):
    if path == "unsorted":
        return st.session_state.data["unsorted_decks"].get(deck_name, [])
    else:
        folder_dict = get_folder_dict(path[:-1]) if len(path) > 1 else st.session_state.data["files"]
        folder_name = path[-1] if path else ""
        return folder_dict.get(folder_name, {}).get("decks", {}).get(deck_name, [])

def list_all_folder_paths(base_dict=None, current_prefix=None):
    if base_dict is None:
        base_dict = st.session_state.data["files"]
    if current_prefix is None:
        current_prefix = []

    paths = ["Root (Unsorted)"]
    
    def _traverse(f_dict, prefix):
        for f_name, f_info in f_dict.items():
            path_tuple = prefix + [f_name]
            paths.append(" / ".join(path_tuple))
            if "folders" in f_info and f_info["folders"]:
                _traverse(f_info["folders"], path_tuple)

    _traverse(base_dict, [])
    return paths

def move_deck(deck_name, source_path, target_path_str):
    cards = []
    if source_path == "unsorted":
        if deck_name in st.session_state.data["unsorted_decks"]:
            cards = st.session_state.data["unsorted_decks"].pop(deck_name)
    else:
        folder_dict = get_folder_dict(source_path[:-1]) if len(source_path) > 1 else st.session_state.data["files"]
        if source_path and source_path[-1] in folder_dict:
            decks = folder_dict[source_path[-1]].get("decks", {})
            if deck_name in decks:
                cards = decks.pop(deck_name)

    if target_path_str == "Root (Unsorted)":
        st.session_state.data["unsorted_decks"][deck_name] = cards
    else:
        target_path = target_path_str.split(" / ")
        target_dict = get_folder_dict(target_path[:-1]) if len(target_path) > 1 else st.session_state.data["files"]
        if target_path[-1] in target_dict:
            if "decks" not in target_dict[target_path[-1]]:
                target_dict[target_path[-1]]["decks"] = {}
            target_dict[target_path[-1]]["decks"][deck_name] = cards

    save_data(st.session_state.data)

def delete_deck(deck_name, path):
    if path == "unsorted":
        st.session_state.data["unsorted_decks"].pop(deck_name, None)
    else:
        folder_dict = get_folder_dict(path[:-1]) if len(path) > 1 else st.session_state.data["files"]
        folder_name = path[-1] if path else ""
        if folder_name in folder_dict and "decks" in folder_dict[folder_name]:
            folder_dict[folder_name]["decks"].pop(deck_name, None)
    save_data(st.session_state.data)

def shuffle_deck(deck_name, path):
    cards = get_cards(deck_name, path)
    random.shuffle(cards)
    save_data(st.session_state.data)

def rename_deck(old_name, new_name, path):
    if not new_name.strip() or old_name == new_name:
        return
    cards = get_cards(old_name, path)
    delete_deck(old_name, path)
    if path == "unsorted":
        st.session_state.data["unsorted_decks"][new_name.strip()] = cards
    else:
        folder_dict = get_folder_dict(path[:-1]) if len(path) > 1 else st.session_state.data["files"]
        folder_name = path[-1] if path else ""
        folder_dict[folder_name]["decks"][new_name.strip()] = cards
    save_data(st.session_state.data)

def delete_folder(folder_name, parent_path):
    curr_dict = get_folder_dict(parent_path) if parent_path else st.session_state.data["files"]
    if folder_name in curr_dict:
        curr_dict.pop(folder_name)
        save_data(st.session_state.data)

def rename_folder(old_name, new_name, parent_path):
    if not new_name.strip() or old_name == new_name:
        return
    curr_dict = get_folder_dict(parent_path) if parent_path else st.session_state.data["files"]
    if old_name in curr_dict:
        curr_dict[new_name.strip()] = curr_dict.pop(old_name)
        save_data(st.session_state.data)

def move_folder(folder_name, source_path, target_path_str):
    source_dict = get_folder_dict(source_path) if source_path else st.session_state.data["files"]
    if folder_name not in source_dict:
        return
    
    folder_data = source_dict.pop(folder_name)
    
    if target_path_str == "Root (Unsorted)":
        source_dict[folder_name] = folder_data
        return
    else:
        target_path = target_path_str.split(" / ")
        target_dict = get_folder_dict(target_path[:-1]) if len(target_path) > 1 else st.session_state.data["files"]
        if target_path[-1] in target_dict:
            if "folders" not in target_dict[target_path[-1]]:
                target_dict[target_path[-1]]["folders"] = {}
            target_dict[target_path[-1]]["folders"][folder_name] = folder_data
    
    save_data(st.session_state.data)

# Export / Import & URL Link Generators
def export_deck_code(deck_name, cards):
    minified_cards = []
    for c in cards:
        card_data = {
            "t": c.get("type", "Standard"),
            "q": c.get("question", "")
        }
        if "answer" in c and c["answer"]:
            card_data["a"] = c["answer"]
        if "options" in c and c["options"]:
            card_data["o"] = c["options"]
        if "explanation" in c and c["explanation"]:
            card_data["e"] = c["explanation"]
        if "image" in c and c["image"]:
            card_data["i"] = c["image"]
            
        minified_cards.append(card_data)

    payload = {
        "type": "deck",
        "n": deck_name,
        "c": minified_cards
    }
    
    raw_json = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode("utf-8")
    compressed = zlib.compress(raw_json, level=9)
    return base64.urlsafe_b64encode(compressed).decode("utf-8")

def export_deck_link(deck_name, cards, base_url="http://localhost:8501"):
    encoded_code = export_deck_code(deck_name, cards)
    return f"{base_url}/?deck={urllib.parse.quote(encoded_code)}"

def export_folder_code(folder_name, folder_data):
    payload = {"type": "folder", "n": folder_name, "data": folder_data}
    raw_json = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode("utf-8")
    compressed = zlib.compress(raw_json, level=9)
    return base64.urlsafe_b64encode(compressed).decode("utf-8")

def import_any_code(encoded_code, target_path):
    try:
        clean_code = encoded_code.strip().encode("utf-8")
        
        try:
            decoded_bytes = base64.urlsafe_b64decode(clean_code)
        except Exception:
            try:
                decoded_bytes = base64.b85decode(clean_code)
            except Exception:
                decoded_bytes = base64.b64decode(clean_code)

        try:
            decompressed = zlib.decompress(decoded_bytes)
            payload = json.loads(decompressed.decode("utf-8"))
        except Exception:
            payload = json.loads(decoded_bytes.decode("utf-8"))

        item_type = payload.get("type", "deck")
        
        if item_type == "folder":
            folder_name = payload.get("n", payload.get("name", "Imported Folder"))
            folder_data = payload.get("data", {})
            target_dict = get_folder_dict(target_path) if target_path != "unsorted" else st.session_state.data["files"]
            target_dict[folder_name] = folder_data
            save_data(st.session_state.data)
            return True, f"Successfully imported folder '{folder_name}'!"
        else:
            deck_name = payload.get("n", payload.get("name", "Imported Deck"))
            raw_cards = payload.get("c", payload.get("cards", []))
            
            cards = []
            for c in raw_cards:
                if "t" in c:
                    card = {
                        "type": c.get("t", "Standard"),
                        "question": c.get("q", ""),
                        "answer": c.get("a", ""),
                        "options": c.get("o", []),
                        "explanation": c.get("e", ""),
                        "image": c.get("i", None),
                        "interval": 1,
                        "ease_factor": 2.5,
                        "next_review": time.time()
                    }
                else:
                    card = c
                cards.append(card)

            if target_path == "unsorted":
                st.session_state.data["unsorted_decks"][deck_name] = cards
            else:
                folder_dict = get_folder_dict(target_path[:-1]) if len(target_path) > 1 else st.session_state.data["files"]
                folder_name = target_path[-1] if target_path else ""
                if "decks" not in folder_dict[folder_name]:
                    folder_dict[folder_name]["decks"] = {}
                folder_dict[folder_name]["decks"][deck_name] = cards
            save_data(st.session_state.data)
            return True, f"Successfully imported deck '{deck_name}' with {len(cards)} cards!"
    except Exception as e:
        return False, f"Invalid code/link payload: {str(e)}"

def navigate_to(page, deck_name=None, location=None):
    st.session_state.current_page = page
    st.session_state.show_ans = False
    st.session_state.show_srs = False
    st.session_state.reveal_blanks = False
    if deck_name:
        st.session_state.active_deck = deck_name
    if location:
        st.session_state.deck_location = location

# Run URL import check on app refresh
check_and_handle_url_import()

# Page: Home (Dashboard)
def render_home():
    st.title("📚 HKDSE Flashcard Hub")
    st.write("Organize, study, and master your flashcards with spaced repetition!")

    # Sidebar for folder navigation
    with st.sidebar:
        st.subheader("📁 Folders & Decks")
        
        # Create new folder
        with st.expander("➕ Create New Folder"):
            new_folder_name = st.text_input("Folder Name", key="create_folder_input")
            parent_folder_display = st.selectbox(
                "Parent Folder",
                ["Root"] + [p.replace("Root (Unsorted)", "Root") for p in list_all_folder_paths()[1:]],
                key="parent_folder_select"
            )
            if st.button("Create Folder", key="create_folder_btn", use_container_width=True):
                if new_folder_name.strip():
                    if parent_folder_display == "Root":
                        st.session_state.data["files"][new_folder_name.strip()] = {"folders": {}}
                    else:
                        parent_path = parent_folder_display.split(" / ")
                        parent_dict = get_folder_dict(parent_path) if parent_path else st.session_state.data["files"]
                        if parent_dict and parent_path[-1] in parent_dict:
                            if "folders" not in parent_dict[parent_path[-1]]:
                                parent_dict[parent_path[-1]]["folders"] = {}
                            parent_dict[parent_path[-1]]["folders"][new_folder_name.strip()] = {"folders": {}}
                    save_data(st.session_state.data)
                    st.rerun()

        # Browse folders and decks
        def render_sidebar_tree(folder_dict, path):
            for name, info in list(folder_dict.items()):
                current_path = path + [name]
                path_key = "_".join(current_path)

                with st.expander(f"📂 {name}", expanded=False):
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        if st.button("✏️", key=f"rename_folder_btn_{path_key}", use_container_width=True, help="Rename Folder"):
                            st.session_state[f"editing_rename_folder_{path_key}"] = not st.session_state.get(f"editing_rename_folder_{path_key}", False)
                            st.rerun()
                    with col2:
                        if st.button("📤", key=f"move_folder_btn_{path_key}", use_container_width=True, help="Move Folder"):
                            st.session_state[f"moving_folder_{path_key}"] = not st.session_state.get(f"moving_folder_{path_key}", False)
                            st.rerun()
                    with col3:
                        if st.button("📋", key=f"code_folder_btn_{path_key}", use_container_width=True, help="Get Folder Code"):
                            st.session_state[f"show_code_folder_{path_key}"] = not st.session_state.get(f"show_code_folder_{path_key}", False)
                            st.rerun()
                    with col4:
                        if st.button("🗑️", key=f"delete_folder_btn_{path_key}", use_container_width=True, help="Delete Folder"):
                            if st.session_state.get(f"confirm_delete_folder_{path_key}"):
                                delete_folder(name, path)
                                st.session_state[f"confirm_delete_folder_{path_key}"] = False
                                st.rerun()
                            else:
                                st.session_state[f"confirm_delete_folder_{path_key}"] = True
                                st.rerun()

                    if st.session_state.get(f"show_code_folder_{path_key}"):
                        st.code(export_folder_code(name, info))
                    
                    if st.session_state.get(f"editing_rename_folder_{path_key}"):
                        ren_col1, ren_col2 = st.columns([2, 1])
                        with ren_col1:
                            new_name = st.text_input("New folder name", value=name, key=f"rename_input_folder_{path_key}", label_visibility="collapsed")
                        with ren_col2:
                            if st.button("✓ Save", key=f"save_rename_folder_{path_key}", use_container_width=True):
                                if new_name.strip() and new_name != name:
                                    rename_folder(name, new_name, path)
                                st.session_state[f"editing_rename_folder_{path_key}"] = False
                                st.rerun()
                    
                    if st.session_state.get(f"moving_folder_{path_key}"):
                        target_folder = st.selectbox("Move to:", [p for p in list_all_folder_paths() if p != "Root (Unsorted)" and p != " / ".join(current_path)], key=f"move_target_folder_{path_key}")
                        move_col1, move_col2 = st.columns([1, 1])
                        with move_col1:
                            if st.button("✓ Move", key=f"confirm_move_folder_{path_key}", use_container_width=True):
                                move_folder(name, path, target_folder)
                                st.session_state[f"moving_folder_{path_key}"] = False
                                st.rerun()
                        with move_col2:
                            if st.button("✕ Cancel", key=f"cancel_move_folder_{path_key}", use_container_width=True):
                                st.session_state[f"moving_folder_{path_key}"] = False
                                st.rerun()

                    # Decks in this folder
                    decks = info.get("decks", {})
                    for deck_name in list(decks.keys()):
                        deck_key = f"{path_key}_{deck_name}"
                        deck_col1, deck_col2, deck_col3, deck_col4, deck_col5, deck_col6, deck_col7 = st.columns([2, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8])
                        with deck_col1:
                            if st.button(f"{deck_name}", key=f"open_deck_{deck_key}", use_container_width=True):
                                navigate_to("editor", deck_name, current_path)
                        with deck_col2:
                            if st.button("🔀", key=f"shuffle_{deck_key}", help="Shuffle Deck Cards", use_container_width=True):
                                shuffle_deck(deck_name, current_path)
                                st.success("Shuffled!")
                                st.rerun()
                        with deck_col3:
                            if st.button("📖", key=f"review_{deck_key}", help="Review (Due)", use_container_width=True):
                                st.session_state.review_cards = [c for c in decks[deck_name] if c.get("next_review", 0) <= time.time()]
                                st.session_state.review_idx = 0
                                st.session_state.review_mode = "study"
                                navigate_to("review", deck_name, current_path)
                        with deck_col4:
                            if st.button("🎯", key=f"practice_{deck_key}", help="Practice", use_container_width=True):
                                st.session_state.review_cards = decks[deck_name].copy()
                                random.shuffle(st.session_state.review_cards)
                                st.session_state.review_idx = 0
                                st.session_state.review_mode = "practice"
                                navigate_to("review", deck_name, current_path)
                        with deck_col5:
                            if st.button("✏️", key=f"rename_deck_{deck_key}", help="Rename", use_container_width=True):
                                st.session_state[f"editing_rename_deck_{deck_key}"] = not st.session_state.get(f"editing_rename_deck_{deck_key}", False)
                                st.rerun()
                        with deck_col6:
                            if st.button("📤", key=f"move_deck_{deck_key}", help="Move", use_container_width=True):
                                st.session_state[f"moving_deck_{deck_key}"] = not st.session_state.get(f"moving_deck_{deck_key}", False)
                                st.rerun()
                        with deck_col7:
                            if st.button("🗑️", key=f"delete_deck_{deck_key}", help="Delete", use_container_width=True):
                                if st.session_state.get(f"confirm_delete_deck_{deck_key}"):
                                    delete_deck(deck_name, current_path)
                                    st.session_state[f"confirm_delete_deck_{deck_key}"] = False
                                    st.rerun()
                                else:
                                    st.session_state[f"confirm_delete_deck_{deck_key}"] = True
                                    st.rerun()
                        
                        if st.session_state.get(f"editing_rename_deck_{deck_key}"):
                            ren_col1, ren_col2 = st.columns([2, 1])
                            with ren_col1:
                                new_deck_name = st.text_input("New name", value=deck_name, key=f"rename_input_deck_{deck_key}", label_visibility="collapsed")
                            with ren_col2:
                                if st.button("✓ Save", key=f"save_rename_deck_{deck_key}", use_container_width=True):
                                    if new_deck_name.strip() and new_deck_name != deck_name:
                                        rename_deck(deck_name, new_deck_name, current_path)
                                    st.session_state[f"editing_rename_deck_{deck_key}"] = False
                                    st.rerun()
                        
                        if st.session_state.get(f"moving_deck_{deck_key}"):
                            target_folder = st.selectbox("Move to:", list_all_folder_paths(), key=f"move_target_{deck_key}")
                            move_col1, move_col2 = st.columns([1, 1])
                            with move_col1:
                                if st.button("✓ Move", key=f"confirm_move_{deck_key}", use_container_width=True):
                                    move_deck(deck_name, current_path, target_folder)
                                    st.session_state[f"moving_deck_{deck_key}"] = False
                                    st.rerun()
                            with move_col2:
                                if st.button("✕ Cancel", key=f"cancel_move_{deck_key}", use_container_width=True):
                                    st.session_state[f"moving_deck_{deck_key}"] = False
                                    st.rerun()

                    # Nested folders
                    if info.get("folders"):
                        st.subheader("Subfolders")
                        render_sidebar_tree(info["folders"], current_path)

        render_sidebar_tree(st.session_state.data["files"], [])

        # Unsorted decks
        st.divider()
        st.subheader("Unsorted Decks")
        for deck_name in list(st.session_state.data["unsorted_decks"].keys()):
            unsorted_key = f"unsorted_{deck_name}"
            deck_col1, deck_col2, deck_col3, deck_col4, deck_col5, deck_col6, deck_col7 = st.columns([2, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8])
            with deck_col1:
                if st.button(f"{deck_name}", key=f"open_{unsorted_key}", use_container_width=True):
                    navigate_to("editor", deck_name, "unsorted")
            with deck_col2:
                if st.button("🔀", key=f"shuffle_{unsorted_key}", help="Shuffle Deck Cards", use_container_width=True):
                    shuffle_deck(deck_name, "unsorted")
                    st.success("Shuffled!")
                    st.rerun()
            with deck_col3:
                if st.button("📖", key=f"review_{unsorted_key}", help="Review (Due)", use_container_width=True):
                    st.session_state.review_cards = [c for c in st.session_state.data["unsorted_decks"][deck_name] if c.get("next_review", 0) <= time.time()]
                    st.session_state.review_idx = 0
                    st.session_state.review_mode = "study"
                    navigate_to("review", deck_name, "unsorted")
            with deck_col4:
                if st.button("🎯", key=f"practice_{unsorted_key}", help="Practice", use_container_width=True):
                    st.session_state.review_cards = st.session_state.data["unsorted_decks"][deck_name].copy()
                    random.shuffle(st.session_state.review_cards)
                    st.session_state.review_idx = 0
                    st.session_state.review_mode = "practice"
                    navigate_to("review", deck_name, "unsorted")
            with deck_col5:
                if st.button("✏️", key=f"rename_{unsorted_key}", help="Rename", use_container_width=True):
                    st.session_state[f"editing_rename_{unsorted_key}"] = not st.session_state.get(f"editing_rename_{unsorted_key}", False)
                    st.rerun()
            with deck_col6:
                if st.button("📤", key=f"move_{unsorted_key}", help="Move", use_container_width=True):
                    st.session_state[f"moving_{unsorted_key}"] = not st.session_state.get(f"moving_{unsorted_key}", False)
                    st.rerun()
            with deck_col7:
                if st.button("🗑️", key=f"delete_{unsorted_key}", help="Delete", use_container_width=True):
                    if st.session_state.get(f"confirm_delete_{unsorted_key}"):
                        delete_deck(deck_name, "unsorted")
                        st.session_state[f"confirm_delete_{unsorted_key}"] = False
                        st.rerun()
                    else:
                        st.session_state[f"confirm_delete_{unsorted_key}"] = True
                        st.rerun()
            
            if st.session_state.get(f"editing_rename_{unsorted_key}"):
                ren_col1, ren_col2 = st.columns([2, 1])
                with ren_col1:
                    new_deck_name = st.text_input("New name", value=deck_name, key=f"rename_input_{unsorted_key}", label_visibility="collapsed")
                with ren_col2:
                    if st.button("✓ Save", key=f"save_rename_{unsorted_key}", use_container_width=True):
                        if new_deck_name.strip() and new_deck_name != deck_name:
                            rename_deck(deck_name, new_deck_name, "unsorted")
                        st.session_state[f"editing_rename_{unsorted_key}"] = False
                        st.rerun()
            
            if st.session_state.get(f"moving_{unsorted_key}"):
                target_folder = st.selectbox("Move to:", list_all_folder_paths(), key=f"move_target_{unsorted_key}")
                move_col1, move_col2 = st.columns([1, 1])
                with move_col1:
                    if st.button("✓ Move", key=f"confirm_move_{unsorted_key}", use_container_width=True):
                        move_deck(deck_name, "unsorted", target_folder)
                        st.session_state[f"moving_{unsorted_key}"] = False
                        st.rerun()
                with move_col2:
                    if st.button("✕ Cancel", key=f"cancel_move_{unsorted_key}", use_container_width=True):
                        st.session_state[f"moving_{unsorted_key}"] = False
                        st.rerun()

    # Main Content
    col1, col2 = st.columns(2)
    with col1:
        with st.expander("➕ Create New Deck", expanded=False):
            new_deck_name = st.text_input("Deck Name", key="new_deck_name_input")
            target_folder = st.selectbox("Target Folder", list_all_folder_paths(), key="target_folder_select")
            if st.button("Create Deck", use_container_width=True):
                if new_deck_name.strip():
                    if target_folder == "Root (Unsorted)":
                        st.session_state.data["unsorted_decks"][new_deck_name.strip()] = []
                    else:
                        target_path = target_folder.split(" / ")
                        target_dict = get_folder_dict(target_path[:-1]) if len(target_path) > 1 else st.session_state.data["files"]
                        if target_path[-1] in target_dict:
                            if "decks" not in target_dict[target_path[-1]]:
                                target_dict[target_path[-1]]["decks"] = {}
                            target_dict[target_path[-1]]["decks"][new_deck_name.strip()] = []
                    save_data(st.session_state.data)
                    st.rerun()

    with col2:
        with st.expander("📥 Import Deck or Folder from Code / Link", expanded=False):
            import_code = st.text_area("Paste code or shareable link parameter here", key="import_code_input")
            target_import = st.selectbox("Import to", list_all_folder_paths(), key="import_target")
            if st.button("Import Item", use_container_width=True):
                if import_code.strip():
                    # Strip URL prefix if user pastes full share link
                    clean_input = import_code.strip()
                    if "?deck=" in clean_input:
                        clean_input = clean_input.split("?deck=")[-1]

                    target_path = "unsorted" if target_import == "Root (Unsorted)" else target_import.split(" / ")
                    success, message = import_any_code(clean_input, target_path)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

# Page: Editor
def render_editor():
    deck_name = st.session_state.active_deck
    location = st.session_state.deck_location

    col_back, col_title, col_shuffle = st.columns([1, 3, 1])
    with col_back:
        if st.button("← Back", use_container_width=True):
            navigate_to("home")
    with col_title:
        st.title(f"📝 Editing: {deck_name}")
    with col_shuffle:
        if st.button("🔀 Shuffle Deck", use_container_width=True):
            shuffle_deck(deck_name, location)
            st.success("Deck shuffled!")
            st.rerun()

    st.write(f"Location: {' / '.join(location) if location != 'unsorted' else 'Unsorted'}")

    cards = get_cards(deck_name, location)

    with st.expander("🔗 Share Deck (Link & Code)"):
        app_domain = st.text_input("App Base URL", value="https://your-app-name.streamlit.app", help="Replace with your deployed Streamlit URL")
        
        share_link = export_deck_link(deck_name, cards, base_url=app_domain)
        export_code = export_deck_code(deck_name, cards)

        st.subheader("🌐 Shareable Direct Link")
        st.code(share_link)
        st.caption("Anyone clicking this link will automatically import this deck when opening your app.")

        st.subheader("📋 Raw Export Code")
        st.code(export_code)

    with st.expander("➕ Add New Card", expanded=True):
        card_type = st.selectbox("Card Type", ["Standard", "Fill in Blank", "Multiple Choice"], key="add_card_type")
        
        question_placeholder = "Type your question here..."
        if card_type == "Fill in Blank":
            question_placeholder = "Example: The capital of France is Paris."
        
        new_question = st.text_area("Question / Prompt", placeholder=question_placeholder, key="add_question_input")
        uploaded_image = st.file_uploader("Attach Image (Optional)", type=["png", "jpg", "jpeg"], key="add_image_input")
        
        new_answer = ""
        new_options = []
        new_explanation = ""

        if card_type == "Standard":
            st.divider()
            new_answer = st.text_area("Answer", key="add_answer_input")

        elif card_type == "Multiple Choice":
            st.divider()
            options_raw = st.text_area("Options (One per line)", placeholder="Option 1\nOption 2\nOption 3", key="add_options_input")
            new_options = [o.strip() for o in options_raw.splitlines() if o.strip()]
            
            if new_options:
                new_answer = st.selectbox("✅ Correct Answer", new_options, key="add_mc_answer_input")
            else:
                new_answer = st.text_input("✅ Correct Answer (Exact text match)", key="add_mc_answer_input")
                
            new_explanation = st.text_area("💡 Explanation (Optional)", key="add_explanation_input")

        elif card_type == "Fill in Blank":
            st.divider()
            st.subheader("🖱️ Interactive Blank Creator")
            st.caption("Highlight text in the box below and click 'Turn Highlighted Text into Blank'.")
            
            components.html("""
            <div style="font-family: sans-serif; color: white;">
                <textarea id="blankTextarea" style="width: 100%; height: 90px; border-radius: 6px; padding: 8px; background: #1E293B; color: #FFF; border: 1px solid #475569;" placeholder="Paste text here, select word(s), and click below..."></textarea>
                <div style="margin-top: 6px; display: flex; gap: 8px;">
                    <button onclick="makeBlank()" style="background: #2563EB; color: white; border: none; padding: 8px 12px; border-radius: 6px; font-weight: bold; cursor: pointer;">✨ Turn Highlighted Text into Blank</button>
                    <button onclick="copyToClipboard()" style="background: #059669; color: white; border: none; padding: 8px 12px; border-radius: 6px; font-weight: bold; cursor: pointer;">📋 Copy Result</button>
                </div>
            </div>
            <script>
                let blankCounter = 1;
                function makeBlank() {
                    let textarea = document.getElementById("blankTextarea");
                    let start = textarea.selectionStart;
                    let end = textarea.selectionEnd;
                    let selected = textarea.value.substring(start, end);
                    if (selected.trim().length > 0) {
                        let replacement = "{" + blankCounter + ":" + selected + "}";
                        blankCounter++;
                        textarea.value = textarea.value.substring(0, start) + replacement + textarea.value.substring(end);
                    }
                }
                function copyToClipboard() {
                    let textarea = document.getElementById("blankTextarea");
                    textarea.select();
                    document.execCommand("copy");
                    alert("Copied to clipboard!");
                }
            </script>
            """, height=160)

        if st.button("💾 Add Card to Deck", type="primary", use_container_width=True, key="submit_add_card_btn"):
            if new_question.strip():
                if card_type == "Multiple Choice":
                    if not new_options:
                        st.error("Please add options for the multiple choice question!")
                        st.stop()
                    if new_answer.strip() not in new_options:
                        st.error("Correct answer must match one of the options!")
                        st.stop()

                image_path = None
                if uploaded_image is not None:
                    os.makedirs(UPLOADS_DIR, exist_ok=True)
                    image_path = os.path.join(UPLOADS_DIR, uploaded_image.name)
                    with open(image_path, "wb") as f:
                        f.write(uploaded_image.getbuffer())

                card_data = {
                    "type": card_type,
                    "question": new_question.strip(),
                    "image": image_path,
                    "interval": 1,
                    "ease_factor": 2.5,
                    "next_review": time.time()
                }

                if card_type == "Standard":
                    card_data["answer"] = new_answer.strip()
                elif card_type == "Multiple Choice":
                    card_data["options"] = new_options
                    card_data["answer"] = new_answer.strip()
                    card_data["explanation"] = new_explanation.strip()

                cards.append(card_data)
                save_data(st.session_state.data)
                st.success("Card added!")
                st.rerun()
            else:
                st.error("Please enter a question!")

    st.subheader(f"Existing Cards ({len(cards)})")
    for idx, c in enumerate(cards):
        with st.container(border=True):
            col_txt, col_edit, col_del = st.columns([4.5, 0.75, 0.75])
            with col_txt:
                st.markdown(f"**#{idx+1} [{c['type']}]** {c['question'][:80]}")
            with col_edit:
                if st.button("Edit", key=f"edit_btn_{idx}", use_container_width=True, help="✏️ Edit this card"):
                    st.session_state[f"editing_{idx}"] = not st.session_state.get(f"editing_{idx}", False)
                    st.rerun()
            with col_del:
                if st.button("Delete", key=f"del_btn_{idx}", use_container_width=True, help="🗑️ Delete this card"):
                    if st.session_state.get(f"confirm_delete_card_{idx}"):
                        cards.pop(idx)
                        save_data(st.session_state.data)
                        st.session_state[f"confirm_delete_card_{idx}"] = False
                        st.rerun()
                    else:
                        st.session_state[f"confirm_delete_card_{idx}"] = True
                        st.rerun()

            if st.session_state.get(f"editing_{idx}"):
                st.divider()
                st.write("**✏️ Edit Card**")
                
                if c["type"] == "Standard":
                    new_question_edit = st.text_area("Question", value=c.get("question", ""), key=f"edit_q_{idx}")
                    new_answer_edit = st.text_area("Answer", value=c.get("answer", ""), key=f"edit_a_{idx}")
                    if st.button("💾 Save Changes", type="primary", use_container_width=True, key=f"save_edit_{idx}"):
                        c["question"] = new_question_edit.strip()
                        c["answer"] = new_answer_edit.strip()
                        save_data(st.session_state.data)
                        st.session_state[f"editing_{idx}"] = False
                        st.rerun()

                elif c["type"] == "Multiple Choice":
                    current_options = [str(opt).strip() for opt in c.get("options", []) if str(opt).strip()]
                    current_ans = str(c.get("answer", "")).strip()

                    new_question_edit = st.text_area("Question", value=c.get("question", ""), key=f"edit_q_{idx}", height=100)
                    
                    st.subheader("📋 Manage Options")
                    updated_options = []
                    for opt_idx, opt in enumerate(current_options):
                        opt_col1, opt_col2 = st.columns([4, 1])
                        with opt_col1:
                            val = st.text_input(f"Option {opt_idx + 1}", value=opt, key=f"opt_val_{idx}_{opt_idx}")
                            if val.strip():
                                updated_options.append(val.strip())
                        with opt_col2:
                            if st.button("Delete", key=f"del_opt_{idx}_{opt_idx}", use_container_width=True, help="🗑️ Delete option"):
                                current_options.pop(opt_idx)
                                c["options"] = current_options
                                if current_ans not in current_options and current_options:
                                    c["answer"] = current_options[0]
                                save_data(st.session_state.data)
                                st.rerun()

                    st.write("**Add new option:**")
                    new_opt_col1, new_opt_col2 = st.columns([4, 1])
                    with new_opt_col1:
                        new_option = st.text_input("New option text", key=f"new_opt_{idx}")
                    with new_opt_col2:
                        if st.button("Add Option", key=f"add_opt_{idx}", use_container_width=True):
                            if new_option.strip() and new_option.strip() not in updated_options:
                                updated_options.append(new_option.strip())
                                c["options"] = updated_options
                                save_data(st.session_state.data)
                                st.rerun()

                    ans_idx = updated_options.index(current_ans) if current_ans in updated_options else 0
                    if updated_options:
                        new_answer_edit = st.selectbox("✅ Correct Answer", updated_options, index=ans_idx, key=f"edit_a_{idx}")
                    else:
                        new_answer_edit = ""
                        st.warning("⚠️ Please add at least one option.")

                    new_explanation_edit = st.text_area("💡 Explanation", value=c.get("explanation", ""), key=f"edit_exp_{idx}", height=80)

                    if st.button("💾 Save All Changes", type="primary", use_container_width=True, key=f"save_mc_edit_{idx}"):
                        if not updated_options:
                            st.error("Multiple choice questions require options!")
                        elif not new_answer_edit:
                            st.error("Please select a correct answer!")
                        else:
                            c["question"] = new_question_edit.strip()
                            c["options"] = updated_options
                            c["answer"] = new_answer_edit
                            c["explanation"] = new_explanation_edit.strip()
                            save_data(st.session_state.data)
                            st.session_state[f"editing_{idx}"] = False
                            st.rerun()

                else:  # Fill in Blank
                    new_question_edit = st.text_area(
                        "Question (Format: {1:answer1} and {2:answer2})", 
                        value=c.get("question", ""), 
                        key=f"edit_q_{idx}",
                        height=120,
                        help="Use {number:answer} for each blank."
                    )
                    
                    st.subheader("👁️ Live Preview")
                    blanks = re.findall(r"\{(\d+):([^\}]+)\}", new_question_edit)
                    if blanks:
                        preview_text = new_question_edit
                        for num, ans in blanks:
                            preview_text = preview_text.replace(f"{{{num}:{ans}}}", f"<span class='highlighted-answer'>{ans}</span>")
                        st.markdown("**With answers highlighted (study mode):**")
                        st.markdown(preview_text, unsafe_allow_html=True)
                        
                        preview_blanks = new_question_edit
                        for num, ans in blanks:
                            preview_blanks = preview_blanks.replace(f"{{{num}:{ans}}}", " `[ ____ ]` ")
                        st.markdown("**During practice (blanks to fill):**")
                        st.markdown(preview_blanks)
                        
                        st.info(f"✓ Found {len(blanks)} blank(s) to fill")
                    else:
                        st.warning("⚠️ No blanks detected. Use format {number:answer}")
                    
                    if st.button("💾 Save Changes", type="primary", use_container_width=True, key=f"save_fib_edit_{idx}"):
                        c["question"] = new_question_edit.strip()
                        save_data(st.session_state.data)
                        st.session_state[f"editing_{idx}"] = False
                        st.rerun()

# Page: Review
def render_review():
    cards = st.session_state.review_cards
    idx = st.session_state.review_idx

    if idx >= len(cards):
        st.balloons()
        st.success("🎉 You've finished all cards in this session!")
        if st.button("Return to Dashboard", type="primary"):
            navigate_to("home")
        return

    card = cards[idx]
    progress = (idx + 1) / len(cards)
    mode_label = "📖 Study Mode (SRS)" if st.session_state.review_mode == "study" else "🎯 Practice Mode"
    st.progress(progress, text=f"Card {idx + 1} of {len(cards)} — {mode_label} — Deck: {st.session_state.active_deck}")

    c_pad, c_exit = st.columns([3, 1])
    with c_pad:
        with st.popover("📝 Toggle Scratchpad"):
            stroke_color = st.color_picker("Color", "#FFFFFF")
            st_canvas(
                fill_color="rgba(255, 255, 255, 0)",
                stroke_width=3,
                stroke_color=stroke_color,
                background_color="#0f172a",
                height=250,
                drawing_mode="freedraw",
                key=f"canvas_{idx}"
            )
    with c_exit:
        if st.button("Exit Session", use_container_width=True):
            navigate_to("home")

    with st.container(border=True):
        card_type = card.get("type", "Standard").upper()
        st.caption(f"TYPE: **{card_type}**")            
        if card.get("image") and os.path.exists(card["image"]):
            st.image(card["image"], use_column_width=True)

        if card["type"] == "Standard":
            st.markdown(f"### {card['question']}")
            st.divider()

            if not st.session_state.show_ans:
                if st.button("👁️ Show Answer", use_container_width=True, type="primary"):
                    st.session_state.show_ans = True
                    st.rerun()
            else:
                st.markdown("#### **Answer:**")
                st.info(card.get("answer", ""))
                render_srs_controls(card)

        elif card["type"] == "Multiple Choice":
            st.markdown(f"### {card['question']}")
            
            opt_key = f"mc_opts_{idx}_{st.session_state.active_deck}"
            if opt_key not in st.session_state:
                opts = card.get("options", []).copy()
                random.shuffle(opts)
                st.session_state[opt_key] = opts
            
            shuffled_opts = st.session_state[opt_key]
            selected_opt = st.radio("Choose an answer:", shuffled_opts, key=f"mc_{idx}")

            if not st.session_state.show_srs:
                if st.button("Check Answer", use_container_width=True, type="primary"):
                    st.session_state[f"last_selected_{idx}"] = selected_opt
                    st.session_state.show_srs = True
                    st.rerun()
            else:
                correct = str(card.get("answer", "")).strip()
                user_selected = str(st.session_state.get(f"last_selected_{idx}", selected_opt)).strip()
                
                if user_selected == correct:
                    st.markdown(f"<div class='correct-answer-highlight'>✅ Correct: {correct}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='wrong-answer-highlight'>❌ Your Answer: {user_selected}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='correct-answer-highlight'>✅ Correct Answer: {correct}</div>", unsafe_allow_html=True)
                
                if card.get("explanation"):
                    st.info(f"**Explanation:** {card.get('explanation')}")
                
                render_srs_controls(card)

        else:  # Fill in Blank
            blanks = re.findall(r"\{(\d+):([^\}]+)\}", card["question"])
            
            if not st.session_state.reveal_blanks:
                display_text = card["question"]
                for num, ans in blanks:
                    display_text = display_text.replace(f"{{{num}:{ans}}}", " `[ ____ ]` ")
                st.markdown(f"### {display_text}")
                
                user_inputs = {}
                for num, ans in blanks:
                    user_inputs[num] = (st.text_input(f"Blank #{num}:", key=f"blank_{idx}_{num}"), ans)

                if not st.session_state.show_srs:
                    if st.button("Check Answer", use_container_width=True, type="primary"):
                        st.session_state[f"last_fib_inputs_{idx}"] = user_inputs
                        st.session_state.reveal_blanks = True
                        st.session_state.show_srs = True
                        st.rerun()
            else:
                saved_inputs = st.session_state.get(f"last_fib_inputs_{idx}", {})
                all_correct = True
                
                for num, (val, target) in saved_inputs.items():
                    user_val = val.strip()
                    target_val = target.strip()
                    if user_val.lower() != target_val.lower():
                        all_correct = False
                        st.markdown(f"<div class='wrong-answer-highlight'>❌ Blank #{num} Incorrect: '{user_val}' (Correct: '{target_val}')</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='correct-answer-highlight'>✅ Blank #{num} Correct: '{target_val}'</div>", unsafe_allow_html=True)
                
                if all_correct and saved_inputs:
                    st.success("🎉 All Blanks Correct!")
                
                display_text = card["question"]
                for num, ans in blanks:
                    display_text = display_text.replace(f"{{{num}:{ans}}}", f"<span class='highlighted-answer'>{ans}</span>")
                st.markdown(f"### {display_text}", unsafe_allow_html=True)
                
                render_srs_controls(card)

def render_srs_controls(card):
    st.divider()
    if st.session_state.review_mode == "study":
        st.write("**How easily did you recall this card?**")
    else:
        st.write("**Next card**")
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("❌ Missed" if st.session_state.review_mode == "study" else "❌ Again", key="srs_1", use_container_width=True):
            apply_srs(card, 1)
    with c2:
        if st.button("⚡ Hard", key="srs_3", use_container_width=True):
            apply_srs(card, 3)
    with c3:
        if st.button("👍 Good", key="srs_4", use_container_width=True):
            apply_srs(card, 4)
    with c4:
        if st.button("✅ Easy" if st.session_state.review_mode == "study" else "✅ Got it", key="srs_5", use_container_width=True):
            apply_srs(card, 5)

def apply_srs(card, quality):
    if st.session_state.review_mode == "study":
        ease = card.get("ease_factor", 2.5)
        interval = card.get("interval", 1)

        if quality < 3:
            interval = 1
            st.session_state.review_cards.append(card)
        else:
            interval = max(1, int(interval * ease))
            ease = max(1.3, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))

        card["ease_factor"] = ease
        card["interval"] = interval
        card["next_review"] = time.time() + (interval * 86400)

        save_data(st.session_state.data)
    
    st.session_state.show_ans = False
    st.session_state.show_srs = False
    st.session_state.reveal_blanks = False
    st.session_state.review_idx += 1
    st.rerun()

# Main App Router
if st.session_state.current_page == "home":
    render_home()
elif st.session_state.current_page == "editor":
    render_editor()
elif st.session_state.current_page == "review":
    render_review()