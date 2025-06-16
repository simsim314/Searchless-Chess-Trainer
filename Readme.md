# Advanced Chess Analysis & Training Suite

This project is a Python-based chess analysis and training suite built with Tkinter and powered by the [**searchless-chess from deep mind**](https://github.com/google-deepmind/searchless_chess) library—a transformer-based neural network engine that evaluates chess positions purely through pattern recognition, without relying on brute-force search.

Unlike traditional chess engines that evaluate millions of positions per second, **searchless-chess** makes moves based solely on deep positional understanding, just like a human master. This eliminates the usual frustration or excuse of competing against a machine’s calculation speed, keeping training realistic, fair, and insightful.

The suite utilizes two distinct engines—**9M** and **136M**—to deliver balanced and actionable feedback:

* **9M engine:** Elo \~2050, better than 90% of players on lichess. Its analysis focuses on practical, achievable moves suitable for ambitious hobbyists and club players.
* **136M engine:** Elo \~2700 (senior master, roughly 2450 USCF). Provides world-class insights and challenging analyses, perfect for players aspiring to advanced mastery.

With this dual-engine approach, you receive meaningful, human-like training and advice—not just “perfect” moves you have no realistic chance of finding.

---

## Applications

### 🎯 PGN Analyzer (`main_pgn_analyzer_gui.py`)
Deep, move-by-move analysis of a complete game from PGN. Uses both 9M and 136M engines with color-coded hints and evaluation symbols (!, ??, etc.).

### 🧠 Blunder Trainer (`main_blunder_trainer_gui.py`)
Trains users on previously made blunders. Includes a progress tracker and filters solved puzzles.

### ♟️ Play vs. Engine (`play_against_engine.py`)
Play a full Chess960 game against the 9M engine. Asymmetric random starting positions included.

### 🛠️ Blunder Scanner (`blunder_scanner.py`)
Command-line tool that detects blunders from PGN files and creates a `blunders_report.json` used by the Blunder Trainer.

---

## Installation

```bash
git clone https://github.com/simsim314/Searchless-Chess-Trainer.git
cd searchless-chess/checkpoints
bash download.sh
cd ..
cd ..
```

---

## How to Use

### 1. (Optional) Generate Blunder Data

```bash
python blunder_scanner.py my_games.pgn --player YourLichessUsername --output_json blunders_report.json
```

### 2. Run the PGN Analyzer

```bash
python main_pgn_analyzer_gui.py
```

### 3. Run the Blunder Trainer

```bash
python main_blunder_trainer_gui.py
```

### 4. Play Against the Engine

```bash
python play_against_engine.py
```

---

## File-by-File Breakdown

### Main Applications

* **`main_pgn_analyzer_gui.py`**
  GUI for PGN input and analysis.
  Key class: `MainPgnAnalyzerGUI`

* **`main_blunder_trainer_gui.py`**
  Blunder quiz UI linked to engine and tracker.
  Key class: `MainBlunderTrainerGUI`

* **`play_against_engine.py`**
  Chess960 play interface.
  Key class: `MainChessVsEngineGUI`

* **`blunder_scanner.py`**
  PGN-to-blunder JSON converter.
  Key function: `scan_pgn_file()`

---

### Controllers

* **`pgn_analyzer_controller.py`**
  Manages PGN analysis and evaluation rendering.
  Key class: `PgnAnalyzerController`

* **`blunder_trainer_controller.py`**
  Handles puzzle logic, user moves, engine checks.
  Key class: `BlunderTrainerController`

* **`game_controller.py`**
  Play vs engine game manager.
  Key class: `GameController`

---

### Game/Data Managers

* **`blunder_data_manager.py`**
  Loads and filters `blunders_report.json`.
  Key class: `BlunderDataManager`

* **`learned_blunder_tracker.py`**
  Tracks solved blunders in `learned_blunders_progress.json`.
  Key class: `LearnedBlunderTracker`

* **`game_manager.py`**
  Active game state holder using `python-chess`.
  Key class: `GameManager`

* **`pgn_manager.py`**
  PGN parsing and move navigation.
  Key class: `PgnManager`

---

### GUI Components

* **`chess_board_widget.py`**
  Draws the board, arrows, highlights.
  Key class: `ChessBoardWidget`

* **`blunder_feedback_panel.py`**
  Displays user feedback and engine suggestions.
  Key class: `BlunderFeedbackPanel`

* **`chess_draw_utils.py`**
  Pure drawing functions for canvas rendering.

---

### Engines & Utilities

* **`engines.py`**
  Wraps the `searchless-chess` engine interface.
  Key class: `SearchlessEngineManager`

* **`utils.py`**
  Misc helpers like `pwin_to_cp()` and `setup_asymmetric_chess960()`.

* **`constants.py`, `constants_blunder_trainer.py`**
  Styling, thresholds, and config values.
