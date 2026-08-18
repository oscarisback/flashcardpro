import json
import os
import random
import re
import time
import base64
import streamlit as st
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

def export_deck_code(deck_name, cards):
    payload = {"name": deck_name, "cards": cards}
    raw_json = json.dumps(payload, ensure_ascii=False)
    encoded = base64.b64encode(raw_json.encode("utf-8")).decode("utf-8")
    return encoded

def import_deck_code(encoded_code, target_path):
    try:
        decoded_json = base64.b64decode(encoded_code.strip().encode("utf-8")).decode("utf-8")
        payload = json.loads(decoded_json)
        deck_name = payload.get("name", "Imported Deck")
        cards = payload.get("cards", [])

        if target_path == "unsorted":
            st.session_state.data["unsorted_decks"][deck_name] = cards
        else:
            folder_dict = get_folder_dict(target_path[:-1]) if len(target_path) > 1 else st.session_state.data["files"]
            folder_name = target_path[-1] if target_path else ""
            if "decks" not in folder_dict[folder_name]:
                folder_dict[folder_name]["decks"] = {}
            folder_dict[folder_name]["decks"][deck_name] = cards

        save_data(st.session_state.data)
        return True, f"Successfully imported '{deck_name}' with {len(cards)} cards!"
    except Exception as e:
        return False, f"Invalid code: {str(e)}"

def navigate_to(page, deck_name=None, location=None):
    st.session_state.current_page = page
    st.session_state.show_ans = False
    st.session_state.show_srs = False
    st.session_state.reveal_blanks = False
    if deck_name:
        st.session_state.active_deck = deck_name
    if location:
        st.session_state.deck_location = location

# Page: Home (Dashboard)
def render_home():
    st.title("📚 HKDSE Flashcard Hub")
    st.write("Organize, study, and master your flashcards with spaced repetition!")

    # Sidebar for folder navigation
    with st.sidebar:
        st.subheader("📁 Folders & Decks")
        
        # Create new folder
        with st.expander("➕ Create New Folder"):
            new_folder_name = st.text_input("Folder Name")
            parent_folder_display = st.selectbox(
                "Parent Folder",
                ["Root"] + [p.replace("Root (Unsorted)", "Root") for p in list_all_folder_paths()[1:]]
            )
            if st.button("Create Folder", key="create_folder_btn"):
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
            for name, info in folder_dict.items():
                with st.expander(f"📂 {name}", expanded=False):
                    current_path = path + [name]
                    
                    # Folder actions
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✏️ Rename", key=f"rename_folder_{name}"):
                            st.session_state[f"rename_folder_{name}"] = True
                    with col2:
                        if st.button("🗑️ Delete", key=f"delete_folder_{name}"):
                            if st.session_state.get(f"confirm_delete_folder_{name}"):
                                delete_folder(name, path)
                                st.session_state[f"confirm_delete_folder_{name}"] = False
                                st.rerun()
                            else:
                                st.session_state[f"confirm_delete_folder_{name}"] = True
                                st.warning("Click again to confirm deletion")
                    
                    if st.session_state.get(f"rename_folder_{name}"):
                        new_name = st.text_input("New folder name", key=f"rename_input_folder_{name}")
                        if st.button("Save", key=f"save_rename_folder_{name}"):
                            rename_folder(name, new_name, path)
                            st.session_state[f"rename_folder_{name}"] = False
                            st.rerun()

                    # Decks in this folder
                    decks = info.get("decks", {})
                    for deck_name in decks.keys():
                        deck_col1, deck_col2, deck_col3, deck_col4 = st.columns([3, 1, 1, 1])
                        with deck_col1:
                            if st.button(f"🎴 {deck_name}", key=f"open_deck_{deck_name}_{path}"):
                                navigate_to("editor", deck_name, current_path)
                        with deck_col2:
                            if st.button("📖", key=f"review_{deck_name}_{path}", help="Review this deck"):
                                st.session_state.review_cards = [c for c in decks[deck_name] if c.get("next_review", 0) <= time.time()]
                                st.session_state.review_idx = 0
                                navigate_to("review", deck_name, current_path)
                        with deck_col3:
                            if st.button("✏️", key=f"rename_deck_{deck_name}_{path}", help="Rename"):
                                st.session_state[f"rename_deck_{deck_name}_{path}"] = True
                        with deck_col4:
                            if st.button("🗑️", key=f"delete_deck_{deck_name}_{path}", help="Delete"):
                                if st.session_state.get(f"confirm_delete_deck_{deck_name}_{path}"):
                                    delete_deck(deck_name, current_path)
                                    st.session_state[f"confirm_delete_deck_{deck_name}_{path}"] = False
                                    st.rerun()
                                else:
                                    st.session_state[f"confirm_delete_deck_{deck_name}_{path}"] = True
                        
                        if st.session_state.get(f"rename_deck_{deck_name}_{path}"):
                            new_deck_name = st.text_input("New deck name", key=f"rename_input_deck_{deck_name}_{path}")
                            if st.button("Save", key=f"save_rename_deck_{deck_name}_{path}"):
                                rename_deck(deck_name, new_deck_name, current_path)
                                st.session_state[f"rename_deck_{deck_name}_{path}"] = False
                                st.rerun()

                    # Nested folders
                    if info.get("folders"):
                        st.subheader("Subfolders")
                        render_sidebar_tree(info["folders"], current_path)

        render_sidebar_tree(st.session_state.data["files"], [])

        # Unsorted decks
        st.divider()
        st.subheader("Unsorted Decks")
        for deck_name in st.session_state.data["unsorted_decks"].keys():
            deck_col1, deck_col2, deck_col3, deck_col4 = st.columns([3, 1, 1, 1])
            with deck_col1:
                if st.button(f"🎴 {deck_name}", key=f"open_unsorted_{deck_name}"):
                    navigate_to("editor", deck_name, "unsorted")
            with deck_col2:
                if st.button("📖", key=f"review_unsorted_{deck_name}", help="Review"):
                    st.session_state.review_cards = [c for c in st.session_state.data["unsorted_decks"][deck_name] if c.get("next_review", 0) <= time.time()]
                    st.session_state.review_idx = 0
                    navigate_to("review", deck_name, "unsorted")
            with deck_col3:
                if st.button("✏️", key=f"rename_unsorted_{deck_name}", help="Rename"):
                    st.session_state[f"rename_unsorted_{deck_name}"] = True
            with deck_col4:
                if st.button("🗑️", key=f"delete_unsorted_{deck_name}", help="Delete"):
                    if st.session_state.get(f"confirm_delete_unsorted_{deck_name}"):
                        delete_deck(deck_name, "unsorted")
                        st.session_state[f"confirm_delete_unsorted_{deck_name}"] = False
                        st.rerun()
                    else:
                        st.session_state[f"confirm_delete_unsorted_{deck_name}"] = True
            
            if st.session_state.get(f"rename_unsorted_{deck_name}"):
                new_deck_name = st.text_input("New deck name", key=f"rename_input_unsorted_{deck_name}")
                if st.button("Save", key=f"save_rename_unsorted_{deck_name}"):
                    rename_deck(deck_name, new_deck_name, "unsorted")
                    st.session_state[f"rename_unsorted_{deck_name}"] = False
                    st.rerun()

    # Main Content
    col1, col2 = st.columns(2)
    with col1:
        with st.expander("➕ Create New Deck", expanded=False):
            new_deck_name = st.text_input("Deck Name")
            target_folder = st.selectbox("Target Folder", list_all_folder_paths())
            if st.button("Create Deck"):
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
        with st.expander("📥 Import Deck from Code", expanded=False):
            import_code = st.text_area("Paste your deck code here")
            target_import = st.selectbox("Import to", list_all_folder_paths(), key="import_target")
            if st.button("Import Deck"):
                if import_code.strip():
                    target_path = "unsorted" if target_import == "Root (Unsorted)" else target_import.split(" / ")
                    success, message = import_deck_code(import_code, target_path)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

# Page: Editor
def render_editor():
    deck_name = st.session_state.active_deck
    location = st.session_state.deck_location

    st.title(f"📝 Editing: {deck_name}")
    st.write(f"Location: {' / '.join(location) if location != 'unsorted' else 'Unsorted'}")

    cards = get_cards(deck_name, location)

    # Export deck code
    with st.expander("📤 Export Deck Code"):
        code = export_deck_code(deck_name, cards)
        st.code(code)
        st.write("Share this code with others to import your deck!")

    # Add new card
    with st.expander("➕ Add New Card", expanded=True):
        with st.form("card_form", clear_on_submit=True):
            card_type = st.selectbox("Card Type", ["Standard", "Fill in Blank", "Multiple Choice"])
            question = st.text_area("Question / Prompt", help="For Fill-in-Blank, format as: {1:answer}")
            uploaded_image = st.file_uploader("Attach Image (Optional)", type=["png", "jpg", "jpeg"])
            
            answer = ""
            options_raw = ""
            explanation = ""

            if card_type == "Standard":
                answer = st.text_area("Answer")
            elif card_type == "Multiple Choice":
                options_raw = st.text_area("Options (One per line)")
                answer = st.text_input("Correct Answer (Exact text match)")
                explanation = st.text_area("Explanation (Optional)")

            if st.form_submit_button("💾 Add Card to Deck", type="primary"):
                if question.strip():
                    image_path = None
                    if uploaded_image is not None:
                        os.makedirs(UPLOADS_DIR, exist_ok=True)
                        image_path = os.path.join(UPLOADS_DIR, uploaded_image.name)
                        with open(image_path, "wb") as f:
                            f.write(uploaded_image.getbuffer())

                    card_data = {
                        "type": card_type,
                        "question": question.strip(),
                        "image": image_path,
                        "interval": 1,
                        "ease_factor": 2.5,
                        "next_review": time.time()
                    }

                    if card_type == "Standard":
                        card_data["answer"] = answer.strip()
                    elif card_type == "Multiple Choice":
                        opts = [o.strip() for o in options_raw.splitlines() if o.strip()]
                        card_data["options"] = opts
                        card_data["answer"] = answer.strip()
                        card_data["explanation"] = explanation.strip()

                    cards.append(card_data)
                    save_data(st.session_state.data)
                    st.success("Card added!")
                    st.rerun()

    st.subheader(f"Existing Cards ({len(cards)})")
    for idx, c in enumerate(cards):
        with st.container(border=True):
            col_txt, col_edit, col_del = st.columns([4, 1, 1])
            with col_txt:
                st.markdown(f"**#{idx+1} [{c['type']}] {c['question'][:80]}")
            with col_edit:
                if st.button("✏️", key=f"edit_{idx}", use_container_width=True):
                    st.session_state[f"editing_{idx}"] = not st.session_state.get(f"editing_{idx}", False)
            with col_del:
                if st.button("🗑️", key=f"del_{idx}", use_container_width=True):
                    if st.session_state.get(f"confirm_delete_card_{idx}"):
                        cards.pop(idx)
                        save_data(st.session_state.data)
                        st.session_state[f"confirm_delete_card_{idx}"] = False
                        st.rerun()
                    else:
                        st.session_state[f"confirm_delete_card_{idx}"] = True
                        st.warning("Click again to confirm")

            # Edit card
            if st.session_state.get(f"editing_{idx}"):
                st.divider()
                st.write("**Edit Card**")
                with st.form(f"edit_form_{idx}", clear_on_submit=True):
                    if c["type"] == "Standard":
                        new_question = st.text_area("Question", value=c.get("question", ""), key=f"q_{idx}")
                        new_answer = st.text_area("Answer", value=c.get("answer", ""), key=f"a_{idx}")
                        if st.form_submit_button("Save Changes"):
                            c["question"] = new_question.strip()
                            c["answer"] = new_answer.strip()
                            save_data(st.session_state.data)
                            st.session_state[f"editing_{idx}"] = False
                            st.rerun()
                    elif c["type"] == "Multiple Choice":
                        new_question = st.text_area("Question", value=c.get("question", ""), key=f"q_{idx}")
                        new_opts = st.text_area("Options (one per line)", value="\n".join(c.get("options", [])), key=f"opts_{idx}")
                        new_answer = st.text_input("Correct Answer", value=c.get("answer", ""), key=f"a_{idx}")
                        new_explanation = st.text_area("Explanation", value=c.get("explanation", ""), key=f"exp_{idx}")
                        if st.form_submit_button("Save Changes"):
                            c["question"] = new_question.strip()
                            c["options"] = [o.strip() for o in new_opts.splitlines() if o.strip()]
                            c["answer"] = new_answer.strip()
                            c["explanation"] = new_explanation.strip()
                            save_data(st.session_state.data)
                            st.session_state[f"editing_{idx}"] = False
                            st.rerun()
                    else:  # Fill in Blank
                        new_question = st.text_area("Question (Format: {1:answer})", value=c.get("question", ""), key=f"q_{idx}")
                        if st.form_submit_button("Save Changes"):
                            c["question"] = new_question.strip()
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
    st.progress(progress, text=f"Card {idx + 1} of {len(cards)} — Deck: {st.session_state.active_deck}")

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
            opts = card.get("options", [])
            shuffled_opts = opts.copy()
            random.shuffle(shuffled_opts)
            
            selected_opt = st.radio("Choose an answer:", shuffled_opts, key=f"mc_{idx}")

            if not st.session_state.show_srs:
                if st.button("Check Answer", use_container_width=True, type="primary"):
                    correct = card.get("answer", "")
                    col1, col2 = st.columns(2)
                    with col1:
                        if selected_opt == correct:
                            st.success("✅ Correct!")
                        else:
                            st.error(f"❌ Incorrect! Correct answer: **{correct}**")
                    
                    if card.get("explanation"):
                        st.info(f"**Explanation:** {card.get('explanation')}")
                    
                    st.session_state.show_srs = True
                    st.rerun()
            else:
                render_srs_controls(card)

        else:  # Fill in Blank
            blanks = re.findall(r"\{(\d+):([^\}]+)\}", card["question"])
            display_text = card["question"]
            
            if not st.session_state.reveal_blanks:
                # Show highlighted answers
                for num, ans in blanks:
                    display_text = display_text.replace(f"{{{num}:{ans}}}", f"<span class='highlighted-answer'>{ans}</span>")
                st.markdown(f"### {display_text}", unsafe_allow_html=True)
                
                if st.button("Hide Answers & Practice", use_container_width=True, type="primary"):
                    st.session_state.reveal_blanks = True
                    st.rerun()
            else:
                # Show blanks to fill in
                for num, ans in blanks:
                    display_text = display_text.replace(f"{{{num}:{ans}}}", " `[ ____ ]` ")
                st.markdown(f"### {display_text}")
                
                user_inputs = {}
                for num, ans in blanks:
                    user_inputs[num] = (st.text_input(f"Blank #{num}:", key=f"blank_{idx}_{num}"), ans)

                if not st.session_state.show_srs:
                    if st.button("Check Answer", use_container_width=True, type="primary"):
                        all_correct = True
                        for num, (val, target) in user_inputs.items():
                            if val.strip().lower() != target.strip().lower():
                                all_correct = False
                                st.error(f"Blank #{num} Incorrect! Correct: `{target}`")
                        if all_correct:
                            st.success("✅ All Blanks Correct!")
                        st.session_state.show_srs = True
                        st.rerun()
                else:
                    render_srs_controls(card)

def render_srs_controls(card):
    st.divider()
    st.write("**How easily did you recall this card?**")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("❌ Missed", key="srs_1", use_container_width=True):
            apply_srs(card, 1)
    with c2:
        if st.button("⚡ Hard", key="srs_3", use_container_width=True):
            apply_srs(card, 3)
    with c3:
        if st.button("👍 Good", key="srs_4", use_container_width=True):
            apply_srs(card, 4)
    with c4:
        if st.button("✅ Easy", key="srs_5", use_container_width=True):
            apply_srs(card, 5)

def apply_srs(card, quality):
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