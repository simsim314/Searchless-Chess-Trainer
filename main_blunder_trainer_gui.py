# ===== START OF FILE main_blunder_trainer_gui.py =====
import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import logging

from engines import SearchlessEngineManager, SEARCHLESS_ENGINES_AVAILABLE
from constants import IMAGE_PATH, MIN_BOARD_SIZE_PX, DEFAULT_BOARD_SIZE_PX, LOG_FILENAME, LOG_FORMAT

from chess_board_widget import ChessBoardWidget
from blunder_data_manager import BlunderDataManager # Already imports LearnedBlunderTracker implicitly
from blunder_feedback_panel import BlunderFeedbackPanel
from blunder_trainer_controller import BlunderTrainerController

class MainBlunderTrainerGUI:
    def __init__(self, root_tk_window):
        self.root = root_tk_window
        self.root.title("Chess Blunder Trainer - Advanced") # Updated title

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.engine_manager = SearchlessEngineManager()
        # DataManager now instantiates LearnedBlunderTracker
        self.data_manager = BlunderDataManager()
        self.controller = None
        self.show_hints_var_tk = tk.BooleanVar(value=False)
        self.show_only_unsolved_var_tk = tk.BooleanVar(value=True) # For new filter option

        self._create_main_widgets_layout()
        self._initialize_application_logic()

        self.root.protocol("WM_DELETE_WINDOW", self._on_application_window_close)

    def _create_main_widgets_layout(self):
        main_paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned_window.grid(row=0, column=0, sticky="nsew")

        self.left_pane_frame = ttk.Frame(main_paned_window, padding=5)
        main_paned_window.add(self.left_pane_frame, weight=1)

        # --- Top Controls (Nav, Retry, Play) ---
        top_controls_frame = ttk.LabelFrame(self.left_pane_frame, text="Training Controls", padding=10)
        top_controls_frame.pack(fill=tk.X, pady=(0,5), side=tk.TOP, anchor=tk.N)

        self.next_blunder_btn = ttk.Button(top_controls_frame, text="Next",
                                          command=self._gui_action_next_blunder)
        self.next_blunder_btn.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)

        self.prev_blunder_btn = ttk.Button(top_controls_frame, text="Prev",
                                          command=self._gui_action_prev_blunder)
        self.prev_blunder_btn.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)

        self.retry_attempt_btn = ttk.Button(top_controls_frame, text="Retry",
                                           command=self._gui_action_retry_current)
        self.retry_attempt_btn.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)

        # --- Play Controls ---
        play_controls_frame = ttk.LabelFrame(self.left_pane_frame, text="Play Controls", padding=10)
        play_controls_frame.pack(fill=tk.X, pady=(0,5), side=tk.TOP, anchor=tk.N)

        self.play_from_blunder_btn = ttk.Button(play_controls_frame, text="Play vs Engine",
                                           command=self._gui_action_play_from_blunder)
        self.play_from_blunder_btn.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)

        self.return_to_training_btn = ttk.Button(play_controls_frame, text="Stop Play",
                                           command=self._gui_action_return_to_training)
        self.return_to_training_btn.pack(side=tk.LEFT, padx=2, pady=2, fill=tk.X, expand=True)

        # --- General Options (Flip, Hints, Filter) ---
        options_frame = ttk.LabelFrame(self.left_pane_frame, text="Options", padding=10)
        options_frame.pack(fill=tk.X, pady=(0,5), side=tk.TOP, anchor=tk.N)

        self.flip_board_btn = ttk.Button(options_frame, text="Flip Board",
                                          command=self._gui_action_flip_board)
        self.flip_board_btn.pack(side=tk.LEFT, padx=2, pady=2)

        self.show_hints_checkbox = ttk.Checkbutton(options_frame, text="Show Hints",
                                                   variable=self.show_hints_var_tk,
                                                   command=self._gui_action_toggle_hints)
        self.show_hints_checkbox.pack(side=tk.LEFT, padx=5, pady=2)

        self.filter_solved_checkbox = ttk.Checkbutton(options_frame, text="Only Unsolved",
                                                      variable=self.show_only_unsolved_var_tk,
                                                      command=self._gui_action_toggle_solved_filter)
        self.filter_solved_checkbox.pack(side=tk.LEFT, padx=5, pady=2)


        self.feedback_panel_component = BlunderFeedbackPanel(self.left_pane_frame)
        # BlunderFeedbackPanel packs itself and should take remaining space in left_pane_frame
        # To make it expand more, ensure its parent (left_pane_frame) gives it space.
        # The LabelFrames above are packed with side=tk.TOP, so FeedbackPanel will get what's left.

        self.status_bar_variable = tk.StringVar(value="Initializing...")
        status_bar_label = ttk.Label(self.left_pane_frame, textvariable=self.status_bar_variable,
                                     relief=tk.SUNKEN, anchor=tk.W)
        status_bar_label.pack(fill=tk.X, side=tk.BOTTOM, pady=(5,0), ipady=2)

        # ... (Right pane setup remains the same) ...
        self.right_pane_frame = ttk.Frame(main_paned_window, padding=5)
        main_paned_window.add(self.right_pane_frame, weight=3)
        self.right_pane_frame.grid_rowconfigure(0, weight=1)
        self.right_pane_frame.grid_columnconfigure(0, weight=1)

        self.board_widget_component = ChessBoardWidget(
            parent=self.right_pane_frame,
            board_size_px=DEFAULT_BOARD_SIZE_PX,
            image_path=IMAGE_PATH,
            on_resize_callback=self.handle_board_widget_resize_from_gui
        )
        self.board_widget_component.frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

    def _initialize_application_logic(self):
        # ... (Engine loading)
        self.status_bar_variable.set("Loading 9M Chess Engine...")
        self.root.update_idletasks()

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
        logging.info("9M Engine loaded for Blunder Trainer's live evaluations.")
        
        # Apply initial filter state to DataManager BEFORE loading blunders
        self.data_manager.set_show_only_unsolved(self.show_only_unsolved_var_tk.get())

        self.status_bar_variable.set("Loading blunder data...")
        self.root.update_idletasks()

        if not self.data_manager.load_blunders(): # This now loads and filters
            messagebox.showwarning("Data Load Warning", "Could not load blunder data.")
            self.status_bar_variable.set("Error: Blunder data not found.")
            logging.warning("Blunder data not loaded or invalid.")
        else:
            logging.info(f"Blunder data loaded: {self.data_manager.get_blunder_count()} blunders for training session.")

        self.controller = BlunderTrainerController(
            board_widget=self.board_widget_component,
            feedback_panel=self.feedback_panel_component,
            data_manager=self.data_manager,
            engine_manager=self.engine_manager,
            gui_update_buttons_callback=self._update_gui_button_states
        )
        self.controller.set_show_hints_in_play_mode_var(self.show_hints_var_tk)
        logging.info("BlunderTrainerController initialized.")

        if self.data_manager.has_blunders():
            self.data_manager.current_index = -1 # Start before the first
            self.controller.action_select_next_blunder() # Load the first available blunder
        else:
            self.status_bar_variable.set("No blunders available for training with current filter.")
            logging.info("No blunders available for training after initialization and filtering.")
            self.controller.load_and_display_current_blunder() # Will show "No blunders" message

        self._update_gui_button_states()

    def _gui_action_toggle_solved_filter(self):
        if self.controller and self.data_manager:
            is_playing = self.controller.current_interaction_mode.startswith("playing_from_blunder")
            if is_playing:
                # Prevent filter change during active play to avoid confusion
                messagebox.showinfo("Filter Info", "Stop play mode to change blunder filter.")
                self.show_only_unsolved_var_tk.set(not self.show_only_unsolved_var_tk.get()) # Revert checkbox
                return

            new_filter_state = self.show_only_unsolved_var_tk.get()
            self.data_manager.set_show_only_unsolved(new_filter_state)
            # Reloading blunders based on new filter
            logging.info(f"GUI: Toggled 'Only Unsolved' filter to {new_filter_state}. Reloading blunders.")
            # Instead of full reload, just trigger next blunder which will use the new filtered list
            # or display "no blunders" if the new list is empty.
            self.controller.action_select_next_blunder() # This will pick from the new filtered list
            if not self.data_manager.has_blunders():
                 self.status_bar_variable.set("No blunders match current filter.")
            self._update_gui_button_states()


    def _on_application_window_close(self):
        logging.info("Blunder Trainer GUI: Closing application.")
        if self.data_manager and self.data_manager.learned_tracker.has_unsaved_changes:
            if messagebox.askyesno("Unsaved Progress", "You have unsaved learning progress. Save now?"):
                self.data_manager.save_learning_progress()
        self.root.destroy()

    # ... (other GUI actions and _update_gui_button_states need no major changes for this step,
    #      but _update_gui_button_states should correctly reflect interactability based on modes)

    def _gui_action_toggle_hints(self):
        if self.controller:
            if self.controller.current_interaction_mode.startswith("playing_from_blunder"):
                self.controller.toggle_hints_in_play_mode()
            elif self.controller.current_interaction_mode == "showing_feedback":
                 if not self.show_hints_var_tk.get(): 
                    self.controller.board_widget.clear_visual_cues()
                    if self.controller.current_blunder_data_active:
                        self.controller.board_widget.draw_arrow(
                            self.controller.current_blunder_data_active['blunder_move_uci'],
                            ACTUAL_BLUNDER_MOVE_COLOR, BLUNDER_ARROW_WIDTH
                        )
                        attempt_info = self.controller.current_blunder_data_active.get(JSON_ATTEMPT_KEY, {})
                        user_attempt_uci = attempt_info.get(JSON_ATTEMPT_UCI_KEY)
                        if user_attempt_uci:
                            self.controller.board_widget.draw_arrow(
                                user_attempt_uci, USER_TRIAL_MOVE_COLOR, USER_ATTEMPT_ARROW_WIDTH
                            )
                    self.feedback_panel.clear_hints()
                 else: 
                    self.controller._redraw_all_visual_cues_for_current_state()
            logging.info(f"GUI: Hints toggled. State: {self.show_hints_var_tk.get()}")
        self._update_gui_button_states()


    def _gui_action_next_blunder(self):
        if self.controller:
             self.controller.action_select_next_blunder()
        # Status message and button states are updated by controller and its callbacks
    
    def _gui_action_prev_blunder(self):
        if self.controller:
            self.controller.action_select_prev_blunder()

    def _gui_action_flip_board(self):
        if self.controller:
            self.controller.action_flip_board_view()
            self.status_bar_variable.set("Board view flipped.")
            logging.info("GUI: Board view flipped.")

    def _gui_action_retry_current(self):
        if self.controller:
            self.controller.action_retry_current_blunder()
            logging.info("GUI: Retry current blunder action invoked.")
        # Button states updated by controller callback

    def _gui_action_play_from_blunder(self):
        if self.controller:
            self.controller.action_play_from_blunder_position()
            logging.info("GUI: Play from blunder action invoked.")
        # Button states updated by controller callback

    def _gui_action_return_to_training(self):
        if self.controller:
            self.controller.action_return_to_training()
            logging.info("GUI: Return to training action invoked.")
        # Button states updated by controller callback

    def handle_board_widget_resize_from_gui(self):
        if self.controller:
            self.controller.handle_board_resize()
            logging.info("MainGUI: Relayed resize event to controller.")
        else:
            logging.warning("MainGUI: Resize event received, but controller not yet initialized.")

    def _update_gui_button_states(self):
        if not hasattr(self, 'controller') or not self.controller:
            if hasattr(self, 'next_blunder_btn'): self.next_blunder_btn.config(state=tk.DISABLED)
            # ... disable all other buttons ...
            if hasattr(self, 'play_from_blunder_btn'): self.play_from_blunder_btn.config(state=tk.DISABLED)
            if hasattr(self, 'return_to_training_btn'): self.return_to_training_btn.config(state=tk.DISABLED)
            if hasattr(self, 'show_hints_checkbox'): self.show_hints_checkbox.config(state=tk.DISABLED)
            if hasattr(self, 'filter_solved_checkbox'): self.filter_solved_checkbox.config(state=tk.DISABLED)
            return

        mode = self.controller.current_interaction_mode
        has_blunders_for_session = self.data_manager.has_blunders() # Based on current filter
        blunder_loaded_for_display = self.controller.current_blunder_data_active is not None

        is_playing_mode = mode.startswith("playing_from_blunder")
        is_player_turn_in_play = mode == "playing_from_blunder_player_turn"
        is_showing_feedback_training = mode == "showing_feedback"
        is_user_input_training = mode == "user_input"
        is_waiting_for_blunder = mode == "waiting_for_blunder"
        
        # Training navigation: Next/Prev enabled if not playing, and not in user_input mode (i.e., feedback shown or engine thinking for user)
        # And there must be blunders loaded in the current session list.
        can_navigate_training = has_blunders_for_session and not is_playing_mode and not is_user_input_training and not is_waiting_for_blunder
        self.next_blunder_btn.config(state=tk.NORMAL if can_navigate_training else tk.DISABLED)
        self.prev_blunder_btn.config(state=tk.NORMAL if can_navigate_training else tk.DISABLED)
        
        # Retry: if blunder is loaded for display and we are in feedback mode for training
        self.retry_attempt_btn.config(state=tk.NORMAL if blunder_loaded_for_display and is_showing_feedback_training else tk.DISABLED)

        # Play vs Engine: if blunder is loaded for display and we are in feedback mode for training
        self.play_from_blunder_btn.config(state=tk.NORMAL if blunder_loaded_for_display and is_showing_feedback_training else tk.DISABLED)

        # Stop Play: if currently in any play mode
        self.return_to_training_btn.config(state=tk.NORMAL if is_playing_mode else tk.DISABLED)

        # Flip board: always enabled if a blunder is loaded for display OR if playing
        self.flip_board_btn.config(state=tk.NORMAL if blunder_loaded_for_display or is_playing_mode else tk.DISABLED)

        # Show Hints Checkbox: Enabled during player's turn in play mode, or when showing feedback in training.
        self.show_hints_checkbox.config(state=tk.NORMAL if is_player_turn_in_play or is_showing_feedback_training else tk.DISABLED)
        
        # Filter Solved Checkbox: Always enabled, unless actively playing.
        self.filter_solved_checkbox.config(state=tk.NORMAL if not is_playing_mode else tk.DISABLED)

        logging.debug(f"MainGUI: Buttons updated. Mode: {mode}, "
                      f"Next: {self.next_blunder_btn.cget('state')}, Prev: {self.prev_blunder_btn.cget('state')}, "
                      f"Retry: {self.retry_attempt_btn.cget('state')}, Flip: {self.flip_board_btn.cget('state')}, "
                      f"Play: {self.play_from_blunder_btn.cget('state')}, StopPlay: {self.return_to_training_btn.cget('state')}, "
                      f"HintsChk: {self.show_hints_checkbox.cget('state')}, FilterSolvedChk: {self.filter_solved_checkbox.cget('state')}")


# ... (setup_logging and __main__ block remain the same) ...
# (Make sure they are correctly included from your previous version)
def setup_logging():
    log_file_path = LOG_FILENAME
    if not os.path.isabs(LOG_FILENAME):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            log_file_path = os.path.join(script_dir, LOG_FILENAME)
        except NameError:
            log_file_path = LOG_FILENAME
    log_dir = os.path.dirname(log_file_path)
    if log_dir and not os.path.exists(log_dir):
        try: os.makedirs(log_dir)
        except OSError as e:
            print(f"Error creating log directory {log_dir}: {e}")
            log_file_path = os.path.basename(LOG_FILENAME) if os.path.basename(LOG_FILENAME) else "blunder_trainer_refactored.log"

    logging.basicConfig(filename=log_file_path, filemode='w',
                        level=logging.DEBUG,
                        format=LOG_FORMAT)
    logging.info("Blunder Trainer (Refactored) application starting...")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s: (%(module)s.%(funcName)s) %(message)s')
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler)

if __name__ == '__main__':
    setup_logging()

    _startup_tk_for_error_msg = tk.Tk()
    _startup_tk_for_error_msg.withdraw()

    if not os.path.isdir(IMAGE_PATH):
        messagebox.showerror("Resource Error",
                             f"Image directory '{IMAGE_PATH}' not found. Piece images will not be displayed.",
                             parent=_startup_tk_for_error_msg)
        logging.error(f"Image directory '{IMAGE_PATH}' not found.")

    if not SEARCHLESS_ENGINES_AVAILABLE:
        messagebox.showerror("Dependency Error",
                               "The 'searchless_chess' library components (engines) were not found or failed to import. "
                               "AI functionality will be unavailable. Please check your Python environment and the library installation.",
                               parent=_startup_tk_for_error_msg)
        logging.critical("searchless_chess package not found or import failed. This is critical for engine functionality.")

    _startup_tk_for_error_msg.destroy()

    main_tk_window = tk.Tk()
    app_gui = MainBlunderTrainerGUI(main_tk_window)
    main_tk_window.mainloop()

    logging.info("Blunder Trainer (Refactored) application finished.")
# ===== END OF FILE main_blunder_trainer_gui.py =====
