import json
import random
import re
import os
import tkinter as tk
from tkinter import colorchooser, messagebox, ttk

DATA_FILE = "flashcard_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"files": {}, "unsorted_decks": {}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

class DSEFlashcardApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HKDSE Master Flashcard App")
        self.geometry("1280x850")
        self.configure(bg="#0f172a")

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TCombobox", fieldbackground="#ffffff", background="#e2e8f0", padding=5)

        self.data = load_data()
        self.current_deck_name = None
        self.current_deck_data = []

        self.container = tk.Frame(self, bg="#0f172a")
        self.container.pack(fill="both", expand=True)

        self.show_home_screen()

    def clear_container(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    # ==================== 1. HOME SCREEN & DASHBOARD ====================
    def show_home_screen(self):
        self.clear_container()

        top_bar = tk.Frame(self.container, bg="#1e293b", height=70)
        top_bar.pack(fill="x")
        
        tk.Label(
            top_bar, text="📚 HKDSE Flashcard Hub", font=("Segoe UI", 20, "bold"),
            fg="#f8fafc", bg="#1e293b"
        ).pack(side="left", padx=25, pady=15)

        # ADJUSTMENT 3: Instant Random Deck Selector Button (No animation)
        tk.Button(
            top_bar, text="🎲 Quick Random Deck", font=("Segoe UI", 11, "bold"),
            bg="#f59e0b", fg="white", activebackground="#d97706", activeforeground="white",
            bd=0, cursor="hand2", command=self.open_random_deck, padx=14, pady=6
        ).pack(side="right", padx=15, pady=15)

        tk.Button(
            top_bar, text="+ New Deck", font=("Segoe UI", 11, "bold"),
            bg="#2563eb", fg="white", activebackground="#1d4ed8", activeforeground="white",
            bd=0, cursor="hand2", command=self.create_deck_dialog, padx=14, pady=6
        ).pack(side="right", padx=5, pady=15)

        tk.Button(
            top_bar, text="+ New Folder", font=("Segoe UI", 11, "bold"),
            bg="#3b82f6", fg="white", activebackground="#2563eb", activeforeground="white",
            bd=0, cursor="hand2", command=self.create_folder_dialog, padx=14, pady=6
        ).pack(side="right", padx=5, pady=15)

        main_area = tk.Frame(self.container, bg="#0f172a")
        main_area.pack(fill="both", expand=True, padx=35, pady=25)

        # Folders
        tk.Label(main_area, text="FOLDERS", font=("Segoe UI", 12, "bold"), fg="#94a3b8", bg="#0f172a").pack(anchor="w")
        folder_frame = tk.Frame(main_area, bg="#0f172a")
        folder_frame.pack(fill="x", pady=(8, 25))

        if not self.data["files"]:
            tk.Label(folder_frame, text="No folders created yet.", fg="#64748b", bg="#0f172a", font=("Segoe UI", 11)).pack(anchor="w")

        for folder_name, folder_info in self.data["files"].items():
            deck_count = len(folder_info.get("decks", {}))
            btn = tk.Button(
                folder_frame, text=f"📁 {folder_name}\n({deck_count} Decks)", font=("Segoe UI", 11, "bold"),
                bg=folder_info.get("color", "#334155"), fg="white", activebackground="#475569", activeforeground="white",
                bd=0, cursor="hand2", padx=20, pady=12,
                command=lambda f=folder_name: self.view_folder_contents(f)
            )
            btn.pack(side="left", padx=8, pady=5)

        # Unsorted Decks
        tk.Label(main_area, text="UNSORTED DECKS", font=("Segoe UI", 12, "bold"), fg="#94a3b8", bg="#0f172a").pack(anchor="w")
        deck_frame = tk.Frame(main_area, bg="#0f172a")
        deck_frame.pack(fill="both", expand=True, pady=8)

        if not self.data["unsorted_decks"]:
            tk.Label(deck_frame, text="No unsorted decks available.", fg="#64748b", bg="#0f172a", font=("Segoe UI", 11)).pack(anchor="w")

        for deck_name in list(self.data["unsorted_decks"].keys()):
            df = tk.Frame(deck_frame, bg="#1e293b", highlightbackground="#334155", highlightthickness=1, padx=15, pady=15)
            df.pack(side="left", padx=10, pady=10)

            tk.Label(df, text=f"🎴 {deck_name}", font=("Segoe UI", 13, "bold"), fg="#f8fafc", bg="#1e293b").pack(pady=(0, 10))
            
            tk.Button(
                df, text="▶ Review", bg="#2563eb", fg="white", font=("Segoe UI", 10, "bold"), bd=0, cursor="hand2",
                command=lambda d=deck_name: self.start_review(d, "unsorted")
            ).pack(fill="x", pady=3)

            tk.Button(
                df, text="✏️ Edit Cards", bg="#475569", fg="white", font=("Segoe UI", 10, "bold"), bd=0, cursor="hand2",
                command=lambda d=deck_name: self.manage_deck_cards(d, "unsorted")
            ).pack(fill="x", pady=3)

            # ADJUSTMENT 1: Rename Deck Option
            tk.Button(
                df, text="📝 Rename Deck", bg="#334155", fg="white", font=("Segoe UI", 9), bd=0, cursor="hand2",
                command=lambda d=deck_name: self.rename_deck_dialog(d, "unsorted")
            ).pack(fill="x", pady=3)

            if self.data["files"]:
                move_btn = tk.Button(
                    df, text="📂 Move to Folder", bg="#0f172a", fg="#94a3b8", font=("Segoe UI", 9), bd=0, cursor="hand2",
                    command=lambda d=deck_name: self.move_deck_dialog(d)
                )
                move_btn.pack(fill="x", pady=(3, 0))

    # ADJUSTMENT 1: Dialog to Rename Deck
    def rename_deck_dialog(self, old_name, location):
        dialog = tk.Toplevel(self)
        dialog.title("Rename Deck")
        dialog.geometry("380x180")
        dialog.configure(bg="#1e293b")

        tk.Label(dialog, text=f"Rename '{old_name}' to:", font=("Segoe UI", 11, "bold"), fg="white", bg="#1e293b").pack(pady=(15, 5))
        entry = tk.Entry(dialog, font=("Segoe UI", 12))
        entry.insert(0, old_name)
        entry.pack(pady=5)

        def do_rename():
            new_name = entry.get().strip()
            if not new_name:
                messagebox.showwarning("Warning", "Deck name cannot be empty.")
                return

            if location == "unsorted":
                if new_name != old_name and new_name in self.data["unsorted_decks"]:
                    messagebox.showerror("Error", "A deck with this name already exists!")
                    return
                cards = self.data["unsorted_decks"].pop(old_name)
                self.data["unsorted_decks"][new_name] = cards
            else:
                folder_decks = self.data["files"][location]["decks"]
                if new_name != old_name and new_name in folder_decks:
                    messagebox.showerror("Error", "A deck with this name already exists in this folder!")
                    return
                cards = folder_decks.pop(old_name)
                folder_decks[new_name] = cards

            save_data(self.data)
            dialog.destroy()
            self.show_home_screen()

        tk.Button(dialog, text="Save New Name", font=("Segoe UI", 11, "bold"), bg="#10b981", fg="white", bd=0, command=do_rename).pack(pady=15)

    def move_deck_dialog(self, deck_name):
        dialog = tk.Toplevel(self)
        dialog.title("Move Deck")
        dialog.geometry("380x200")
        dialog.configure(bg="#1e293b")

        tk.Label(dialog, text=f"Move '{deck_name}' to:", font=("Segoe UI", 12, "bold"), fg="white", bg="#1e293b").pack(pady=15)
        
        folder_var = tk.StringVar(value=list(self.data["files"].keys())[0])
        dropdown = ttk.Combobox(dialog, textvariable=folder_var, values=list(self.data["files"].keys()), state="readonly")
        dropdown.pack(pady=10)

        def do_move():
            target_folder = folder_var.get()
            if target_folder in self.data["files"]:
                deck_cards = self.data["unsorted_decks"].pop(deck_name)
                self.data["files"][target_folder]["decks"][deck_name] = deck_cards
                save_data(self.data)
                dialog.destroy()
                self.show_home_screen()

        tk.Button(dialog, text="Move Deck", font=("Segoe UI", 11, "bold"), bg="#2563eb", fg="white", bd=0, command=do_move).pack(pady=15)

    def create_folder_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title("New Folder")
        dialog.geometry("380x230")
        dialog.configure(bg="#1e293b")

        tk.Label(dialog, text="Folder Name:", font=("Segoe UI", 11, "bold"), fg="white", bg="#1e293b").pack(pady=(15, 5))
        name_entry = tk.Entry(dialog, font=("Segoe UI", 12))
        name_entry.pack(pady=5)

        selected_color = ["#2563eb"]

        def pick_color():
            color = colorchooser.askcolor()[1]
            if color:
                selected_color[0] = color
                color_btn.config(bg=color)

        color_btn = tk.Button(dialog, text="Pick Accent Color", font=("Segoe UI", 10, "bold"), bg=selected_color[0], fg="white", bd=0, command=pick_color)
        color_btn.pack(pady=10)

        def save():
            name = name_entry.get().strip()
            if name:
                self.data["files"][name] = {"color": selected_color[0], "decks": {}}
                save_data(self.data)
                dialog.destroy()
                self.show_home_screen()

        tk.Button(dialog, text="Create Folder", font=("Segoe UI", 11, "bold"), command=save, bg="#10b981", fg="white", bd=0).pack(pady=10)

    def create_deck_dialog(self, target_folder=None):
        dialog = tk.Toplevel(self)
        dialog.title("New Deck")
        dialog.geometry("380x200")
        dialog.configure(bg="#1e293b")

        tk.Label(dialog, text="Deck Name:", font=("Segoe UI", 11, "bold"), fg="white", bg="#1e293b").pack(pady=(15, 5))
        name_entry = tk.Entry(dialog, font=("Segoe UI", 12))
        name_entry.pack(pady=5)

        def save():
            name = name_entry.get().strip()
            if name:
                if target_folder:
                    self.data["files"][target_folder]["decks"][name] = []
                    location = target_folder
                else:
                    if name not in self.data["unsorted_decks"]:
                        self.data["unsorted_decks"][name] = []
                    location = "unsorted"
                
                save_data(self.data)
                dialog.destroy()
                self.editor_screen(name, location)

        tk.Button(dialog, text="Create & Add Cards", font=("Segoe UI", 11, "bold"), command=save, bg="#10b981", fg="white", bd=0).pack(pady=15)

    def view_folder_contents(self, folder_name):
        dialog = tk.Toplevel(self)
        dialog.title(f"Folder: {folder_name}")
        dialog.geometry("620x450")
        dialog.configure(bg="#1e293b")

        top_f = tk.Frame(dialog, bg="#1e293b")
        top_f.pack(fill="x", padx=20, pady=15)

        tk.Label(top_f, text=f"📁 {folder_name}", font=("Segoe UI", 16, "bold"), fg="white", bg="#1e293b").pack(side="left")
        
        tk.Button(
            top_f, text="+ Add Deck", font=("Segoe UI", 10, "bold"), bg="#2563eb", fg="white", bd=0,
            command=lambda: [dialog.destroy(), self.create_deck_dialog(target_folder=folder_name)]
        ).pack(side="right")

        decks = self.data["files"][folder_name].get("decks", {})

        if not decks:
            tk.Label(dialog, text="No decks inside this folder.", fg="#94a3b8", bg="#1e293b", font=("Segoe UI", 12)).pack(pady=30)

        for d_name in list(decks.keys()):
            row = tk.Frame(dialog, bg="#0f172a", padx=10, pady=10)
            row.pack(fill="x", padx=20, pady=6)

            tk.Label(row, text=f"🎴 {d_name}", font=("Segoe UI", 12, "bold"), fg="white", bg="#0f172a").pack(side="left")
            
            tk.Button(
                row, text="▶ Review", font=("Segoe UI", 10, "bold"), bg="#2563eb", fg="white", bd=0,
                command=lambda d=d_name: [dialog.destroy(), self.start_review(d, folder_name)]
            ).pack(side="right", padx=4)

            tk.Button(
                row, text="✏️ Edit", font=("Segoe UI", 10, "bold"), bg="#475569", fg="white", bd=0,
                command=lambda d=d_name: [dialog.destroy(), self.manage_deck_cards(d, folder_name)]
            ).pack(side="right", padx=4)

            # ADJUSTMENT 1: Rename deck inside folder
            tk.Button(
                row, text="📝 Rename", font=("Segoe UI", 10), bg="#334155", fg="white", bd=0,
                command=lambda d=d_name: [dialog.destroy(), self.rename_deck_dialog(d, folder_name)]
            ).pack(side="right", padx=4)

    # ==================== 2. CARD EDITOR ====================
    def manage_deck_cards(self, deck_name, location):
        self.clear_container()

        tk.Label(self.container, text=f"Managing Deck: {deck_name}", font=("Segoe UI", 18, "bold"), fg="white", bg="#0f172a").pack(pady=20)

        top_btns = tk.Frame(self.container, bg="#0f172a")
        top_btns.pack(fill="x", padx=35)

        tk.Button(top_btns, text="+ Add New Card", bg="#10b981", fg="white", font=("Segoe UI", 11, "bold"), bd=0, padx=12, pady=6,
                  command=lambda: self.editor_screen(deck_name, location)).pack(side="left")

        tk.Button(top_btns, text="← Back to Home", font=("Segoe UI", 11), bg="#334155", fg="white", bd=0, padx=12, pady=6,
                  command=self.show_home_screen).pack(side="right")

        cards = self.data["unsorted_decks"].get(deck_name, []) if location == "unsorted" else self.data["files"][location]["decks"].get(deck_name, [])

        list_frame = tk.Frame(self.container, bg="#1e293b")
        list_frame.pack(fill="both", expand=True, padx=35, pady=15)

        if not cards:
            tk.Label(list_frame, text="No cards in this deck yet.", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 13)).pack(pady=40)

        for idx, card in enumerate(cards):
            c_row = tk.Frame(list_frame, bg="#0f172a", padx=10, pady=10)
            c_row.pack(fill="x", padx=15, pady=6)

            lbl_text = f"[{card['type']}] " + (card['question'][:60] + "..." if len(card['question']) > 60 else card['question'])
            tk.Label(c_row, text=lbl_text, font=("Segoe UI", 11), fg="white", bg="#0f172a").pack(side="left", padx=10)

            tk.Button(c_row, text="Delete", bg="#ef4444", fg="white", font=("Segoe UI", 9, "bold"), bd=0,
                      command=lambda i=idx: self.delete_card(deck_name, location, i)).pack(side="right", padx=5)
            tk.Button(c_row, text="Edit", bg="#3b82f6", fg="white", font=("Segoe UI", 9, "bold"), bd=0,
                      command=lambda i=idx: self.editor_screen(deck_name, location, card_idx=i)).pack(side="right", padx=5)

    def delete_card(self, deck_name, location, card_idx):
        cards = self.data["unsorted_decks"][deck_name] if location == "unsorted" else self.data["files"][location]["decks"][deck_name]
        cards.pop(card_idx)
        save_data(self.data)
        self.manage_deck_cards(deck_name, location)

    def editor_screen(self, deck_name, location, card_idx=None):
        self.clear_container()

        cards = self.data["unsorted_decks"][deck_name] if location == "unsorted" else self.data["files"][location]["decks"][deck_name]
        editing = card_idx is not None
        card_data = cards[card_idx] if editing else {"type": "Standard", "question": "", "answer": ""}

        tk.Label(self.container, text=f"{'Edit' if editing else 'Add'} Card in '{deck_name}'",
                 font=("Segoe UI", 18, "bold"), fg="white", bg="#0f172a").pack(pady=20)

        form_frame = tk.Frame(self.container, bg="#1e293b", padx=30, pady=25)
        form_frame.pack(padx=35, pady=10, fill="both", expand=True)

        card_type = tk.StringVar(value=card_data.get("type", "Standard"))

        type_row = tk.Frame(form_frame, bg="#1e293b")
        type_row.pack(anchor="w", pady=(0, 10))
        tk.Label(type_row, text="Card Type: ", bg="#1e293b", fg="white", font=("Segoe UI", 11, "bold")).pack(side="left")
        type_dropdown = ttk.Combobox(type_row, textvariable=card_type, values=["Standard", "Fill in Blank"], state="readonly")
        type_dropdown.pack(side="left", padx=10)

        # ADJUSTMENT 2: Button to convert selected text to blank automatically
        def make_selected_text_blank():
            try:
                start_idx = q_txt.index("sel.first")
                end_idx = q_txt.index("sel.last")
                selected_text = q_txt.get(start_idx, end_idx)

                if selected_text:
                    full_text = q_txt.get("1.0", "end-1c")
                    existing_nums = [int(n) for n in re.findall(r"\{(\d+):", full_text)]
                    next_num = max(existing_nums) + 1 if existing_nums else 1

                    blank_formatted = f"{{{next_num}:{selected_text}}}"
                    q_txt.delete(start_idx, end_idx)
                    q_txt.insert(start_idx, blank_formatted)
            except tk.TclError:
                messagebox.showinfo("Tip", "Please highlight/select text with your mouse inside the text box first.")

        make_blank_btn = tk.Button(
            type_row, text="✨ Convert Highlighted Text to Blank", font=("Segoe UI", 10, "bold"),
            bg="#f59e0b", fg="white", bd=0, cursor="hand2", command=make_selected_text_blank, padx=10, pady=2
        )

        tk.Label(form_frame, text="Card Content / Question:", bg="#1e293b", fg="white", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(10, 5))
        
        q_txt = tk.Text(form_frame, height=5, font=("Segoe UI", 11))
        q_txt.insert("1.0", card_data.get("question", ""))
        q_txt.pack(fill="x", pady=5)

        fib_info = tk.Label(
            form_frame,
            text="💡 Tip: Highlight text with your mouse and click 'Convert Highlighted Text to Blank' above!",
            fg="#60a5fa", bg="#1e293b", justify="left", font=("Segoe UI", 10)
        )

        std_lbl = tk.Label(form_frame, text="Back Side (Answer):", bg="#1e293b", fg="white", font=("Segoe UI", 11, "bold"))
        back_txt = tk.Text(form_frame, height=4, font=("Segoe UI", 11))
        back_txt.insert("1.0", card_data.get("answer", ""))

        def on_type_change(event=None):
            if card_type.get() == "Fill in Blank":
                make_blank_btn.pack(side="left", padx=15)
                fib_info.pack(anchor="w", pady=10)
                std_lbl.pack_forget()
                back_txt.pack_forget()
            else:
                make_blank_btn.pack_forget()
                fib_info.pack_forget()
                std_lbl.pack(anchor="w", pady=(10, 5))
                back_txt.pack(fill="x", pady=5)

        type_dropdown.bind("<<ComboboxSelected>>", on_type_change)
        on_type_change()

        def save_card():
            ctype = card_type.get()
            q = q_txt.get("1.0", "end-1c").strip()
            a = back_txt.get("1.0", "end-1c").strip() if ctype == "Standard" else ""

            if not q:
                messagebox.showwarning("Warning", "Text field cannot be empty.")
                return

            new_card = {"type": ctype, "question": q, "answer": a, "missed": False}

            if editing:
                cards[card_idx] = new_card
            else:
                cards.append(new_card)

            save_data(self.data)
            self.manage_deck_cards(deck_name, location)

        btn_bar = tk.Frame(form_frame, bg="#1e293b")
        btn_bar.pack(pady=20)

        tk.Button(btn_bar, text="Save Flashcard", bg="#10b981", fg="white", font=("Segoe UI", 11, "bold"), bd=0, padx=15, pady=8, command=save_card).pack(side="left", padx=10)
        tk.Button(btn_bar, text="Cancel", font=("Segoe UI", 11), bg="#475569", fg="white", bd=0, padx=15, pady=8, command=lambda: self.manage_deck_cards(deck_name, location)).pack(side="left", padx=10)

    # ==================== 3. REVIEW & WHITEBOARD ====================
    def start_review(self, deck_name, location):
        if location == "unsorted":
            self.current_deck_data = self.data["unsorted_decks"].get(deck_name, [])
        else:
            self.current_deck_data = self.data["files"][location]["decks"].get(deck_name, [])

        if not self.current_deck_data:
            messagebox.showinfo("Empty Deck", "This deck has no cards! Add cards first.")
            self.editor_screen(deck_name, location)
            return

        self.current_deck_name = deck_name
        self.current_card_idx = 0
        self.show_review_screen()

    def show_review_screen(self):
        self.clear_container()

        card = self.current_deck_data[self.current_card_idx]

        top_frame = tk.Frame(self.container, bg="#0f172a")
        top_frame.pack(fill="x", padx=35, pady=15)

        tk.Label(
            top_frame, text=f"Reviewing: {self.current_deck_name} ({self.current_card_idx + 1}/{len(self.current_deck_data)})",
            font=("Segoe UI", 16, "bold"), fg="white", bg="#0f172a"
        ).pack(side="left")

        tk.Button(top_frame, text="Exit Review", font=("Segoe UI", 10), bg="#334155", fg="white", bd=0, command=self.show_home_screen).pack(side="right")

        split_frame = tk.Frame(self.container, bg="#0f172a")
        split_frame.pack(fill="both", expand=True, padx=35, pady=10)

        card_box = tk.Frame(split_frame, bg="#1e293b")
        card_box.pack(side="left", fill="both", expand=True, padx=(0, 10))

        wb_frame = tk.Frame(split_frame, bg="#1e293b")
        wb_frame.pack(side="right", fill="both", expand=True, padx=(10, 0))

        tk.Label(wb_frame, text="📝 Scratchpad / Whiteboard", font=("Segoe UI", 12, "bold"), fg="white", bg="#1e293b").pack(pady=8)
        
        canvas = tk.Canvas(wb_frame, bg="#ffffff", highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=10, pady=5)

        self.last_x, self.last_y = None, None

        def start_draw(event):
            self.last_x, self.last_y = event.x, event.y

        def draw(event):
            if self.last_x and self.last_y:
                canvas.create_line(
                    self.last_x, self.last_y, event.x, event.y,
                    fill="#0f172a", width=3, capstyle=tk.ROUND, joinstyle=tk.ROUND
                )
                self.last_x, self.last_y = event.x, event.y

        def reset_draw(event):
            self.last_x, self.last_y = None, None

        canvas.bind("<Button-1>", start_draw)
        canvas.bind("<B1-Motion>", draw)
        canvas.bind("<ButtonRelease-1>", reset_draw)

        tk.Button(wb_frame, text="Clear Scratchpad", font=("Segoe UI", 10), bg="#475569", fg="white", bd=0, command=lambda: canvas.delete("all")).pack(pady=10)

        if card["type"] == "Standard":
            q_label = tk.Label(card_box, text=card["question"], font=("Segoe UI", 16, "bold"), fg="white", wraplength=450, bg="#1e293b")
            q_label.pack(pady=40)

            ans_label = tk.Label(card_box, text="", font=("Segoe UI", 14), fg="#60a5fa", wraplength=450, bg="#1e293b")
            ans_label.pack(pady=20)

            def reveal():
                ans_label.config(text=card["answer"])

            tk.Button(card_box, text="Reveal Answer", font=("Segoe UI", 11, "bold"), command=reveal, bg="#2563eb", fg="white", bd=0, padx=12, pady=6).pack(pady=15)

        else:
            text_str = card["question"]
            blanks = re.findall(r"\{(\d+):([^\}]+)\}", text_str)

            display_text = text_str
            for num, ans in blanks:
                display_text = display_text.replace(f"{{{num}:{ans}}}", f" [ Blank #{num} ] ")

            tk.Label(card_box, text=display_text, font=("Segoe UI", 14, "bold"), fg="white", wraplength=450, bg="#1e293b").pack(pady=25)

            entries = {}
            entries_frame = tk.Frame(card_box, bg="#1e293b")
            entries_frame.pack(pady=10)

            for num, ans in blanks:
                r = tk.Frame(entries_frame, bg="#1e293b")
                r.pack(fill="x", pady=4)
                tk.Label(r, text=f"Blank #{num}:", font=("Segoe UI", 11, "bold"), fg="white", bg="#1e293b").pack(side="left", padx=5)
                e = tk.Entry(r, font=("Segoe UI", 11), width=18)
                e.pack(side="right", padx=5)
                entries[num] = (e, ans)

            def check_blanks():
                all_correct = True
                for num, (entry, correct_ans) in entries.items():
                    if entry.get().strip().lower() != correct_ans.strip().lower():
                        all_correct = False
                        break

                if all_correct:
                    messagebox.showinfo("Correct!", "All blanks filled correctly!")
                else:
                    corr_msg = "\n".join([f"Blank #{n}: {a}" for n, (_, a) in entries.items()])
                    messagebox.showerror("Incorrect", f"Correct Answers:\n{corr_msg}")

            tk.Button(card_box, text="Check Answers", font=("Segoe UI", 11, "bold"), command=check_blanks, bg="#f59e0b", fg="white", bd=0, padx=12, pady=6).pack(pady=15)

        btn_frame = tk.Frame(card_box, bg="#1e293b")
        btn_frame.pack(side="bottom", fill="x", pady=20)

        def record_result(got_correct):
            if not got_correct:
                card["missed"] = True
                self.current_deck_data.append(card)

            if self.current_card_idx + 1 < len(self.current_deck_data):
                self.current_card_idx += 1
                self.show_review_screen()
            else:
                messagebox.showinfo("Deck Finished!", "Great job! Review finished.")
                self.show_home_screen()

        tk.Button(btn_frame, text="❌ Missed (Retry)", bg="#ef4444", fg="white", font=("Segoe UI", 10, "bold"), bd=0, pady=8,
                  command=lambda: record_result(False)).pack(side="left", padx=20, expand=True)

        tk.Button(btn_frame, text="✅ Got it Right", bg="#10b981", fg="white", font=("Segoe UI", 10, "bold"), bd=0, pady=8,
                  command=lambda: record_result(True)).pack(side="right", padx=20, expand=True)

    # ADJUSTMENT 3: Instant Random Deck Selection Function
    def open_random_deck(self):
        all_deck_options = []
        
        # Unsorted decks
        for deck in self.data["unsorted_decks"].keys():
            all_deck_options.append((deck, "unsorted"))

        # Decks in folders
        for folder_name, folder_data in self.data["files"].items():
            for deck in folder_data.get("decks", {}).keys():
                all_deck_options.append((deck, folder_name))

        if not all_deck_options:
            messagebox.showwarning("Warning", "No decks found to pick from!")
            return

        chosen_deck, location = random.choice(all_deck_options)
        messagebox.showinfo("Random Pick", f"🎯 Randomly selected deck: '{chosen_deck}'!\nOpening review mode...")
        self.start_review(chosen_deck, location)

if __name__ == "__main__":
    app = DSEFlashcardApp()
    app.mainloop()