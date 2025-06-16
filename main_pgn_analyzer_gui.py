# ===== START OF FILE main_pgn_analyzer_gui.py =====
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import os
import sys
import logging
import threading

from engines import SearchlessEngineManager, SEARCHLESS_ENGINES_AVAILABLE
from constants import IMAGE_PATH, DEFAULT_BOARD_SIZE_PX, LOG_FILENAME, LOG_FORMAT, DEFAULT_PLAYER_NAME_TO_TRACK
from chess_board_widget import ChessBoardWidget
from blunder_feedback_panel import BlunderFeedbackPanel
from pgn_analyzer_controller import PgnAnalyzerController
import chess_draw_utils as cdu

class MainPgnAnalyzerGUI:
    def __init__(self, root_tk_window):
        self.root = root_tk_window
        self.root.title("PGN Game Analyzer")

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.engine_manager = SearchlessEngineManager()
        self.controller = None

        self._create_main_widgets_layout()
        self._initialize_application_logic()

        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

    def _create_main_widgets_layout(self):
        main_paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned_window.grid(row=0, column=0, sticky="nsew")

        left_pane = ttk.Frame(main_paned_window, padding=5)
        main_paned_window.add(left_pane, weight=2)
        left_pane.grid_rowconfigure(4, weight=1) # Move list expands
        left_pane.grid_columnconfigure(0, weight=1)

        pgn_input_frame = ttk.LabelFrame(left_pane, text="PGN Input & Analysis", padding=5)
        pgn_input_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        pgn_input_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(pgn_input_frame, text="Player Name:").grid(row=0, column=0, sticky="w", padx=2)
        self.player_name_var = tk.StringVar(value=DEFAULT_PLAYER_NAME_TO_TRACK)
        self.player_name_entry = ttk.Entry(pgn_input_frame, textvariable=self.player_name_var)
        self.player_name_entry.grid(row=0, column=1, sticky="ew", padx=2)
        
        self.analyze_btn = ttk.Button(pgn_input_frame, text="Analyze Game", command=self._gui_action_analyze_game)
        self.analyze_btn.grid(row=0, column=2, sticky="e", padx=5)

        self.pgn_input_text = scrolledtext.ScrolledText(left_pane, height=8, width=40, wrap=tk.WORD)
        self.pgn_input_text.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=5)

        nav_frame = ttk.LabelFrame(left_pane, text="Navigation", padding=5)
        nav_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        for i in range(4): nav_frame.grid_columnconfigure(i, weight=1)

        self.nav_start_btn = ttk.Button(nav_frame, text="<< Start", command=self._gui_action_nav_start)
        self.nav_start_btn.grid(row=0, column=0, sticky="ew", padx=2)
        self.nav_prev_btn = ttk.Button(nav_frame, text="< Prev", command=self._gui_action_nav_prev)
        self.nav_prev_btn.grid(row=0, column=1, sticky="ew", padx=2)
        self.nav_next_btn = ttk.Button(nav_frame, text="Next >", command=self._gui_action_nav_next)
        self.nav_next_btn.grid(row=0, column=2, sticky="ew", padx=2)
        self.nav_end_btn = ttk.Button(nav_frame, text="End >>", command=self._gui_action_nav_end)
        self.nav_end_btn.grid(row=0, column=3, sticky="ew", padx=2)
        
        play_frame = ttk.LabelFrame(left_pane, text="Interactive Play", padding=5)
        play_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)
        play_frame.grid_columnconfigure(0, weight=1)
        play_frame.grid_columnconfigure(1, weight=1)
        
        self.play_from_here_btn = ttk.Button(play_frame, text="Play From Here", command=self._gui_action_play_from_here)
        self.play_from_here_btn.grid(row=0, column=0, sticky="ew", padx=2)
        self.return_to_analysis_btn = ttk.Button(play_frame, text="Return to Analysis", command=self._gui_action_return_to_analysis)
        self.return_to_analysis_btn.grid(row=0, column=1, sticky="ew", padx=2)

        move_list_frame = ttk.LabelFrame(left_pane, text="Game Moves", padding=5)
        move_list_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=5)
        move_list_frame.grid_rowconfigure(0, weight=1)
        move_list_frame.grid_columnconfigure(0, weight=1)

        self.move_listbox = tk.Listbox(move_list_frame, font=("Courier New", 11))
        self.move_listbox.grid(row=0, column=0, sticky="nsew")
        self.move_listbox.bind("<<ListboxSelect>>", self._gui_action_on_move_select)
        
        scrollbar = ttk.Scrollbar(move_list_frame, orient=tk.VERTICAL, command=self.move_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.move_listbox.config(yscrollcommand=scrollbar.set)
        
        center_pane = ttk.Frame(main_paned_window, padding=5)
        main_paned_window.add(center_pane, weight=3)
        center_pane.grid_rowconfigure(0, weight=1)
        center_pane.grid_columnconfigure(0, weight=1)
        
        self.board_widget = ChessBoardWidget(parent=center_pane, image_path=IMAGE_PATH, on_resize_callback=self._gui_action_handle_resize)
        self.board_widget.frame.grid(row=0, column=0, sticky="nsew")

        right_pane = ttk.Frame(main_paned_window, padding=5)
        main_paned_window.add(right_pane, weight=2)
        self.feedback_panel = BlunderFeedbackPanel(right_pane)

        status_frame = ttk.Frame(self.root, relief=tk.SUNKEN)
        status_frame.grid(row=1, column=0, sticky="ew")
        
        self.status_var = tk.StringVar(value="Ready. Paste a PGN and click Analyze.")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor=tk.W)
        status_label.pack(side=tk.LEFT, padx=5, pady=2, fill=tk.X, expand=True)
        self.progress_bar = ttk.Progressbar(status_frame, orient='horizontal', mode='determinate')

    def _initialize_application_logic(self):
        self.status_var.set("Loading engines...")
        self.root.update_idletasks()

        if not SEARCHLESS_ENGINES_AVAILABLE:
            messagebox.showerror("Engine Error", "Searchless_chess library not found."); self.root.destroy(); return
        if not self.engine_manager.load_engines(load_136m_flag=True) or not self.engine_manager.engine_9M or not self.engine_manager.engine_136M:
            messagebox.showerror("Engine Error", "Could not load required engines."); self.root.destroy(); return
        
        gui_callbacks = {
            'update_status': self.update_status,
            'update_progress': self.update_progress,
            'populate_move_list': self.populate_move_list,
            'show_error': lambda title, msg: messagebox.showerror(title, msg),
            'update_move_selection': self.update_move_list_selection,
            'update_button_states': self._update_button_states
        }

        self.controller = PgnAnalyzerController(
            board_widget=self.board_widget,
            feedback_panel=self.feedback_panel,
            engine_manager=self.engine_manager,
            gui_callback_manager=gui_callbacks
        )
        self.update_status("Ready. Paste a PGN and click Analyze.")
        self._update_button_states()

    def _update_button_states(self):
        analysis_done = bool(self.controller and self.controller.analysis_results)
        in_play_mode = self.controller and self.controller.interaction_mode == 'play'

        nav_state = tk.NORMAL if analysis_done and not in_play_mode else tk.DISABLED
        self.nav_start_btn.config(state=nav_state)
        self.nav_prev_btn.config(state=tk.NORMAL if analysis_done and self.controller.current_move_index > 0 and not in_play_mode else tk.DISABLED)
        self.nav_next_btn.config(state=tk.NORMAL if analysis_done and self.controller.current_move_index < len(self.controller.analysis_results) - 1 and not in_play_mode else tk.DISABLED)
        self.nav_end_btn.config(state=nav_state)
        self.analyze_btn.config(state=tk.NORMAL if not in_play_mode else tk.DISABLED)
        self.move_listbox.config(state=tk.NORMAL if not in_play_mode else tk.DISABLED)
        
        self.play_from_here_btn.config(state=tk.NORMAL if analysis_done and not in_play_mode else tk.DISABLED)
        self.return_to_analysis_btn.config(state=tk.NORMAL if in_play_mode else tk.DISABLED)

    def _gui_action_analyze_game(self):
        pgn_text = self.pgn_input_text.get("1.0", tk.END)
        player_name = self.player_name_var.get()
        if not pgn_text.strip() or not player_name.strip():
            messagebox.showwarning("Input Required", "Please paste a PGN and enter a player name."); return

        self.analyze_btn.config(state=tk.DISABLED)
        self._update_button_states()
        self.move_listbox.delete(0, tk.END)

        analysis_thread = threading.Thread(target=self.run_analysis_thread, args=(pgn_text, player_name), daemon=True)
        analysis_thread.start()
        
    def run_analysis_thread(self, pgn_text, player_name):
        self.controller.load_and_analyze_pgn(pgn_text, player_name)
        self.root.after(10, self._update_button_states)
        self.root.after(10, lambda: self.progress_bar.pack_forget())

    def _gui_action_on_move_select(self, event):
        w = event.widget
        if not w.curselection(): return
        if self.controller: self.controller.navigate_to_move(int(w.curselection()[0]))

    def _gui_action_nav_start(self):
        if self.controller: self.controller.navigate_to_move(0)
    def _gui_action_nav_prev(self):
        if self.controller: self.controller.navigate_to_move(self.controller.current_move_index - 1)
    def _gui_action_nav_next(self):
        if self.controller: self.controller.navigate_to_move(self.controller.current_move_index + 1)
    def _gui_action_nav_end(self):
        if self.controller and self.controller.analysis_results: self.controller.navigate_to_move(len(self.controller.analysis_results) - 1)
    
    def _gui_action_play_from_here(self):
        if self.controller: self.controller.action_play_from_here()
    def _gui_action_return_to_analysis(self):
        if self.controller: self.controller.action_return_to_analysis()

    def _gui_action_handle_resize(self):
        if self.controller: self.controller.handle_board_resize()
    
    def update_status(self, text):
        self.root.after(0, lambda: self.status_var.set(text))

    def update_progress(self, current_val, max_val):
        def task():
            if not self.progress_bar.winfo_ismapped(): self.progress_bar.pack(side=tk.RIGHT, padx=5, pady=2, fill=tk.X, expand=True)
            self.progress_bar['maximum'] = max_val
            self.progress_bar['value'] = current_val
        self.root.after(0, task)

    def populate_move_list(self, analysis_results):
        def task():
            self.move_listbox.delete(0, tk.END)
            for i, result in enumerate(analysis_results):
                move_num_str = f"{(result['ply'] + 1) // 2}.{'..' if result['ply'] % 2 == 0 else ''}"
                display_text = f"{move_num_str:<5} {result['move_san']:<8} {result.get('quality_symbol', '')}"
                self.move_listbox.insert(tk.END, display_text)
                if not result['is_tracked_player_move']: self.move_listbox.itemconfig(i, {'fg': 'grey'})
        self.root.after(0, task)
    
    def update_move_list_selection(self, index):
        def task():
            self.move_listbox.selection_clear(0, tk.END)
            self.move_listbox.selection_set(index)
            self.move_listbox.activate(index)
            self.move_listbox.see(index)
            self._update_button_states()
        self.root.after(0, task)

def setup_logging():
    logging.basicConfig(filename=LOG_FILENAME, filemode='a', level=logging.DEBUG, format=LOG_FORMAT)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s: (%(module)s.%(funcName)s) %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

if __name__ == '__main__':
    setup_logging()
    root = tk.Tk()
    app = MainPgnAnalyzerGUI(root)
    root.mainloop()
# ===== END OF FILE main_pgn_analyzer_gui.py =====