import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import logging
import chess # For chess.WHITE, chess.BLACK constants

from constants import (
    IMAGE_PATH, MIN_BOARD_SIZE_PX, DEFAULT_BOARD_SIZE_PX,
    LOG_FILENAME, LOG_FORMAT
)

from engines import SearchlessEngineManager, SEARCHLESS_ENGINES_AVAILABLE
from chess_board_widget import ChessBoardWidget
from blunder_feedback_panel import BlunderFeedbackPanel # Renaming this or its usage might be a future step
from game_controller import GameController 

class MainChessVsEngineGUI:
    def __init__(self, root_tk_window):
        self.root = root_tk_window
        self.root.title("Chess vs 9M Engine")

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.engine_manager = SearchlessEngineManager()
        self.controller = None 
        self.show_hints_var_tk = tk.BooleanVar(value=False)

        self._create_main_widgets_layout()
        self._initialize_application_logic(self.root) 

        self.root.protocol("WM_DELETE_WINDOW", self._on_application_window_close)
        print("✅ GUI Initialized: Chess vs 9M Engine")

    def _create_main_widgets_layout(self):
        main_paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned_window.grid(row=0, column=0, sticky="nsew")

        self.left_pane_frame = ttk.Frame(main_paned_window, padding=5)
        main_paned_window.add(self.left_pane_frame, weight=1) # Adjust weight as needed

        # --- Game Controls ---
        game_controls_frame = ttk.LabelFrame(self.left_pane_frame, text="Game Controls", padding=10)
        game_controls_frame.pack(fill=tk.X, pady=(0,5), side=tk.TOP, anchor=tk.N)

        self.start_game_btn = ttk.Button(game_controls_frame, text="Play as White", # Changed text
                                           command=self._gui_action_start_new_game_white) # New specific command
        self.start_game_btn.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)

        # NEW: Play as Black button
        self.play_as_black_btn = ttk.Button(game_controls_frame, text="Play as Black",
                                           command=self._gui_action_play_as_black)
        self.play_as_black_btn.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)
        
        self.reset_game_btn = ttk.Button(game_controls_frame, text="Reset Game",
                                           command=self._gui_action_reset_game)
        self.reset_game_btn.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)


        # --- Action Controls ---
        action_controls_frame = ttk.LabelFrame(self.left_pane_frame, text="Actions", padding=10)
        action_controls_frame.pack(fill=tk.X, pady=(0,5), side=tk.TOP, anchor=tk.N)

        # NEW: Make Engine Move for Player button
        self.make_engine_move_btn = ttk.Button(action_controls_frame, text="Engine Move for Me",
                                                 command=self._gui_action_make_engine_move_for_player)
        self.make_engine_move_btn.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)

        # NEW: Take Back button
        self.take_back_btn = ttk.Button(action_controls_frame, text="Take Back",
                                        command=self._gui_action_take_back)
        self.take_back_btn.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)


        # --- General Options (Flip, Hints) ---
        options_frame = ttk.LabelFrame(self.left_pane_frame, text="Options", padding=10)
        options_frame.pack(fill=tk.X, pady=(0,5), side=tk.TOP, anchor=tk.N)

        self.flip_board_btn = ttk.Button(options_frame, text="Flip Board / Swap Sides", # Clarified text
                                          command=self._gui_action_flip_board)
        self.flip_board_btn.pack(side=tk.LEFT, padx=2, pady=2)

        self.show_hints_checkbox = ttk.Checkbutton(options_frame, text="Show Hints",
                                                   variable=self.show_hints_var_tk,
                                                   command=self._gui_action_toggle_hints)
        self.show_hints_checkbox.pack(side=tk.LEFT, padx=5, pady=2)

        # BlunderFeedbackPanel is used for general game feedback now
        self.feedback_panel_component = BlunderFeedbackPanel(self.left_pane_frame)
        # Ensure BlunderFeedbackPanel's methods like update_feedback, update_hints, clear_hints are suitable

        self.status_bar_variable = tk.StringVar(value="Initializing...")
        status_bar_label = ttk.Label(self.left_pane_frame, textvariable=self.status_bar_variable,
                                     relief=tk.SUNKEN, anchor=tk.W)
        status_bar_label.pack(fill=tk.X, side=tk.BOTTOM, pady=(5,0), ipady=2)

        self.right_pane_frame = ttk.Frame(main_paned_window, padding=5)
        main_paned_window.add(self.right_pane_frame, weight=3) # Adjust weight as needed
        self.right_pane_frame.grid_rowconfigure(0, weight=1)
        self.right_pane_frame.grid_columnconfigure(0, weight=1)

        self.board_widget_component = ChessBoardWidget(
            parent=self.right_pane_frame,
            board_size_px=DEFAULT_BOARD_SIZE_PX,
            image_path=IMAGE_PATH,
            on_resize_callback=self.handle_board_widget_resize_from_gui
        )
        self.board_widget_component.frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        print("✅ Main widgets layout created.")

    def _initialize_application_logic(self, root_tk): 
        self.status_bar_variable.set("Loading 9M Chess Engine...")
        self.root.update_idletasks()
        print("🔄 Loading 9M Chess Engine...")

        if not SEARCHLESS_ENGINES_AVAILABLE:
             messagebox.showerror("Engine Error", "Searchless_chess library not found.")
             logging.critical("Searchless_chess library not available during init.")
             self.root.destroy()
             return

        self.engine_manager.load_engines(load_136m_flag=False)

        if not self.engine_manager.engine_9M:
            messagebox.showerror("Engine Load Failed", "Could not load 9M chess engine.")
            logging.critical("Failed to load 9M engine during init.")
            self.root.destroy()
            return
        logging.info("9M Engine loaded for play.")
        print("✅ 9M Engine loaded.")
        
        self.controller = GameController(
            board_widget=self.board_widget_component,
            feedback_panel=self.feedback_panel_component,
            engine_manager=self.engine_manager,
            gui_update_buttons_callback=self._update_gui_button_states
        )
        self.controller.root = root_tk 

        logging.info("GameController initialized in GUI.")
        print("🔄 GameController setup in GUI...")

        self.controller._transition_to_mode("IDLE") 
        self.status_bar_variable.set("Ready. Choose to play as White or Black.")
        print("✅ Game controller linked to GUI. Ready for actions.")
        
        self._update_gui_button_states()

    def _on_application_window_close(self):
        logging.info("Chess vs 9M Engine: Closing application.")
        print("Application closing.")
        self.root.destroy()

    def _gui_action_toggle_hints(self):
        if self.controller:
            self.controller.toggle_game_hints(self.show_hints_var_tk.get())

    def _gui_action_flip_board(self):
        if self.controller:
            self.controller.action_flip_board_view()
            # Status bar might be updated by controller's feedback logic

    def _gui_action_start_new_game_white(self): # Renamed from _gui_action_start_new_game
        if self.controller:
            self.controller.action_start_new_game(player_color=chess.WHITE)

    def _gui_action_play_as_black(self): # NEW
        if self.controller:
            self.controller.action_play_as_black()

    def _gui_action_reset_game(self):
        if self.controller:
            self.controller.action_reset_game()

    def _gui_action_make_engine_move_for_player(self): # NEW
        if self.controller:
            self.controller.action_make_engine_move_for_player()
    
    def _gui_action_take_back(self): # NEW
        if self.controller:
            self.controller.action_take_back()


    def handle_board_widget_resize_from_gui(self):
        if self.controller:
            self.controller.handle_board_resize()
        else:
            logging.warning("MainGUI: Resize event received, but controller not yet initialized.")

    def _update_gui_button_states(self):
        if not self.controller or not hasattr(self.controller, 'game_manager'): 
            # Initial setup or error state, disable most things
            if hasattr(self, 'start_game_btn'): self.start_game_btn.config(state=tk.NORMAL)
            if hasattr(self, 'play_as_black_btn'): self.play_as_black_btn.config(state=tk.NORMAL)
            if hasattr(self, 'reset_game_btn'): self.reset_game_btn.config(state=tk.DISABLED)
            if hasattr(self, 'flip_board_btn'): self.flip_board_btn.config(state=tk.NORMAL) # Can flip empty board
            if hasattr(self, 'show_hints_checkbox'): self.show_hints_checkbox.config(state=tk.DISABLED)
            if hasattr(self, 'make_engine_move_btn'): self.make_engine_move_btn.config(state=tk.DISABLED)
            if hasattr(self, 'take_back_btn'): self.take_back_btn.config(state=tk.DISABLED)
            return

        mode = self.controller.current_interaction_mode
        game_is_active = self.controller.game_manager.is_active()
        is_player_turn = game_is_active and mode == "PLAYER_TURN"
        can_take_back = game_is_active and self.controller.game_manager.has_moves_to_take_back()

        # Start game buttons are always enabled to allow starting a new game
        self.start_game_btn.config(state=tk.NORMAL)
        self.play_as_black_btn.config(state=tk.NORMAL)
        
        self.reset_game_btn.config(state=tk.NORMAL if game_is_active else tk.DISABLED)
        
        # Flip board / Swap Sides: always enabled, behavior changes if game is active
        self.flip_board_btn.config(state=tk.NORMAL) 
        
        self.show_hints_checkbox.config(state=tk.NORMAL if game_is_active else tk.DISABLED)
        # Removed auto-unchecking logic; hint visibility is now solely controlled by
        # self.show_hints_var_tk (via user) and GameController.show_hints_active

        self.make_engine_move_btn.config(state=tk.NORMAL if is_player_turn else tk.DISABLED)
        self.take_back_btn.config(state=tk.NORMAL if can_take_back else tk.DISABLED)

        logging.debug(f"MainGUI: Buttons updated. Mode: {mode}, GameActive: {game_is_active}, PlayerTurn: {is_player_turn}, CanTakeBack: {can_take_back}")


def setup_logging():
    log_file_path = LOG_FILENAME 
    if not os.path.isabs(log_file_path):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            log_file_path = os.path.join(script_dir, log_file_path)
        except NameError:
            pass 
    
    log_dir = os.path.dirname(log_file_path)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except OSError as e:
            print(f"Error creating log directory {log_dir}: {e}")
            log_file_path = os.path.basename(LOG_FILENAME) if os.path.basename(LOG_FILENAME) else "chess_app.log"

    logging.basicConfig(filename=log_file_path, filemode='w',
                        level=logging.DEBUG,
                        format=LOG_FORMAT) 
    logging.info("Chess vs 9M Engine application starting...")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s: (%(module)s.%(funcName)s) %(message)s')
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler)

if __name__ == '__main__':
    setup_logging()
    print("Starting Chess vs 9M Engine Application...")

    _startup_tk_for_error_msg = tk.Tk()
    _startup_tk_for_error_msg.withdraw()

    if not os.path.isdir(IMAGE_PATH): 
        messagebox.showerror("Resource Error",
                             f"Image directory '{IMAGE_PATH}' not found. Piece images will not be displayed.",
                             parent=_startup_tk_for_error_msg)
        logging.error(f"Image directory '{IMAGE_PATH}' not found.")
        print(f"⚠️ Image directory '{IMAGE_PATH}' not found.")

    if not SEARCHLESS_ENGINES_AVAILABLE:
        messagebox.showerror("Dependency Error",
                               "The 'searchless_chess' library components (engines) were not found or failed to import. "
                               "AI functionality will be unavailable. Please check your Python environment and the library installation.",
                               parent=_startup_tk_for_error_msg)
        logging.critical("searchless_chess package not found or import failed.")
        print("❌ CRITICAL: searchless_chess package not found.")

    _startup_tk_for_error_msg.destroy()

    main_tk_window = tk.Tk()
    app_gui = MainChessVsEngineGUI(main_tk_window)
    main_tk_window.mainloop()

    logging.info("Chess vs 9M Engine application finished.")
    print("Application finished.")
