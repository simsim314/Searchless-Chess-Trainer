# Technical Report: Advanced Chess Analysis & Training Suite

## 1.0 Introduction

This document provides a detailed technical overview of the "Advanced Chess Analysis & Training Suite," a collection of Python applications designed for chess improvement. The suite leverages the searchless-chess library for high-speed, neural network-based move evaluation, wrapped in user-friendly Tkinter GUIs. This report details the architecture, key components, and operational flow of each application within the suite.

The system is architected using a Model-View-Controller (MVC) pattern, where:

* **Model**: Consists of the data and game management classes (`PgnManager`, `GameManager`, `BlunderDataManager`, `LearnedBlunderTracker`) and the `python-chess` board objects.
* **View**: Comprises the GUI main files (`main_*.py`), the `ChessBoardWidget`, and the `BlunderFeedbackPanel`.
* **Controller**: The logic layers (`PgnAnalyzerController`, `BlunderTrainerController`, `GameController`) that mediate between the Model and the View.

## 2.0 Core Components & Utilities

### 2.1 `engines.py`

**Purpose**: Provides a clean, high-level interface to the searchless-chess engine library.

**Key Class**: `SearchlessEngineManager`

* `__init__()` – Initializes placeholders (None) for the 9M and 136M engine models.
* `load_engines(load_136m_flag=True)` – Dynamically loads models from disk.
* `get_top_engine_moves_list(engine_instance, board_state, num_moves=3)` – Returns top move list with `uci`, `san`, and `p_win`.

**Usage Example:**

```python
engine_mgr = SearchlessEngineManager()
engine_mgr.load_engines()
board = chess.Board()
top_moves = engine_mgr.get_top_engine_moves_list(engine_mgr.engine_9M, board)
```

### 2.2 `utils.py`

**Purpose**: Stateless helpers for conversions and setup.

**Key Functions**:

* `pwin_to_cp(prob)` – Converts probability to centipawns.
* `cp_to_pwin(centipawns)` – Converts CP to win probability.
* `format_score_for_display(score_value, is_cp=False)` – Formats for display.
* `setup_asymmetric_chess960()` – Generates varied Chess960 boards.

**Usage Example:**

```python
import utils
cp = utils.pwin_to_cp(0.75)  # ~273
formatted = utils.format_score_for_display(cp, is_cp=True)  # '2.73'
```

### 2.3 `constants.py` & `constants_blunder_trainer.py`

**Purpose**: Centralized configuration and magic numbers.

## 3.0 PGN Analyzer Application

### 3.1 `main_pgn_analyzer_gui.py`

**Key Class**: `MainPgnAnalyzerGUI`

* `_create_main_widgets_layout()` – Lays out widgets.
* `_initialize_application_logic()` – Initializes controller and callbacks.
* `_gui_action_analyze_game()` – Triggers PGN analysis in a thread.
* `_gui_action_on_move_select(event)` – Handles move list selection.

### 3.2 `pgn_analyzer_controller.py`

**Key Class**: `PgnAnalyzerController`

* `load_and_analyze_pgn(pgn_string, player_name)` – Entry point for analysis.
* `_perform_full_game_analysis()` – Iterates through moves, classifies quality.
* `_redraw_visuals_for_current_move()` – Updates board and hints.
* `_get_cp_for_mover(pwin, board)` – Converts P(Win) to CP from correct perspective.

**Usage Example:**

```python
pgn = pgn_input_widget.get()
player = player_input.get()
controller.load_and_analyze_pgn(pgn, player)
```

### 3.3 `pgn_manager.py`

**Key Class**: `PgnManager`

* `load_pgn_from_string(pgn_string)` – Parses PGN string.
* `get_total_plies_mainline()` – Computes total plies.

## 4.0 Blunder Trainer Application

### 4.1 `main_blunder_trainer_gui.py`

**Key Class**: `MainBlunderTrainerGUI`

* `_initialize_application_logic()` – Loads engines and blunders.
* `_gui_action_* methods` – Handles buttons: next, retry, play.
* `_update_gui_button_states()` – Enables/disables UI buttons.

### 4.2 `blunder_trainer_controller.py`

**Key Class**: `BlunderTrainerController`

* `load_and_display_current_blunder()` – Loads and sets up blunder.
* `_handle_user_blunder_fix_attempt(attempted_move_uci)` – User move handler.
* `_evaluate_and_display_user_attempt(user_trial_move_obj)` – Compares to engine line.

**Usage Example:**

```python
controller.action_select_next_blunder()
# ChessBoardWidget calls back on user move
controller._handle_user_blunder_fix_attempt("e2e4")
```

### 4.3 `blunder_data_manager.py`

**Key Class**: `BlunderDataManager`

* `load_blunders()` – Reads blunders report JSON.
* `_filter_and_sort_training_blunders()` – Filters out solved or weak blunders.
* `record_attempt_for_current_blunder(...)`

### 4.4 `learned_blunder_tracker.py`

**Key Class**: `LearnedBlunderTracker`

* `record_attempt(...)`
* `is_blunder_solved(fen)` – Filters blunders by solved state.
* `save_progress()`

## 5.0 Play vs. Engine Application

### 5.1 `play_against_engine.py`

**Key Class**: `MainChessVsEngineGUI`

* Provides buttons for game start, reset, hint, undo.

### 5.2 `game_controller.py`

**Key Class**: `GameController`

* `_handle_user_move_attempt(uci)` – Validates move and triggers engine.
* `_trigger_engine_move()` – Makes engine move and updates state.
* `_redraw_all_visual_cues_for_current_state()`

### 5.3 `game_manager.py`

**Key Class**: `GameManager`

* `start_new_game(...)`
* `make_player_move(uci)`
* `get_engine_move_uci(...)`

**Usage Example:**

```python
game_mgr = GameManager()
game_mgr.start_new_game(player_color=chess.WHITE, engine_instance=engine)
if game_mgr.make_player_move("e2e4"):
    engine_move = game_mgr.get_engine_move_uci(engine_mgr)
    game_mgr.make_move_on_board(engine_move)
```

## 6.0 GUI & Drawing Components

### 6.1 `chess_board_widget.py`

**Key Class**: `ChessBoardWidget`

* `set_position(fen)`
* `draw_arrow(uci, color, width)`
* `draw_text_on_square(square, text, color)`
* `on_move_attempted_callback`

**Usage Example:**

```python
def handle_user_move(uci):
    print(f"User played {uci}")

board_widget.on_move_attempted_callback = handle_user_move
board_widget.set_position("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
board_widget.draw_arrow("e2e4", "green", 10)
```

### 6.2 `chess_draw_utils.py`

**Key Functions**:

* `sq_to_canvas_coords_oriented(...)`
* `canvas_coords_to_sq_oriented(...)`
* `draw_arrow(...)`
* `load_and_resize_piece_images(...)`
