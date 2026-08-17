import json
import os
import random
import re
import time
import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas

DATA_FILE = "flashcard_data.json"

st.set_page_config(
    page_title="HKDSE Flashcard Hub",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stButton button {
        border-radius: 8px;
        font-weight: 600;
    }
    div[data-testid="stExpander"] {
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ==================== DATA MANAGEMENT ====================
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
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# ==================== STATE INITIALIZATION ====================
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

# ==================== HELPER FUNCTIONS ====================
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
    """Returns a list of all available folder paths as human-readable strings."""
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
    """Moves a deck from source_path to target_path_str."""
    # 1. Extract cards from source
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

    # 2. Place cards into target destination
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

def navigate_to(page, deck_name=None, location=None):
    st.session_state.current_page = page
    st.session_state.show_ans = False
    st.session_state.show_srs = False
    if deck_name is not None:
        st.session_state.active_deck = deck_name
    if location is not None:
        st.session_state.deck_location = location
    st.rerun()

# ==================== SIDEBAR ====================
with st.sidebar:
    st.title("📚 HKDSE Hub")
    if st.button("🏠 Home Dashboard", use_container_width=True):
        navigate_to("home")
    
    st.divider()
    path_str = " / ".join(["Home"] + st.session_state.current_path)
    st.caption(f"**Current Location:**\n`{path_str}`")

# ==================== PAGE: HOME ====================
def render_home():
    st.title("🗂️ Deck Manager")
    
    # Top Action Bar
    col_back, col_rand = st.columns([1, 1])
    with col_back:
        if st.session_state.current_path:
            if st.button("⬆️ Up One Level", use_container_width=True):
                st.session_state.current_path.pop()
                st.rerun()
    with col_rand:
        if st.button("🎲 Quick Study (Random Deck)", use_container_width=True, type="primary"):
            all_decks = []
            for d in st.session_state.data["unsorted_decks"].keys():
                all_decks.append((d, "unsorted"))
            def collect(f_dict, path):
                for fn, fi in f_dict.items():
                    cp = path + [fn]
                    for d in fi.get("decks", {}).keys():
                        all_decks.append((d, cp))
                    collect(fi.get("folders", {}), cp)
            collect(st.session_state.data["files"], [])
            
            if all_decks:
                deck, loc = random.choice(all_decks)
                cards = get_cards(deck, loc)
                if cards:
                    st.session_state.review_cards = list(cards)
                    st.session_state.review_idx = 0
                    navigate_to("review", deck, loc)
                else:
                    st.warning("Selected deck has no cards!")
            else:
                st.info("No decks found yet!")

    st.divider()

    # Determine Current Folder Contents
    curr_folders = st.session_state.data["files"]
    for step in st.session_state.current_path:
        if step in curr_folders:
            curr_folders = curr_folders[step].get("folders", {})

    # Folders Section
    st.subheader("📁 Subfolders")
    if curr_folders:
        cols = st.columns(2)
        for idx, f_name in enumerate(list(curr_folders.keys())):
            with cols[idx % 2]:
                with st.container(border=True):
                    st.write(f"📁 **{f_name}**")
                    if st.button("Open Folder", key=f"open_{f_name}", use_container_width=True):
                        st.session_state.current_path.append(f_name)
                        st.rerun()
    else:
        st.caption("No subfolders here.")

    with st.popover("➕ Add New Folder"):
        new_folder_name = st.text_input("Folder Name")
        if st.button("Create Folder", type="primary") and new_folder_name.strip():
            curr_folders[new_folder_name.strip()] = {"folders": {}, "decks": {}}
            save_data(st.session_state.data)
            st.rerun()

    st.divider()

    # Decks Section
    st.subheader("🎴 Flashcard Decks")
    if not st.session_state.current_path:
        decks = st.session_state.data["unsorted_decks"]
        loc_tag = "unsorted"
    else:
        folder_dict = get_folder_dict(st.session_state.current_path[:-1]) if len(st.session_state.current_path) > 1 else st.session_state.data["files"]
        decks = folder_dict.get(st.session_state.current_path[-1], {}).get("decks", {})
        loc_tag = st.session_state.current_path

    all_target_folders = list_all_folder_paths()

    if decks:
        for d_name, cards in list(decks.items()):
            with st.container(border=True):
                c_info, c_rev, c_edit, c_move = st.columns([3, 1, 1, 1])
                with c_info:
                    st.markdown(f"### 🎴 {d_name}")
                    st.caption(f"Total Cards: **{len(cards)}**")
                with c_rev:
                    if st.button("▶ Review", key=f"rev_{d_name}", use_container_width=True, type="primary"):
                        if not cards:
                            st.warning("Deck is empty!")
                        else:
                            st.session_state.review_cards = list(cards)
                            st.session_state.review_idx = 0
                            navigate_to("review", d_name, loc_tag)
                with c_edit:
                    if st.button("✏️ Manage", key=f"edit_{d_name}", use_container_width=True):
                        navigate_to("editor", d_name, loc_tag)
                with c_move:
                    with st.popover("🚚 Move"):
                        selected_target = st.selectbox(
                            "Select Destination Folder",
                            options=all_target_folders,
                            key=f"move_sel_{d_name}"
                        )
                        if st.button("Confirm Move", key=f"confirm_move_{d_name}", type="primary"):
                            move_deck(d_name, loc_tag, selected_target)
                            st.success(f"Moved {d_name}!")
                            st.rerun()
    else:
        st.caption("No decks in this folder.")

    with st.popover("➕ Add New Deck"):
        new_deck_name = st.text_input("Deck Name")
        if st.button("Create Deck", type="primary") and new_deck_name.strip():
            dname = new_deck_name.strip()
            if not st.session_state.current_path:
                st.session_state.data["unsorted_decks"][dname] = []
                loc = "unsorted"
            else:
                folder_dict = get_folder_dict(st.session_state.current_path[:-1]) if len(st.session_state.current_path) > 1 else st.session_state.data["files"]
                folder_dict[st.session_state.current_path[-1]]["decks"][dname] = []
                loc = st.session_state.current_path
            save_data(st.session_state.data)
            navigate_to("editor", dname, loc)

# ==================== PAGE: EDITOR ====================
def render_editor():
    deck_name = st.session_state.active_deck
    path = st.session_state.deck_location
    
    st.header(f"✏️ Editing Deck: `{deck_name}`")

    cards = get_cards(deck_name, path)

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
                        os.makedirs("uploads", exist_ok=True)
                        image_path = os.path.join("uploads", uploaded_image.name)
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
            col_txt, col_del = st.columns([5, 1])
            with col_txt:
                st.markdown(f"**#{idx+1} [{c['type']}] {c['question'][:80]}")
            with col_del:
                if st.button("🗑️", key=f"del_{idx}", use_container_width=True):
                    cards.pop(idx)
                    save_data(st.session_state.data)
                    st.rerun()

# ==================== PAGE: REVIEW ====================
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
        st.caption(f"TYPE: **{card['type'].upper()}**")
        
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
            selected_opt = st.radio("Choose an answer:", opts, key=f"mc_{idx}")

            if not st.session_state.show_srs:
                if st.button("Check Answer", use_container_width=True, type="primary"):
                    correct = card.get("answer", "")
                    if selected_opt == correct:
                        st.success("✅ Correct!")
                    else:
                        st.error(f"❌ Incorrect! Correct answer: {correct}")

                    if card.get("explanation"):
                        st.info(f"Explanation:")
                    st.session_state.show_srs = True
                    st.rerun()
            else:
                render_srs_controls(card)

        else:
            blanks = re.findall(r"\{(\d+):([^\}]+)\}", card["question"])
            display_text = card["question"]
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
    st.session_state.review_idx += 1
    st.rerun()

# ==================== ROUTING ====================
if st.session_state.current_page == "home":
    render_home()
elif st.session_state.current_page == "editor":
    render_editor()
elif st.session_state.current_page == "review":
    render_review()