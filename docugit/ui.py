from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from docugit.extractors import extract_text, replace_text
from docugit.repository import DocumentRepository


AUTHOR_NAME = "Bhavya"
PALETTE = {
    "background": "#111615",
    "panel": "#181f1d",
    "raised": "#202a27",
    "border": "#2c3834",
    "text": "#e7eee9",
    "muted": "#92a19a",
    "accent": "#b7ed72",
    "accent_text": "#16200f",
    "added": "#b7ed72",
    "removed": "#ff8d82",
    "blue": "#91c8e8",
}


class DocuGitApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.repository = DocumentRepository(Path(__file__).resolve().parent.parent)
        self.documents: list[dict] = []
        self.visible_documents: list[dict] = []
        self.selected_document_id: str | None = None
        self.editor_dirty = False
        self.editor_save_after_id: str | None = None

        self.root.title("DocuGit | Document history")
        self.root.geometry("1320x860")
        self.root.minsize(1020, 680)
        self.root.configure(bg=PALETTE["background"])
        self._configure_styles()
        self._build_layout()
        self._refresh_documents()
        self.root.bind("<Control-o>", lambda _event: self._add_document())
        self.root.bind("<Control-s>", lambda _event: self._commit_version())

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("App.TFrame", background=PALETTE["background"])
        style.configure("Panel.TFrame", background=PALETTE["panel"])
        style.configure("Raised.TFrame", background=PALETTE["raised"])
        style.configure(
            "TLabel", background=PALETTE["background"], foreground=PALETTE["text"],
            font=("Aptos", 10),
        )
        style.configure(
            "Panel.TLabel", background=PALETTE["panel"], foreground=PALETTE["text"],
            font=("Aptos", 10),
        )
        style.configure(
            "Muted.TLabel", background=PALETTE["background"], foreground=PALETTE["muted"],
            font=("Aptos", 9),
        )
        style.configure(
            "PanelMuted.TLabel", background=PALETTE["panel"], foreground=PALETTE["muted"],
            font=("Aptos", 9),
        )
        style.configure(
            "Title.TLabel", background=PALETTE["background"], foreground=PALETTE["text"],
            font=("Aptos Display", 20, "bold"),
        )
        style.configure(
            "Accent.TButton", background=PALETTE["accent"], foreground=PALETTE["accent_text"],
            borderwidth=0, padding=(14, 9), font=("Aptos", 10, "bold"),
        )
        style.map("Accent.TButton", background=[("active", "#c9f493"), ("disabled", "#647253")])
        style.configure(
            "Quiet.TButton", background=PALETTE["raised"], foreground=PALETTE["text"],
            borderwidth=0, padding=(12, 8), font=("Aptos", 10),
        )
        style.map("Quiet.TButton", background=[("active", "#2a3732"), ("disabled", "#1a211f")])
        style.configure(
            "Treeview", background=PALETTE["panel"], fieldbackground=PALETTE["panel"],
            foreground=PALETTE["text"], borderwidth=0, rowheight=34,
            font=("Aptos", 10),
        )
        style.configure(
            "Treeview.Heading", background=PALETTE["raised"], foreground=PALETTE["muted"],
            borderwidth=0, padding=(9, 8), font=("Aptos", 9, "bold"),
        )
        style.map(
            "Treeview", background=[("selected", "#35473e")],
            foreground=[("selected", PALETTE["text"])],
        )
        style.configure(
            "TNotebook", background=PALETTE["panel"], borderwidth=0, tabmargins=(0, 0, 0, 0)
        )
        style.configure(
            "TNotebook.Tab", background=PALETTE["raised"], foreground=PALETTE["muted"],
            padding=(16, 10), font=("Aptos", 10, "bold"),
        )
        style.map(
            "TNotebook.Tab", background=[("selected", PALETTE["panel"])],
            foreground=[("selected", PALETTE["accent"])],
        )
        style.configure("Horizontal.TProgressbar", troughcolor=PALETTE["raised"])

    def _build_layout(self) -> None:
        # Outer horizontal paned window: sidebar | main
        self.outer_pane = tk.PanedWindow(self.root, orient="horizontal", sashwidth=7, bg=PALETTE["border"], bd=0, sashrelief="flat")
        self.outer_pane.pack(fill="both", expand=True)
        # Sidebar
        self.sidebar = ttk.Frame(self.outer_pane, style="Panel.TFrame", padding=(16, 18))
        self.sidebar.configure(width=286)
        self.sidebar.grid_propagate(False)
        self._build_sidebar()
        self.outer_pane.add(self.sidebar, minsize=220)
        # Main vertical pane: header+commit | viewer | history
        self.main_pane = tk.PanedWindow(self.outer_pane, orient="vertical", sashwidth=7, bg=PALETTE["border"], bd=0, sashrelief="flat")
        self.outer_pane.add(self.main_pane, minsize=600)
        # Header + commit bar (fixed)
        self.header_commit = ttk.Frame(self.main_pane, style="App.TFrame")
        self.header_commit.columnconfigure(0, weight=1)
        self._build_header()
        self._build_commit_bar()
        self.main_pane.add(self.header_commit, minsize=80, height=110)
        # Viewer/editor/diff area (resizable)
        self.viewer_frame = ttk.Frame(self.main_pane, style="App.TFrame")
        self._build_viewer()
        self.main_pane.add(self.viewer_frame, minsize=200)
        # History (resizable)
        self.history_frame = ttk.Frame(self.main_pane, style="App.TFrame")
        self._build_history()
        self.main_pane.add(self.history_frame, minsize=80, height=180)
        # Footer
        footer = ttk.Frame(self.root, style="App.TFrame")
        footer.pack(fill="x", side="bottom", pady=(0, 0))
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(footer, textvariable=self.status_var, style="Muted.TLabel").pack(side="left")
        ttk.Label(
            footer, text=f"LOCAL REPOSITORY  ·  {self.repository.root}", style="Muted.TLabel"
        ).pack(side="right")

    def _build_sidebar(self) -> None:
        brand = ttk.Frame(self.sidebar, style="Panel.TFrame")
        brand.pack(fill="x", pady=(0, 22))
        ttk.Label(
            brand, text="D", background=PALETTE["accent"], foreground=PALETTE["accent_text"],
            font=("Aptos Display", 18, "bold"), padding=(10, 3),
        ).pack(side="left", padx=(0, 10))
        brand_text = ttk.Frame(brand, style="Panel.TFrame")
        brand_text.pack(side="left", fill="x")
        ttk.Label(
            brand_text, text="DOCUGIT", style="Panel.TLabel", font=("Aptos Display", 14, "bold")
        ).pack(anchor="w")
        ttk.Label(brand_text, text="DOCUMENT HISTORY", style="PanelMuted.TLabel").pack(anchor="w")

        section = ttk.Frame(self.sidebar, style="Panel.TFrame")
        section.pack(fill="x", pady=(0, 9))
        ttk.Label(section, text="WORKSPACE", style="PanelMuted.TLabel").pack(side="left")
        self.count_var = tk.StringVar(value="0")
        ttk.Label(section, textvariable=self.count_var, style="PanelMuted.TLabel").pack(side="right")

        self.search_var = tk.StringVar()
        search = tk.Entry(
            self.sidebar, textvariable=self.search_var, bg=PALETTE["raised"],
            fg=PALETTE["text"], insertbackground=PALETTE["accent"], relief="flat",
            highlightthickness=1, highlightbackground=PALETTE["border"],
            highlightcolor=PALETTE["accent"], font=("Aptos", 10),
        )
        search.pack(fill="x", ipady=9, pady=(0, 10))
        search.insert(0, "Search documents")
        search.configure(fg=PALETTE["muted"])
        search.bind("<FocusIn>", self._clear_search_hint)
        search.bind("<KeyRelease>", lambda _event: self._render_document_list())

        list_frame = ttk.Frame(self.sidebar, style="Panel.TFrame")
        list_frame.pack(fill="both", expand=True)
        self.document_list = tk.Listbox(
            list_frame, bg=PALETTE["panel"], fg=PALETTE["text"],
            selectbackground="#35473e", selectforeground=PALETTE["accent"],
            activestyle="none", relief="flat", borderwidth=0, highlightthickness=0,
            font=("Aptos", 10), selectmode="browse",
        )
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.document_list.yview)
        self.document_list.configure(yscrollcommand=scrollbar.set)
        self.document_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.document_list.bind("<<ListboxSelect>>", self._on_document_select)

        ttk.Button(
            self.sidebar, text="＋   Add document", style="Accent.TButton",
            command=self._add_document,
        ).pack(fill="x", pady=(14, 0))
        ttk.Label(
            self.sidebar, text=f"Signed in as  {AUTHOR_NAME}", style="PanelMuted.TLabel"
        ).pack(anchor="w", pady=(15, 0))

    def _build_header(self) -> None:
        header = ttk.Frame(self.header_commit, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(1, 16))
        header.columnconfigure(0, weight=1)
        title_stack = ttk.Frame(header, style="App.TFrame")
        title_stack.grid(row=0, column=0, sticky="w")
        self.document_title_var = tk.StringVar(value="Select a document")
        ttk.Label(title_stack, textvariable=self.document_title_var, style="Title.TLabel").pack(anchor="w")
        self.document_subtitle_var = tk.StringVar(value="Your local document repository")
        ttk.Label(title_stack, textvariable=self.document_subtitle_var, style="Muted.TLabel").pack(
            anchor="w", pady=(2, 0)
        )
        self.open_button = ttk.Button(
            header, text="↗  Open working copy", style="Quiet.TButton", command=self._open_current
        )
        self.open_button.grid(row=0, column=1, sticky="e", padx=(12, 0))
        self.open_button.state(["disabled"])

    def _build_commit_bar(self) -> None:
        bar = ttk.Frame(self.header_commit, style="Panel.TFrame", padding=(14, 12))
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        bar.columnconfigure(1, weight=1)
        ttk.Label(bar, text="COMMIT TITLE", style="PanelMuted.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 14)
        )
        self.commit_title_var = tk.StringVar(value="Initial import")
        self.commit_entry = tk.Entry(
            bar, textvariable=self.commit_title_var, bg=PALETTE["raised"],
            fg=PALETTE["text"], insertbackground=PALETTE["accent"], relief="flat",
            highlightthickness=1, highlightbackground=PALETTE["border"],
            highlightcolor=PALETTE["accent"], font=("Aptos", 10),
        )
        self.commit_entry.grid(row=0, column=1, sticky="ew", ipady=8, padx=(0, 12))
        self.commit_button = ttk.Button(
            bar, text="Commit working copy", style="Accent.TButton", command=self._commit_version
        )
        self.commit_button.grid(row=0, column=2)
        self.commit_button.state(["disabled"])
        self.link_original_button = ttk.Button(
            bar, text="Link original", style="Quiet.TButton", command=self._link_original
        )
        self.link_original_button.grid(row=0, column=3, padx=(8, 0))
        self.link_original_button.state(["disabled"])
        self.publish_button = ttk.Button(
            bar, text="Publish", style="Quiet.TButton", command=self._publish_current
        )
        self.publish_button.grid(row=0, column=4, padx=(8, 0))
        self.publish_button.state(["disabled"])

    def _build_viewer(self) -> None:
        self.tabs = ttk.Notebook(self.viewer_frame)
        self.tabs.pack(fill="both", expand=True)
        self.preview_tab = ttk.Frame(self.tabs, style="Panel.TFrame")
        self.diff_tab = ttk.Frame(self.tabs, style="Panel.TFrame")
        self.edit_tab = ttk.Frame(self.tabs, style="Panel.TFrame")
        self.tabs.add(self.preview_tab, text="  Preview  ")
        self.tabs.add(self.diff_tab, text="  Diff  ")
        self.tabs.add(self.edit_tab, text="  Edit  ")
        self.preview_caption = tk.StringVar(value="DOCUMENT PREVIEW")
        self._make_text_view(self.preview_tab, self.preview_caption)
        self.diff_caption = tk.StringVar(value="SELECT VERSIONS TO COMPARE")
        self._make_side_by_side_diff_view(self.diff_tab, self.diff_caption)
        self._make_editor_view()
        self._set_text(self.preview_text, "Add a DOCX or XLSX file to see its contents here.")

    def _make_side_by_side_diff_view(self, parent: ttk.Frame, caption_var: tk.StringVar) -> None:
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)
        caption = tk.Label(
            parent, textvariable=caption_var, bg=PALETTE["panel"], fg=PALETTE["muted"],
            font=("Aptos", 9, "bold"), anchor="w", padx=15, pady=12,
        )
        caption.grid(row=0, column=0, sticky="ew", columnspan=2)
        diff_pane = tk.PanedWindow(parent, orient="horizontal", sashwidth=5, bg=PALETTE["border"], bd=0, sashrelief="flat")
        diff_pane.grid(row=1, column=0, sticky="nsew")
        self.diff_scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self._scroll_diff)
        self.diff_scrollbar.grid(row=1, column=1, sticky="ns")
        # Left: old version
        left_frame = ttk.Frame(diff_pane, style="Panel.TFrame")
        right_frame = ttk.Frame(diff_pane, style="Panel.TFrame")
        diff_pane.add(left_frame, minsize=200)
        diff_pane.add(right_frame, minsize=200)
        left_label = tk.Label(left_frame, text="← Old Version", bg=PALETTE["panel"], fg=PALETTE["muted"], font=("Aptos", 9, "bold"), anchor="w", padx=10, pady=2)
        left_label.pack(fill="x")
        right_label = tk.Label(right_frame, text="New Version →", bg=PALETTE["panel"], fg=PALETTE["muted"], font=("Aptos", 9, "bold"), anchor="e", padx=10, pady=2)
        right_label.pack(fill="x")
        left_body = ttk.Frame(left_frame, style="Panel.TFrame")
        right_body = ttk.Frame(right_frame, style="Panel.TFrame")
        left_body.pack(fill="both", expand=True)
        right_body.pack(fill="both", expand=True)
        for body in (left_body, right_body):
            body.rowconfigure(0, weight=1)
            body.columnconfigure(0, weight=1)
        self.diff_left_text = tk.Text(left_frame, wrap="none", bg=PALETTE["panel"], fg=PALETTE["text"],
            insertbackground=PALETTE["accent"], selectbackground="#35473e",
            relief="flat", borderwidth=0, padx=0, pady=8,
            font=("Cascadia Mono", 10), state="disabled", width=1)
        self.diff_right_text = tk.Text(right_frame, wrap="none", bg=PALETTE["panel"], fg=PALETTE["text"],
            insertbackground=PALETTE["accent"], selectbackground="#35473e",
            relief="flat", borderwidth=0, padx=0, pady=8,
            font=("Cascadia Mono", 10), state="disabled", width=1)
        self.diff_left_text.configure(yscrollcommand=lambda first, last: self._diff_scrolled("left", first, last))
        self.diff_right_text.configure(yscrollcommand=lambda first, last: self._diff_scrolled("right", first, last))
        self.diff_left_text.grid(in_=left_body, row=0, column=0, sticky="nsew")
        self.diff_right_text.grid(in_=right_body, row=0, column=0, sticky="nsew")
        left_xscroll = ttk.Scrollbar(left_body, orient="horizontal", command=self.diff_left_text.xview)
        right_xscroll = ttk.Scrollbar(right_body, orient="horizontal", command=self.diff_right_text.xview)
        left_xscroll.grid(row=1, column=0, sticky="ew")
        right_xscroll.grid(row=1, column=0, sticky="ew")
        self.diff_left_text.configure(xscrollcommand=left_xscroll.set)
        self.diff_right_text.configure(xscrollcommand=right_xscroll.set)
        for text in (self.diff_left_text, self.diff_right_text):
            text.bind("<MouseWheel>", self._diff_mousewheel)
            text.bind("<Button-4>", lambda _event: self._diff_scroll_units(-3))
            text.bind("<Button-5>", lambda _event: self._diff_scroll_units(3))
        # Color tags
        for text in (self.diff_left_text, self.diff_right_text):
            text.tag_configure("added", background="#1b2b20", foreground="#b7ed9b")
            text.tag_configure("removed", background="#321f20", foreground="#ffaaa5")
            text.tag_configure("changed", background="#23303b", foreground="#c2dcf2")
            text.tag_configure("empty", background=PALETTE["panel"], foreground=PALETTE["muted"])
            text.tag_configure("line_number", foreground="#718078")

    def _diff_scrolled(self, side: str, first: str, last: str) -> None:
        self.diff_scrollbar.set(first, last)
        if getattr(self, "syncing_diff_scroll", False):
            return
        self.syncing_diff_scroll = True
        try:
            peer = self.diff_right_text if side == "left" else self.diff_left_text
            peer.yview_moveto(first)
        finally:
            self.syncing_diff_scroll = False

    def _scroll_diff(self, *args: str) -> None:
        self.diff_left_text.yview(*args)

    def _diff_scroll_units(self, units: int) -> str:
        self.diff_left_text.yview_scroll(units, "units")
        return "break"

    def _diff_mousewheel(self, event: tk.Event) -> str:
        delta = int(event.delta)
        if delta == 0:
            return "break"
        units = -3 if delta > 0 else 3
        if abs(delta) >= 120:
            units *= max(1, abs(delta) // 120)
        self._diff_scroll_units(units)
        return "break"

    def _make_text_view(self, parent: ttk.Frame, caption_var: tk.StringVar, is_diff: bool = False) -> None:
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)
        caption = tk.Label(
            parent, textvariable=caption_var, bg=PALETTE["panel"], fg=PALETTE["muted"],
            font=("Aptos", 9, "bold"), anchor="w", padx=15, pady=12,
        )
        caption.grid(row=0, column=0, sticky="ew")
        text_frame = ttk.Frame(parent, style="Panel.TFrame")
        text_frame.grid(row=1, column=0, sticky="nsew")
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)
        text = tk.Text(
            text_frame, wrap="none", bg=PALETTE["panel"], fg=PALETTE["text"],
            insertbackground=PALETTE["accent"], selectbackground="#35473e",
            relief="flat", borderwidth=0, padx=16, pady=12,
            font=("Cascadia Mono", 10), state="disabled",
        )
        y_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=text.yview)
        x_scroll = ttk.Scrollbar(text_frame, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        if is_diff:
            text.tag_configure("added", foreground=PALETTE["added"])
            text.tag_configure("removed", foreground=PALETTE["removed"])
            text.tag_configure("header", foreground=PALETTE["blue"])
            self.diff_text = text
        else:
            self.preview_text = text

    def _make_editor_view(self) -> None:
        self.edit_tab.rowconfigure(1, weight=1)
        self.edit_tab.columnconfigure(0, weight=1)
        toolbar = ttk.Frame(self.edit_tab, style="Panel.TFrame")
        toolbar.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 8))
        ttk.Label(
            toolbar, text="EDIT TEXT AND CELL VALUES", style="PanelMuted.TLabel"
        ).pack(side="left")
        self.save_editor_button = ttk.Button(
            toolbar, text="Save working copy", style="Quiet.TButton", command=self._save_editor
        )
        self.save_editor_button.pack(side="right")
        self.editor_text = tk.Text(
            self.edit_tab, wrap="none", bg=PALETTE["panel"], fg=PALETTE["text"],
            insertbackground=PALETTE["accent"], selectbackground="#35473e",
            relief="flat", borderwidth=0, padx=16, pady=12,
            font=("Cascadia Mono", 10), state="disabled",
        )
        self.editor_text.grid(row=1, column=0, sticky="nsew", padx=(0, 12), pady=(0, 12))
        self.editor_text.edit_modified(False)
        self.editor_text.bind("<<Modified>>", self._mark_editor_dirty)

    def _build_history(self) -> None:
        section = ttk.Frame(self.history_frame, style="App.TFrame")
        section.grid(row=3, column=0, sticky="ew")
        section.columnconfigure(0, weight=1)
        heading = ttk.Frame(section, style="App.TFrame")
        heading.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(heading, text="VERSION HISTORY", style="Muted.TLabel").pack(side="left")
        self.compare_button = ttk.Button(
            heading, text="Compare", style="Quiet.TButton", command=self._compare_selected
        )
        self.compare_button.pack(side="right", padx=(8, 0))
        self.restore_button = ttk.Button(
            heading, text="Restore selected", style="Quiet.TButton", command=self._restore_selected
        )
        self.restore_button.pack(side="right")
        self.version_tree = ttk.Treeview(
            section, columns=("version", "title", "author", "time", "size"),
            show="headings", height=5, selectmode="extended",
        )
        headings = {
            "version": ("VERSION", 88, "center"),
            "title": ("COMMIT", 350, "w"),
            "author": ("AUTHOR", 120, "w"),
            "time": ("TIMESTAMP", 190, "w"),
            "size": ("SIZE", 90, "e"),
        }
        for column, (label, width, anchor) in headings.items():
            self.version_tree.heading(column, text=label)
            self.version_tree.column(column, width=width, anchor=anchor, stretch=column == "title")
        self.version_tree.grid(row=1, column=0, sticky="ew")
        self.version_tree.bind("<<TreeviewSelect>>", self._on_version_select)

    def _clear_search_hint(self, _event: tk.Event) -> None:
        if self.search_var.get() == "Search documents":
            self.search_var.set("")
            self.search_box = self.root.focus_get()
            if isinstance(self.search_box, tk.Entry):
                self.search_box.configure(fg=PALETTE["text"])

    def _refresh_documents(self, preferred_id: str | None = None) -> None:
        self.documents = self.repository.list_documents()
        self.count_var.set(str(len(self.documents)))
        self._render_document_list(preferred_id)

    def _render_document_list(self, preferred_id: str | None = None) -> None:
        if preferred_id is None:
            preferred_id = self.selected_document_id
        query = self.search_var.get().strip().lower()
        if query == "search documents":
            query = ""
        self.visible_documents = [
            document for document in self.documents if query in document["file_name"].lower()
        ]
        self.document_list.delete(0, "end")
        selected_index = None
        for index, document in enumerate(self.visible_documents):
            self.document_list.insert(
                "end", f"  {document['file_name']}\n    v{document['current_version']:04d}"
            )
            if document["id"] == preferred_id:
                selected_index = index
        if selected_index is not None:
            self.document_list.selection_set(selected_index)
            self.document_list.activate(selected_index)
            self.document_list.see(selected_index)
            if self.selected_document_id != preferred_id:
                self._select_document(preferred_id)
        elif not self.visible_documents:
            if self.selected_document_id is None:
                self._show_empty_state()
        elif self.selected_document_id is None:
            self.document_list.selection_set(0)
            self._select_document(self.visible_documents[0]["id"])

    def _on_document_select(self, _event: tk.Event) -> None:
        selection = self.document_list.curselection()
        if selection:
            next_id = self.visible_documents[selection[0]]["id"]
            if next_id != self.selected_document_id and self.editor_dirty:
                choice = messagebox.askyesnocancel(
                    "Unsaved edits",
                    "Save edits to the current working copy before switching documents?",
                    parent=self.root,
                )
                if choice is None:
                    self._restore_document_selection()
                    return
                if choice:
                    try:
                        self._save_editor()
                    except Exception as error:
                        messagebox.showerror("Could not save edits", str(error), parent=self.root)
                        self._restore_document_selection()
                        return
                else:
                    self.editor_dirty = False
            self._select_document(next_id)

    def _restore_document_selection(self) -> None:
        for index, document in enumerate(self.visible_documents):
            if document["id"] == self.selected_document_id:
                self.document_list.selection_clear(0, "end")
                self.document_list.selection_set(index)
                self.document_list.activate(index)
                break

    def _select_document(self, document_id: str) -> None:
        self.selected_document_id = document_id
        document = self.repository.get_document(document_id)
        self.document_title_var.set(document["file_name"])
        self.document_subtitle_var.set(
            f"{document['extension'][1:].upper()}  ·  Current version v{document['current_version']:04d}"
        )
        self._load_editor_content()
        self.open_button.state(["!disabled"])
        self.commit_button.state(["!disabled"])
        self.link_original_button.state(["!disabled"])
        if document["source_path"]:
            self.publish_button.state(["!disabled"])
        else:
            self.publish_button.state(["disabled"])
        self._refresh_history()
        self.status_var.set(f"Selected {document['file_name']}")

    def _show_empty_state(self) -> None:
        self.document_title_var.set("Select a document")
        self.document_subtitle_var.set("Your local document repository")
        self.open_button.state(["disabled"])
        self.commit_button.state(["disabled"])
        self.link_original_button.state(["disabled"])
        self.publish_button.state(["disabled"])
        for item in self.version_tree.get_children():
            self.version_tree.delete(item)
        self._set_text(self.preview_text, "Add a DOCX or XLSX file to see its contents here.")
        self.preview_caption.set("DOCUMENT PREVIEW")
        self.editor_text.configure(state="normal")
        self.editor_text.delete("1.0", "end")
        self.editor_text.configure(state="disabled")
        self.editor_dirty = False

    def _refresh_history(self, selected_version: int | None = None) -> None:
        if not self.selected_document_id:
            return
        for item in self.version_tree.get_children():
            self.version_tree.delete(item)
        versions = self.repository.list_versions(self.selected_document_id)
        for version in versions:
            timestamp = datetime.fromisoformat(version["timestamp"]).astimezone().strftime(
                "%b %d, %Y  %H:%M"
            )
            self.version_tree.insert(
                "", "end", iid=str(version["version_number"]),
                values=(
                    f"v{version['version_number']:04d}", version["commit_title"],
                    version["author"], timestamp, self._format_size(version["file_size"]),
                ),
            )
        if versions:
            version_number = selected_version or versions[0]["version_number"]
            iid = str(version_number)
            self.version_tree.selection_set(iid)
            self.version_tree.focus(iid)
            self._show_version(version_number)

    def _show_version(self, version_number: int) -> None:
        version = self.repository.get_version(self.selected_document_id, version_number)
        from docugit.extractors import extract_text

        content = extract_text(self.repository.version_path(version))
        self.preview_caption.set(
            f"VERSION v{version_number:04d}  /  {version['commit_title']}  /  {version['author']}"
        )
        self._set_text(self.preview_text, content or "This document has no readable text content.")

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"

    @staticmethod
    def _set_text(widget: tk.Text, content: str, diff: bool = False) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        if diff:
            for line_number, line in enumerate(content.splitlines(), start=1):
                tag = "added" if line.startswith("+") else "removed" if line.startswith("-") else "header" if line.startswith("@@") else None
                if tag:
                    widget.tag_add(tag, f"{line_number}.0", f"{line_number}.end")
        widget.configure(state="disabled")

    def _show_side_by_side_diff(self, old_lines, new_lines):
        import difflib
        sm = difflib.SequenceMatcher(None, old_lines, new_lines)
        left_lines, right_lines = [], []
        left_tags, right_tags = [], []
        left_numbers, right_numbers = [], []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for i in range(i2 - i1):
                    left_lines.append(old_lines[i1 + i])
                    right_lines.append(new_lines[j1 + i])
                    left_tags.append(None)
                    right_tags.append(None)
                    left_numbers.append(i1 + i + 1)
                    right_numbers.append(j1 + i + 1)
            elif tag == "replace":
                maxlen = max(i2 - i1, j2 - j1)
                for i in range(maxlen):
                    l = old_lines[i1 + i] if i1 + i < i2 else ""
                    r = new_lines[j1 + i] if j1 + i < j2 else ""
                    left_lines.append(l)
                    right_lines.append(r)
                    left_tags.append("changed" if l and r else ("removed" if l else "empty"))
                    right_tags.append("changed" if l and r else ("added" if r else "empty"))
                    left_numbers.append(i1 + i + 1 if l else None)
                    right_numbers.append(j1 + i + 1 if r else None)
            elif tag == "delete":
                for i in range(i2 - i1):
                    left_lines.append(old_lines[i1 + i])
                    right_lines.append("")
                    left_tags.append("removed")
                    right_tags.append("empty")
                    left_numbers.append(i1 + i + 1)
                    right_numbers.append(None)
            elif tag == "insert":
                for i in range(j2 - j1):
                    left_lines.append("")
                    right_lines.append(new_lines[j1 + i])
                    left_tags.append("empty")
                    right_tags.append("added")
                    left_numbers.append(None)
                    right_numbers.append(j1 + i + 1)
        # Display
        self.diff_left_text.configure(state="normal")
        self.diff_right_text.configure(state="normal")
        self.diff_left_text.delete("1.0", "end")
        self.diff_right_text.delete("1.0", "end")
        for idx, (line, tag, number) in enumerate(zip(left_lines, left_tags, left_numbers), 1):
            prefix = f"{number:>4} " if number is not None else "     "
            self.diff_left_text.insert("end", prefix + line + "\n")
            self.diff_left_text.tag_add("line_number", f"{idx}.0", f"{idx}.5")
            if tag:
                self.diff_left_text.tag_add(tag, f"{idx}.0", f"{idx}.end")
        for idx, (line, tag, number) in enumerate(zip(right_lines, right_tags, right_numbers), 1):
            prefix = f"{number:>4} " if number is not None else "     "
            self.diff_right_text.insert("end", prefix + line + "\n")
            self.diff_right_text.tag_add("line_number", f"{idx}.0", f"{idx}.5")
            if tag:
                self.diff_right_text.tag_add(tag, f"{idx}.0", f"{idx}.end")
        self.diff_left_text.configure(state="disabled")
        self.diff_right_text.configure(state="disabled")

    def _load_editor_content(self) -> None:
        if not self.selected_document_id:
            return
        if self.editor_save_after_id is not None:
            self.root.after_cancel(self.editor_save_after_id)
            self.editor_save_after_id = None
        content = extract_text(self.repository.current_path(self.selected_document_id))
        self.editor_text.configure(state="normal")
        self.editor_text.delete("1.0", "end")
        self.editor_text.insert("1.0", content)
        self.editor_text.edit_modified(False)
        self.editor_dirty = False

    def _mark_editor_dirty(self, _event: tk.Event) -> None:
        if not self.editor_text.edit_modified():
            return
        self.editor_text.edit_modified(False)
        self.editor_dirty = True
        if self.editor_save_after_id is not None:
            self.root.after_cancel(self.editor_save_after_id)
        self.editor_save_after_id = self.root.after(900, self._auto_save_editor)

    def _auto_save_editor(self) -> None:
        self.editor_save_after_id = None
        try:
            self._save_editor()
        except Exception as error:
            self.status_var.set(f"Edits not saved: {error}")

    def _save_editor(self) -> None:
        if self.editor_save_after_id is not None:
            self.root.after_cancel(self.editor_save_after_id)
            self.editor_save_after_id = None
        if not self.selected_document_id or not self.editor_dirty:
            return
        content = self.editor_text.get("1.0", "end-1c")
        working_copy = self.repository.current_path(self.selected_document_id)
        replace_text(working_copy, content)
        self.editor_text.edit_modified(False)
        self.editor_dirty = False
        self._set_text(self.preview_text, extract_text(working_copy))
        self.preview_caption.set("UNCOMMITTED WORKING COPY")
        self.status_var.set(f"Saved edits to {working_copy.name}")

    def _close_app(self) -> None:
        if self.editor_dirty:
            choice = messagebox.askyesnocancel(
                "Unsaved edits", "Save edits to the tracked working copy before closing?",
                parent=self.root,
            )
            if choice is None:
                return
            if choice:
                try:
                    self._save_editor()
                except Exception as error:
                    messagebox.showerror("Could not save edits", str(error), parent=self.root)
                    return
        self.root.destroy()

    def _add_document(self) -> None:
        source = filedialog.askopenfilename(
            title="Add document to DocuGit",
            filetypes=[("Word and Excel documents", "*.docx *.xlsx"), ("All files", "*.*")],
        )
        if not source:
            return
        try:
            document = self.repository.add_document(
                source, self.commit_title_var.get(), AUTHOR_NAME
            )
            self.commit_title_var.set("Update document")
            self._refresh_documents(document["id"])
            self.status_var.set(f"Added {document['file_name']} as v0001")
        except Exception as error:
            messagebox.showerror("Could not add document", str(error), parent=self.root)

    def _commit_version(self) -> None:
        if not self.selected_document_id:
            return
        try:
            self._save_editor()
            version = self.repository.commit_current(
                self.selected_document_id, self.commit_title_var.get(), AUTHOR_NAME
            )
            self._refresh_documents(self.selected_document_id)
            self._refresh_history(version["version_number"])
            self._load_editor_content()
            self.commit_title_var.set("Update document")
            self.status_var.set(f"Committed v{version['version_number']:04d} by {AUTHOR_NAME}")
        except Exception as error:
            messagebox.showerror("Could not commit version", str(error), parent=self.root)

    def _link_original(self) -> None:
        if not self.selected_document_id:
            return
        document = self.repository.get_document(self.selected_document_id)
        source = filedialog.askopenfilename(
            title="Link this document to its original",
            filetypes=[("Matching document", f"*{document['extension']}")],
        )
        if not source:
            return
        try:
            original = self.repository.set_original_path(self.selected_document_id, source)
            self.publish_button.state(["!disabled"])
            self.status_var.set(f"Original linked: {original}")
        except Exception as error:
            messagebox.showerror("Could not link original", str(error), parent=self.root)

    def _publish_current(self) -> None:
        if not self.selected_document_id:
            return
        document = self.repository.get_document(self.selected_document_id)
        if not messagebox.askyesno(
            "Publish document",
            f"Commit any uncommitted edits, archive the current original, and replace it at\n"
            f"{document['source_path']}?",
            parent=self.root,
        ):
            return
        try:
            self._save_editor()
            result = self.repository.publish_current(
                self.selected_document_id, self.commit_title_var.get(), AUTHOR_NAME
            )
            version = result["version"]
            self._refresh_documents(self.selected_document_id)
            self._refresh_history(version["version_number"])
            self._load_editor_content()
            self.commit_title_var.set("Update document")
            self.status_var.set(f"Published v{version['version_number']:04d} to original")
        except Exception as error:
            messagebox.showerror("Could not publish document", str(error), parent=self.root)

    def _on_version_select(self, _event: tk.Event) -> None:
        selection = self.version_tree.selection()
        if selection and self.selected_document_id:
            self._show_version(int(selection[0]))

    def _compare_selected(self) -> None:
        if not self.selected_document_id:
            return
        selected = sorted(int(item) for item in self.version_tree.selection())
        if len(selected) >= 2:
            old_number, new_number = selected[0], selected[-1]
        elif len(selected) == 1 and selected[0] > 1:
            new_number = selected[0]
            old_number = new_number - 1
        else:
            messagebox.showinfo(
                "Nothing to compare", "Select two versions, or select a version with an earlier version.",
                parent=self.root,
            )
            return
        try:
            old_version = self.repository.get_version(self.selected_document_id, old_number)
            new_version = self.repository.get_version(self.selected_document_id, new_number)
            from docugit.extractors import extract_text
            old_lines = extract_text(self.repository.version_path(old_version)).splitlines()
            new_lines = extract_text(self.repository.version_path(new_version)).splitlines()
            self.diff_caption.set(f"CHANGES  /  v{old_number:04d}  →  v{new_number:04d}")
            self._show_side_by_side_diff(old_lines, new_lines)
            self.tabs.select(self.diff_tab)
            self.status_var.set(f"Comparing v{old_number:04d} to v{new_number:04d}")
        except Exception as error:
            messagebox.showerror("Could not compare versions", str(error), parent=self.root)

    def _restore_selected(self) -> None:
        if not self.selected_document_id:
            return
        selection = self.version_tree.selection()
        if not selection:
            messagebox.showinfo("Choose a version", "Select a version to restore.", parent=self.root)
            return
        version_number = int(selection[0])
        if not messagebox.askyesno(
            "Restore version",
            f"Restore v{version_number:04d} as a new version? The current document will be replaced.",
            parent=self.root,
        ):
            return
        try:
            version = self.repository.restore_version(
                self.selected_document_id, version_number, AUTHOR_NAME
            )
            self._refresh_documents(self.selected_document_id)
            self._refresh_history(version["version_number"])
            self._load_editor_content()
            self.status_var.set(f"Restored as v{version['version_number']:04d}")
        except Exception as error:
            messagebox.showerror("Could not restore version", str(error), parent=self.root)

    def _open_current(self) -> None:
        if not self.selected_document_id:
            return
        path = self.repository.current_path(self.selected_document_id)
        try:
            os.startfile(path)
            self.status_var.set(f"Opened working copy: {path}")
        except OSError as error:
            messagebox.showerror("Could not open document", str(error), parent=self.root)


def main() -> None:
    root = tk.Tk()
    app = DocuGitApp(root)
    root.protocol("WM_DELETE_WINDOW", app._close_app)
    root.mainloop()