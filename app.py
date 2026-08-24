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
    /* Standardize Font Stack across Streamlit UI */
    html, body, [class*="css"], textarea, button, input {
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
    }
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

def get_all_folder_cards(folder_data):
    """Get all cards from a folder (including subfolders)"""
    all_cards = []
    
    # Get cards from main folder decks
    for deck_name, cards in folder_data.get("decks", {}).items():
        for card in cards:
            card_with_source = card.copy()
            card_with_source["_source"] = f"📚 {deck_name}"
            all_cards.append(card_with_source)
    
    # Get cards from subfolders
    def get_subfolder_cards(subfolder_data, prefix=""):
        cards = []
        for deck_name, deck_cards in subfolder_data.get("decks", {}).items():
            for card in deck_cards:
                card_with_source = card.copy()
                card_with_source["_source"] = f"📁 {prefix}{deck_name}"
                cards.append(card_with_source)
        
        for subfolder_name, subdata in subfolder_data.get("folders", {}).items():
            cards.extend(get_subfolder_cards(subdata, f"{prefix}{subfolder_name}/"))
        
        return cards
    
    for subfolder_name, subfolder_data in folder_data.get("folders", {}).items():
        all_cards.extend(get_subfolder_cards(subfolder_data, f"{subfolder_name}/"))
    
    return all_cards

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
    try:
        cards = []
        if source_path == "unsorted":
            if deck_name in st.session_state.data["unsorted_decks"]:
                cards = st.session_state.data["unsorted_decks"].pop(deck_name)
        else:
            folder_dict = get_folder_dict(source_path[:-1]) if len(source_path) > 1 else st.session_state.data["files"]
            if folder_dict and source_path[-1] in folder_dict:
                decks = folder_dict[source_path[-1]].get("decks", {})
                if deck_name in decks:
                    cards = decks.pop(deck_name)
        
        if not cards:
            st.error(f"Could not find deck '{deck_name}' to move")
            return False
        
        if target_path_str == "Root (Unsorted)":
            st.session_state.data["unsorted_decks"][deck_name] = cards
        else:
            target_path = target_path_str.split(" / ")
            target_dict = get_folder_dict(target_path[:-1]) if len(target_path) > 1 else st.session_state.data["files"]
            if target_dict and target_path[-1] in target_dict:
                if "decks" not in target_dict[target_path[-1]]:
                    target_dict[target_path[-1]]["decks"] = {}
                target_dict[target_path[-1]]["decks"][deck_name] = cards
            else:
                st.error(f"Target folder '{target_path_str}' not found")
                return False
        
        save_data(st.session_state.data)
        return True
    except Exception as e:
        st.error(f"Error moving deck: {str(e)}")
        return False

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

# Compact Encoding Functions
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

def export_folder_code(folder_name, folder_data):
    """Export a folder with all its decks and subfolders"""
    minified_folder = {"folders": {}, "decks": {}}
    
    # Minify subfolders
    for subfolder_name, subfolder_data in folder_data.get("folders", {}).items():
        minified_folder["folders"][subfolder_name] = subfolder_data
    
    # Minify decks
    for deck_name, cards in folder_data.get("decks", {}).items():
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
        minified_folder["decks"][deck_name] = minified_cards
    
    payload = {
        "type": "folder",
        "n": folder_name,
        "data": minified_folder
    }
    
    raw_json = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode("utf-8")
    compressed = zlib.compress(raw_json, level=9)
    return base64.urlsafe_b64encode(compressed).decode("utf-8")

def import_any_code(encoded_code, target_path):
    try:
        clean_code = encoded_code.strip().encode("utf-8")
        
        decoded_bytes = None
        try:
            decoded_bytes = base64.urlsafe_b64decode(clean_code)
        except Exception:
            try:
                decoded_bytes = base64.b85decode(clean_code)
            except Exception:
                try:
                    decoded_bytes = base64.b64decode(clean_code)
                except Exception:
                    return False, "Invalid code format. Please check and try again."

        try:
            decompressed = zlib.decompress(decoded_bytes)
            payload = json.loads(decompressed.decode("utf-8"))
        except Exception as e:
            return False, f"Failed to decompress code: {str(e)}"

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
    if deck_name:
        st.session_state.active_deck = deck_name
    if location:
        st.session_state.deck_location = location

# Page: Home
def render_home():
    st.title("📚 HKDSE Flashcard Hub")
    
    check_and_handle_url_import()
    
    if "show_create_deck" not in st.session_state:
        st.session_state.show_create_deck = False
    if "show_create_folder" not in st.session_state:
        st.session_state.show_create_folder = False
    if "show_import_deck" not in st.session_state:
        st.session_state.show_import_deck = False
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        if st.button("➕ Create Deck", use_container_width=True, key="btn_create_deck"):
            st.session_state.show_create_deck = not st.session_state.show_create_deck
        
        if st.session_state.show_create_deck:
            with st.container(border=True):
                new_deck_name = st.text_input("Deck name:", key="deck_name_input")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Create", use_container_width=True, key="btn_confirm_deck"):
                        if new_deck_name.strip():
                            st.session_state.data["unsorted_decks"][new_deck_name.strip()] = []
                            save_data(st.session_state.data)
                            st.success("Deck created!")
                            st.session_state.show_create_deck = False
                            st.rerun()
                        else:
                            st.error("Please enter a deck name")
                with col_b:
                    if st.button("Cancel", use_container_width=True, key="btn_cancel_deck"):
                        st.session_state.show_create_deck = False
                        st.rerun()
    
    with col2:
        if st.button("📁 Create Folder", use_container_width=True, key="btn_create_folder"):
            st.session_state.show_create_folder = not st.session_state.show_create_folder
        
        if st.session_state.show_create_folder:
            with st.container(border=True):
                new_folder_name = st.text_input("Folder name:", key="folder_name_input")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Create", use_container_width=True, key="btn_confirm_folder"):
                        if new_folder_name.strip():
                            st.session_state.data["files"][new_folder_name.strip()] = {"folders": {}, "decks": {}}
                            save_data(st.session_state.data)
                            st.success("Folder created!")
                            st.session_state.show_create_folder = False
                            st.rerun()
                        else:
                            st.error("Please enter a folder name")
                with col_b:
                    if st.button("Cancel", use_container_width=True, key="btn_cancel_folder"):
                        st.session_state.show_create_folder = False
                        st.rerun()
    
    with col3:
        if st.button("📤 Import", use_container_width=True, key="btn_import_deck"):
            st.session_state.show_import_deck = not st.session_state.show_import_deck
        
        if st.session_state.show_import_deck:
            with st.container(border=True):
                import_code = st.text_input("Paste code:", key="import_code_input")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Import", use_container_width=True, key="btn_confirm_import"):
                        if import_code.strip():
                            success, message = import_any_code(import_code.strip(), "unsorted")
                            if success:
                                st.success(message)
                                st.session_state.show_import_deck = False
                                st.rerun()
                            else:
                                st.error(message)
                        else:
                            st.error("Please paste an import code")
                with col_b:
                    if st.button("Cancel", use_container_width=True, key="btn_cancel_import"):
                        st.session_state.show_import_deck = False
                        st.rerun()
    
    # File Export/Import Section
    with col1:
        if st.button("💾 Export File", use_container_width=True, key="btn_export_file"):
            json_str = json.dumps(st.session_state.data, indent=2)
            st.download_button(
                label="📥 Download flashcard_data.json",
                data=json_str,
                file_name="flashcard_data.json",
                mime="application/json",
                key="download_file_btn"
            )
    
    with col2:
        if st.button("📂 Import File", use_container_width=True, key="btn_import_file"):
            st.session_state.show_import_file = not st.session_state.get("show_import_file", False)
        
        if st.session_state.get("show_import_file"):
            with st.container(border=True):
                uploaded_file = st.file_uploader("Choose a flashcard_data.json file", type=["json"], key="file_upload_input")
                if uploaded_file:
                    try:
                        imported_data = json.load(uploaded_file)
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.button("Import & Merge", use_container_width=True, key="btn_confirm_file_import"):
                                # Merge the imported data
                                for folder_name, folder_data in imported_data.get("files", {}).items():
                                    if folder_name not in st.session_state.data["files"]:
                                        st.session_state.data["files"][folder_name] = folder_data
                                    else:
                                        # Merge folders and decks
                                        for subfolder_name, subfolder_data in folder_data.get("folders", {}).items():
                                            st.session_state.data["files"][folder_name]["folders"][subfolder_name] = subfolder_data
                                        for deck_name, deck_cards in folder_data.get("decks", {}).items():
                                            st.session_state.data["files"][folder_name]["decks"][deck_name] = deck_cards
                                
                                for deck_name, deck_cards in imported_data.get("unsorted_decks", {}).items():
                                    st.session_state.data["unsorted_decks"][deck_name] = deck_cards
                                
                                save_data(st.session_state.data)
                                st.success("✅ File imported and merged successfully!")
                                st.session_state.show_import_file = False
                                st.rerun()
                        with col_b:
                            if st.button("Cancel", use_container_width=True, key="btn_cancel_file_import"):
                                st.session_state.show_import_file = False
                                st.rerun()
                    except Exception as e:
                        st.error(f"Error reading file: {str(e)}")
    
    st.divider()
    
    if st.session_state.data.get("unsorted_decks"):
        st.subheader("📇 Unsorted Decks")
        for deck_name, cards in st.session_state.data["unsorted_decks"].items():
            with st.container(border=True):
                col_deck, col_study, col_edit, col_export, col_more = st.columns([2, 1.2, 1, 1.2, 1])
                with col_deck:
                    st.write(f"**{deck_name}** ({len(cards)} cards)")
                with col_study:
                    if st.button("Study", key=f"study_{deck_name}_unsorted", use_container_width=True):
                        st.session_state.review_cards = [c.copy() for c in cards]
                        st.session_state.review_idx = 0
                        st.session_state.show_ans = False
                        st.session_state.show_srs = False
                        st.session_state.review_mode = "study"
                        navigate_to("review", deck_name, "unsorted")
                        st.rerun()
                with col_edit:
                    if st.button("Edit", key=f"edit_{deck_name}_unsorted", use_container_width=True):
                        navigate_to("editor", deck_name, "unsorted")
                        st.rerun()
                with col_export:
                    if st.button("Export", key=f"exp_{deck_name}_unsorted", use_container_width=True):
                        export_code = export_deck_code(deck_name, cards)
                        st.code(export_code, language="text")
                with col_more:
                    if st.button("⋮", key=f"more_{deck_name}_unsorted"):
                        st.session_state[f"show_options_{deck_name}_unsorted"] = not st.session_state.get(f"show_options_{deck_name}_unsorted", False)
                        st.rerun()
                
                if st.session_state.get(f"show_options_{deck_name}_unsorted"):
                    opt_col1, opt_col2, opt_col3, opt_col4 = st.columns(4)
                    with opt_col1:
                        new_name = st.text_input("New name:", key=f"rename_{deck_name}_unsorted")
                        if st.button("Rename", key=f"rename_btn_{deck_name}_unsorted", use_container_width=True):
                            rename_deck(deck_name, new_name, "unsorted")
                            st.session_state[f"show_options_{deck_name}_unsorted"] = False
                            st.rerun()
                    with opt_col2:
                        if st.button("Shuffle", key=f"shuffle_{deck_name}_unsorted", use_container_width=True):
                            shuffle_deck(deck_name, "unsorted")
                            st.session_state[f"show_options_{deck_name}_unsorted"] = False
                            st.rerun()
                    with opt_col3:
                        if st.button("Move", key=f"move_unsorted_{deck_name}", use_container_width=True):
                            st.session_state[f"moving_{deck_name}_unsorted"] = not st.session_state.get(f"moving_{deck_name}_unsorted", False)
                            st.rerun()
                    with opt_col4:
                        if st.button("Delete", key=f"delete_{deck_name}_unsorted", use_container_width=True):
                            delete_deck(deck_name, "unsorted")
                            st.session_state[f"show_options_{deck_name}_unsorted"] = False
                            st.rerun()
                    
                    if st.session_state.get(f"moving_{deck_name}_unsorted"):
                        st.divider()
                        with st.container(border=True):
                            st.write("**Move deck to folder:**")
                            all_paths = list_all_folder_paths()
                            folder_options = [p for p in all_paths if p != "Root (Unsorted)"]
                            
                            if folder_options:
                                target = st.selectbox("Select destination:", folder_options, key=f"move_target_unsorted_{deck_name}")
                                move_col1, move_col2 = st.columns(2)
                                with move_col1:
                                    if st.button("✓ Confirm Move", key=f"confirm_move_unsorted_{deck_name}", use_container_width=True):
                                        if move_deck(deck_name, "unsorted", target):
                                            st.success(f"✓ Moved '{deck_name}' to '{target}'")
                                            st.session_state[f"moving_{deck_name}_unsorted"] = False
                                            st.session_state[f"show_options_{deck_name}_unsorted"] = False
                                            st.rerun()
                                with move_col2:
                                    if st.button("✕ Cancel", key=f"cancel_move_unsorted_{deck_name}", use_container_width=True):
                                        st.session_state[f"moving_{deck_name}_unsorted"] = False
                                        st.rerun()
                            else:
                                st.info("📁 Create a folder first to move decks")
    
    def display_folder_tree(folder_dict, path=[]):
        for folder_name, folder_info in folder_dict.items():
            with st.expander(f"📁 {folder_name}", expanded=False):
                current_path = path + [folder_name]
                path_str = '/'.join(current_path)
                
                # Folder-level buttons
                st.write("**Folder Actions:**")
                fcol1, fcol2, fcol3, fcol4 = st.columns(4)
                
                with fcol1:
                    if st.button("📚 Review All", key=f"review_all_{path_str}", use_container_width=True):
                        all_cards = get_all_folder_cards(folder_info)
                        if all_cards:
                            st.session_state.review_cards = all_cards
                            st.session_state.review_idx = 0
                            st.session_state.show_ans = False
                            st.session_state.show_srs = False
                            st.session_state.review_mode = "study"
                            navigate_to("review", f"All in {folder_name}", current_path)
                            st.rerun()
                        else:
                            st.warning("No cards in this folder")
                
                with fcol2:
                    if st.button("📤 Export Folder", key=f"export_folder_{path_str}", use_container_width=True):
                        code = export_folder_code(folder_name, folder_info)
                        st.code(code, language="text")
                
                with fcol3:
                    if st.button("📥 Import Folder", key=f"import_folder_btn_{path_str}", use_container_width=True):
                        st.session_state[f"show_import_folder_{path_str}"] = not st.session_state.get(f"show_import_folder_{path_str}", False)
                        st.rerun()
                
                path_str = '/'.join(current_path)
                if st.session_state.get(f"show_import_folder_{path_str}"):
                    with st.container(border=True):
                        import_code = st.text_input(f"Enter folder code to import:", key=f"import_folder_code_{path_str}")
                        icol1, icol2 = st.columns(2)
                        with icol1:
                            if st.button("Import", use_container_width=True, key=f"confirm_import_folder_{path_str}"):
                                if import_code.strip():
                                    # Use import_any_code which supports both new (8-char) and old (base64) formats
                                    success, message = import_any_code(import_code.strip(), current_path)
                                    if success:
                                        st.success(message)
                                        st.session_state[f"show_import_folder_{path_str}"] = False
                                        st.rerun()
                                    else:
                                        st.error(message)
                                else:
                                    st.error("Enter a code")
                        with icol2:
                            if st.button("Cancel", use_container_width=True, key=f"cancel_import_folder_{path_str}"):
                                st.session_state[f"show_import_folder_{path_str}"] = False
                                st.rerun()
                
                st.divider()
                
                if "decks" in folder_info and folder_info["decks"]:
                    st.write("**Decks:**")
                    for deck_name, cards in folder_info["decks"].items():
                        col_deck, col_study, col_edit, col_export, col_more = st.columns([2, 1.2, 1, 1.2, 1])
                        with col_deck:
                            st.write(f"• {deck_name} ({len(cards)} cards)")
                        with col_study:
                            if st.button("Study", key=f"study_{deck_name}_{'/'.join(current_path)}", use_container_width=True):
                                st.session_state.review_cards = [c.copy() for c in cards]
                                st.session_state.review_idx = 0
                                st.session_state.show_ans = False
                                st.session_state.show_srs = False
                                st.session_state.review_mode = "study"
                                navigate_to("review", deck_name, current_path)
                                st.rerun()
                        with col_edit:
                            if st.button("Edit", key=f"edit_{deck_name}_{'/'.join(current_path)}", use_container_width=True):
                                navigate_to("editor", deck_name, current_path)
                                st.rerun()
                        with col_export:
                            if st.button("Export", key=f"exp_{deck_name}_{'/'.join(current_path)}", use_container_width=True):
                                export_code = export_deck_code(deck_name, cards)
                                st.code(export_code, language="text")
                        with col_more:
                            if st.button("⋮", key=f"more_{deck_name}_{'/'.join(current_path)}"):
                                st.session_state[f"show_options_{deck_name}_{'/'.join(current_path)}"] = not st.session_state.get(f"show_options_{deck_name}_{'/'.join(current_path)}", False)
                                st.rerun()
                        
                        if st.session_state.get(f"show_options_{deck_name}_{'/'.join(current_path)}"):
                            opt_col1, opt_col2, opt_col3, opt_col4 = st.columns(4)
                            with opt_col1:
                                new_name = st.text_input("New name:", key=f"rename_{deck_name}_{'/'.join(current_path)}")
                                if st.button("Rename", key=f"rename_btn_{deck_name}_{'/'.join(current_path)}", use_container_width=True):
                                    rename_deck(deck_name, new_name, current_path)
                                    st.session_state[f"show_options_{deck_name}_{'/'.join(current_path)}"] = False
                                    st.rerun()
                            with opt_col2:
                                if st.button("Shuffle", key=f"shuffle_{deck_name}_{'/'.join(current_path)}", use_container_width=True):
                                    shuffle_deck(deck_name, current_path)
                                    st.session_state[f"show_options_{deck_name}_{'/'.join(current_path)}"] = False
                                    st.rerun()
                            with opt_col3:
                                if st.button("Move", key=f"move_folder_{deck_name}_{'/'.join(current_path)}", use_container_width=True):
                                    st.session_state[f"moving_{deck_name}_{'/'.join(current_path)}"] = not st.session_state.get(f"moving_{deck_name}_{'/'.join(current_path)}", False)
                                    st.rerun()
                            with opt_col4:
                                if st.button("Delete", key=f"delete_{deck_name}_{'/'.join(current_path)}", use_container_width=True):
                                    delete_deck(deck_name, current_path)
                                    st.session_state[f"show_options_{deck_name}_{'/'.join(current_path)}"] = False
                                    st.rerun()
                            
                            if st.session_state.get(f"moving_{deck_name}_{'/'.join(current_path)}"):
                                st.divider()
                                with st.container(border=True):
                                    st.write("**Move deck to folder:**")
                                    all_paths = list_all_folder_paths()
                                    
                                    if all_paths:
                                        target = st.selectbox("Select destination:", all_paths, key=f"move_target_folder_{deck_name}_{'/'.join(current_path)}")
                                        move_col1, move_col2 = st.columns(2)
                                        with move_col1:
                                            if st.button("✓ Confirm Move", key=f"confirm_move_folder_{deck_name}_{'/'.join(current_path)}", use_container_width=True):
                                                if move_deck(deck_name, current_path, target):
                                                    st.success(f"✓ Moved '{deck_name}' to '{target}'")
                                                    st.session_state[f"moving_{deck_name}_{'/'.join(current_path)}"] = False
                                                    st.session_state[f"show_options_{deck_name}_{'/'.join(current_path)}"] = False
                                                    st.rerun()
                                        with move_col2:
                                            if st.button("✕ Cancel", key=f"cancel_move_folder_{deck_name}_{'/'.join(current_path)}", use_container_width=True):
                                                st.session_state[f"moving_{deck_name}_{'/'.join(current_path)}"] = False
                                                st.rerun()
                                    else:
                                        st.info("No destinations available")
                
                if "folders" in folder_info and folder_info["folders"]:
                    display_folder_tree(folder_info["folders"], current_path)
                
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    path_str = '/'.join(current_path)
                    if st.button("Move Folder", key=f"move_folder_btn_{path_str}", use_container_width=True):
                        st.session_state[f"moving_folder_{path_str}"] = not st.session_state.get(f"moving_folder_{path_str}", False)
                        st.rerun()
                    
                    if st.session_state.get(f"moving_folder_{path_str}"):
                        st.divider()
                        with st.container(border=True):
                            st.write("**Move folder to new location:**")
                            all_paths = list_all_folder_paths()
                            target = st.selectbox("Select destination:", all_paths, key=f"move_target_{path_str}")
                            move_col1, move_col2 = st.columns(2)
                            with move_col1:
                                if st.button("✓ Confirm", key=f"confirm_move_{path_str}", use_container_width=True):
                                    if target:
                                        move_folder(folder_name, path, target)
                                        st.success(f"✓ Folder moved!")
                                        st.session_state[f"moving_folder_{path_str}"] = False
                                        st.rerun()
                            with move_col2:
                                if st.button("✕ Cancel", key=f"cancel_move_{path_str}", use_container_width=True):
                                    st.session_state[f"moving_folder_{path_str}"] = False
                                    st.rerun()
                
                with col_f2:
                    if st.button("Delete Folder", key=f"del_folder_{path_str}", use_container_width=True):
                        delete_folder(folder_name, path)
                        st.success("Folder deleted!")
                        st.rerun()
    
    if st.session_state.data.get("files"):
        st.subheader("📂 Folder Structure")
        display_folder_tree(st.session_state.data["files"])

# Page: Editor
def render_editor():
    if not st.session_state.active_deck:
        st.error("No deck selected!")
        return
    
    deck_name = st.session_state.active_deck
    location = st.session_state.deck_location
    cards = get_cards(deck_name, location)
    
    st.title(f"✏️ Edit: {deck_name}")
    
    if st.button("← Back to Home"):
        navigate_to("home")
        st.rerun()
    
    st.divider()
    
    with st.expander("➕ Add New Card", expanded=True):
        card_type = st.radio("Card Type:", ["Standard", "Multiple Choice", "Fill in Blank"], horizontal=True, key="card_type_selector")
        
        new_question = ""
        new_answer = ""
        new_options = []
        new_explanation = ""
        uploaded_image = None

        if card_type == "Standard":
            new_question = st.text_area("Question", height=100, key="new_q")
            new_answer = st.text_area("Answer", height=100, key="new_a")
            uploaded_image = st.file_uploader("Upload image (optional)", type=["jpg", "jpeg", "png"], key="img_std")
        
        elif card_type == "Multiple Choice":
            new_question = st.text_area("Question", height=100, key="new_q_mc")
            st.subheader("📋 Multiple Choice Options")
            num_options = st.number_input("Number of options:", min_value=2, max_value=10, value=4)
            new_options = []
            for i in range(num_options):
                opt = st.text_input(f"Option {i+1}:", key=f"opt_{i}")
                if opt.strip():
                    new_options.append(opt.strip())
            
            new_answer = st.selectbox("✅ Correct Answer:", new_options if new_options else ["No options yet"], key="mc_ans")
            new_explanation = st.text_area("💡 Explanation (optional)", height=80, key="mc_exp")
            uploaded_image = st.file_uploader("Upload image (optional)", type=["jpg", "jpeg", "png"], key="img_mc")
        
        else:  # Fill in Blank
            fib_mode = st.radio("Mode:", ["Create Blanks {1:answer}", "Simple Answer"], horizontal=True, key="fib_mode_selector")
            uploaded_image = st.file_uploader("Upload image (optional)", type=["jpg", "jpeg", "png"], key="img_fib")
            
            if "fib_new_state" not in st.session_state:
                st.session_state.fib_new_state = ""
            
            if fib_mode == "Simple Answer":
                new_question = st.text_area("Question", height=100, key="fib_question_simple", placeholder="Enter your question")
                new_answer = st.text_area("Answer", height=100, key="fib_answer_simple", placeholder="Enter the answer")
            else:
                st.write("**Highlight text to turn into a blank:**")
                
                # Single Window Highlight Component with Matched Typography and Increased Frame Height
                highlight_component = f"""
                <div style="font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                    <textarea id="fib_input" style="width: 100%; height: 140px; padding: 10px; border-radius: 8px; border: 1px solid #ccc; font-size: 15px; font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;" placeholder="Type your full sentence here, then highlight a word and click the button below...">{st.session_state.fib_new_state}</textarea>
                    <br><br>
                    <button id="blank_btn" style="background-color: #ff4b4b; color: white; border: none; padding: 6px 12px; font-size: 13px; font-weight: 600; border-radius: 6px; cursor: pointer; font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                        ✨ Turn Highlighted Text into Blank
                    </button>
                </div>

                <script>
                    const textarea = document.getElementById('fib_input');
                    const btn = document.getElementById('blank_btn');

                    btn.addEventListener('click', function() {{
                        const start = textarea.selectionStart;
                        const end = textarea.selectionEnd;
                        const selectedText = textarea.value.substring(start, end);

                        if (selectedText.trim() !== '') {{
                            const currentText = textarea.value;
                            const matches = currentText.match(/\{{\d+:/g) || [];
                            const nextNum = matches.length + 1;
                            
                            const before = currentText.substring(0, start);
                            const after = currentText.substring(end);
                            
                            textarea.value = before + '{{' + nextNum + ':' + selectedText + '}}' + after;
                            
                            // Dispatch input event so Streamlit registers changes
                            textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }} else {{
                            alert('Please highlight a word or phrase inside the text window first!');
                        }}
                    }});
                </script>
                """
                
                # Render the single window editor with expanded container height (260px)
                components.html(highlight_component, height=260)
                
                # Hidden text area syncs state back to Streamlit
                col_raw, col_undo = st.columns([4, 1])
                with col_raw:
                    new_question = st.text_area("Raw Output / Verification", value=st.session_state.fib_new_state, key="fib_new_question_area", height=100)
                    st.session_state.fib_new_state = new_question
                with col_undo:
                    st.write("")  # spacing
                    if st.button("↶ Undo", use_container_width=True, key="undo_blank_btn"):
                        if "fib_history" in st.session_state and len(st.session_state.fib_history) > 1:
                            st.session_state.fib_history.pop()  # Remove current state
                            st.session_state.fib_new_state = st.session_state.fib_history[-1]
                            st.rerun()
                        else:
                            st.warning("Nothing to undo")
                
                # Track history for undo
                if "fib_history" not in st.session_state:
                    st.session_state.fib_history = [st.session_state.fib_new_state]
                elif st.session_state.fib_new_state != st.session_state.fib_history[-1]:
                    st.session_state.fib_history.append(st.session_state.fib_new_state)

                st.divider()
                st.write("**Preview**")
                blanks = re.findall(r"\{(\d+):([^\}]+)\}", new_question)
                
                if blanks:
                    preview_study = new_question
                    for num, ans in blanks:
                        preview_study = preview_study.replace(f"{{{num}:{ans}}}", f"**{ans}**")
                    st.markdown(preview_study)
                    st.caption("📖 Study mode preview")
                    
                    st.divider()
                    
                    preview_practice = new_question
                    for num, ans in blanks:
                        preview_practice = preview_practice.replace(f"{{{num}:{ans}}}", "___")
                    st.markdown(preview_practice)
                    st.caption("🎯 Practice mode preview")
                    
                    st.success(f"✓ {len(blanks)} blank(s) detected!")
                else:
                    st.info("No blanks created yet. Highlight text above and click the button.")

        if st.button("💾 Add Card to Deck", type="primary", use_container_width=True, key="submit_add_card_btn"):
            final_question = st.session_state.get("fib_new_question_area", new_question) if card_type == "Fill in Blank" else new_question
            
            if final_question.strip():
                if card_type == "Multiple Choice":
                    if not new_options:
                        st.error("Please add options for the multiple choice question!")
                        st.stop()
                    if new_answer.strip() not in new_options:
                        st.error("Correct answer must match one of the options!")
                        st.stop()

                if card_type == "Fill in Blank" and fib_mode == "Create Blanks {1:answer}":
                    blanks_check = re.findall(r"\{(\d+):([^\}]+)\}", final_question)
                    if not blanks_check:
                        st.error("No blanks found! Highlight text to embed blanks first.")
                        st.stop()

                image_path = None
                if uploaded_image is not None:
                    os.makedirs(UPLOADS_DIR, exist_ok=True)
                    image_path = os.path.join(UPLOADS_DIR, uploaded_image.name)
                    with open(image_path, "wb") as f:
                        f.write(uploaded_image.getbuffer())

                card_data = {
                    "type": card_type,
                    "question": final_question.strip(),
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
                elif card_type == "Fill in Blank":
                    if fib_mode == "Simple Answer":
                        card_data["answer"] = new_answer.strip()
                    else:
                        card_data["answer"] = ""
                        st.session_state.fib_new_state = ""

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
                    if f"mc_edit_state_{idx}" not in st.session_state:
                        st.session_state[f"mc_edit_state_{idx}"] = {
                            "options": [str(opt).strip() for opt in c.get("options", []) if str(opt).strip()],
                            "answer": str(c.get("answer", "")).strip()
                        }
                    
                    edit_state = st.session_state[f"mc_edit_state_{idx}"]
                    new_question_edit = st.text_area("Question", value=c.get("question", ""), key=f"edit_q_{idx}", height=100)
                    
                    st.subheader("📋 Manage Options")
                    options_to_delete = []
                    for opt_idx, opt in enumerate(edit_state["options"]):
                        opt_col1, opt_col2 = st.columns([4, 1])
                        with opt_col1:
                            new_val = st.text_input(f"Option {opt_idx + 1}", value=opt, key=f"opt_edit_{idx}_{opt_idx}")
                            if new_val.strip():
                                edit_state["options"][opt_idx] = new_val.strip()
                        with opt_col2:
                            if st.button("Delete", key=f"del_opt_{idx}_{opt_idx}", use_container_width=True, help="🗑️ Delete option"):
                                options_to_delete.append(opt_idx)
                    
                    for opt_idx in sorted(options_to_delete, reverse=True):
                        deleted_option = edit_state["options"].pop(opt_idx)
                        if edit_state["answer"] == deleted_option:
                            edit_state["answer"] = ""
                    
                    st.write("**Add new option:**")
                    new_opt_col1, new_opt_col2 = st.columns([4, 1])
                    with new_opt_col1:
                        new_option = st.text_input("New option text", key=f"new_opt_{idx}")
                    with new_opt_col2:
                        if st.button("Add Option", key=f"add_opt_{idx}", use_container_width=True):
                            if new_option.strip() and new_option.strip() not in edit_state["options"]:
                                edit_state["options"].append(new_option.strip())
                                st.rerun()
                            elif new_option.strip() in edit_state["options"]:
                                st.warning("This option already exists!")
                    
                    if edit_state["options"]:
                        ans_idx = edit_state["options"].index(edit_state["answer"]) if edit_state["answer"] in edit_state["options"] else 0
                        new_answer_edit = st.selectbox("✅ Correct Answer", edit_state["options"], index=ans_idx, key=f"edit_a_{idx}")
                        edit_state["answer"] = new_answer_edit
                    else:
                        st.warning("⚠️ Please add at least one option.")
                        new_answer_edit = ""

                    new_explanation_edit = st.text_area("💡 Explanation", value=c.get("explanation", ""), key=f"edit_exp_{idx}", height=80)

                    if st.button("💾 Save All Changes", type="primary", use_container_width=True, key=f"save_mc_edit_{idx}"):
                        if not edit_state["options"]:
                            st.error("Multiple choice questions require options!")
                        elif not edit_state["answer"]:
                            st.error("Please select a correct answer!")
                        else:
                            c["question"] = new_question_edit.strip()
                            c["options"] = edit_state["options"]
                            c["answer"] = edit_state["answer"]
                            c["explanation"] = new_explanation_edit.strip()
                            save_data(st.session_state.data)
                            st.session_state[f"editing_{idx}"] = False
                            if f"mc_edit_state_{idx}" in st.session_state:
                                del st.session_state[f"mc_edit_state_{idx}"]
                            st.rerun()

                else:  # Fill in Blank
                    if f"fib_edit_state_{idx}" not in st.session_state:
                        st.session_state[f"fib_edit_state_{idx}"] = c.get("question", "")
                    
                    fib_text = st.session_state[f"fib_edit_state_{idx}"]
                    
                    st.write("**Question**")
                    st.caption("Type your text below, then add blanks")
                    
                    new_question_edit = st.text_area(
                        "Question Text",
                        value=fib_text,
                        key=f"edit_q_{idx}",
                        height=200
                    )
                    st.session_state[f"fib_edit_state_{idx}"] = new_question_edit
                    
                    existing_blanks = re.findall(r"\{(\d+):", new_question_edit)
                    next_blank_num = max([int(n) for n in existing_blanks] or [0]) + 1
                    
                    st.write("**Add Blank**")
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        text_to_blank = st.text_input("Text to make blank:", key=f"fib_blank_text_{idx}", placeholder="Type phrase from above")
                    with col2:
                        if st.button("Add Blank", use_container_width=True, key=f"add_blank_btn_{idx}"):
                            if text_to_blank.strip():
                                if text_to_blank in new_question_edit:
                                    updated_q = new_question_edit.replace(text_to_blank, f"{{{next_blank_num}:{text_to_blank}}}", 1)
                                    st.session_state[f"fib_edit_state_{idx}"] = updated_q
                                    st.toast(f"✓ Blank created for '{text_to_blank}'!", icon="✅")
                                    st.rerun()
                                else:
                                    st.error(f"Text '{text_to_blank}' not found in question")
                            else:
                                st.warning("Please enter text to make blank")
                    
                    st.divider()
                    st.write("**Preview**")
                    blanks = re.findall(r"\{(\d+):([^\}]+)\}", new_question_edit)
                    
                    if blanks:
                        preview_study = new_question_edit
                        for num, ans in blanks:
                            preview_study = preview_study.replace(f"{{{num}:{ans}}}", f"**{ans}**")
                        st.markdown(preview_study)
                        st.caption("📖 Study mode preview")
                        
                        st.divider()
                        
                        preview_practice = new_question_edit
                        for num, ans in blanks:
                            preview_practice = preview_practice.replace(f"{{{num}:{ans}}}", "___")
                        st.markdown(preview_practice)
                        st.caption("🎯 Practice mode preview")
                        
                        st.success(f"✓ {len(blanks)} blank(s) ready!")
                    else:
                        st.info("No blanks yet. Enter text above and click 'Add Blank'.")
                    
                    if st.button("💾 Save Changes", type="primary", use_container_width=True, key=f"save_fib_edit_{idx}"):
                        if new_question_edit.strip():
                            c["question"] = new_question_edit.strip()
                            save_data(st.session_state.data)
                            st.session_state[f"editing_{idx}"] = False
                            if f"fib_edit_state_{idx}" in st.session_state:
                                del st.session_state[f"fib_edit_state_{idx}"]
                            st.rerun()
                        else:
                            st.error("Question cannot be empty!")

# Page: Review
def render_review():
    cards = st.session_state.review_cards
    idx = st.session_state.review_idx

    if idx >= len(cards):
        st.balloons()
        st.success("🎉 You've finished all cards in this session!")
        if st.button("Return to Dashboard", type="primary"):
            navigate_to("home")
            st.rerun()
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
            st.rerun()

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
            
            # Unique Key tied directly to specific card content prevents alignment bugs on shuffle
            card_q_hash = str(hash(card['question']))
            opt_key = f"mc_opts_{st.session_state.active_deck}_{card_q_hash}"
            
            if opt_key not in st.session_state:
                opts = card.get("options", []).copy()
                random.shuffle(opts)
                st.session_state[opt_key] = opts
            
            shuffled_opts = st.session_state[opt_key]
            selected_opt = st.radio("Choose an answer:", shuffled_opts, key=f"mc_choice_{idx}_{card_q_hash}")

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
            
            if not blanks and card.get("answer"):
                st.markdown(f"### {card['question']}")
                st.divider()
                
                if not st.session_state.show_srs:
                    user_answer = st.text_input("Your answer:", key=f"simple_fib_{idx}", placeholder="Type your answer here")
                    
                    if st.button("Check Answer", use_container_width=True, type="primary"):
                        st.session_state[f"last_simple_fib_{idx}"] = user_answer
                        st.session_state.show_srs = True
                        st.rerun()
                else:
                    saved_answer = st.session_state.get(f"last_simple_fib_{idx}", "")
                    correct_answer = card.get("answer", "").strip()
                    
                    user_answer_clean = saved_answer.strip()
                    correct_answer_clean = correct_answer.strip()
                    
                    if user_answer_clean.lower() == correct_answer_clean.lower():
                        st.markdown(f"<div class='correct-answer-highlight'>✅ Correct: '{correct_answer_clean}'</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='wrong-answer-highlight'>❌ Your Answer: '{user_answer_clean}'</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='correct-answer-highlight'>✅ Correct Answer: '{correct_answer_clean}'</div>", unsafe_allow_html=True)
                    
                    render_srs_controls(card)
            
            elif blanks:
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
                        display_text = display_text.replace(f"{{{num}:{ans}}}", f"**{ans}**")
                    st.markdown(f"### {display_text}")
                    
                    render_srs_controls(card)
            else:
                st.markdown(f"### {card['question']}")
                st.info("⚠️ No content to review for this card")

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