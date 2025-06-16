
# constants_blunder_trainer.py
from constants import ARROW_WIDTH_BASE, HINT_PALETTE_1 # Import base values

# File path for the blunder report
BLUNDER_REPORT_FILE = "blunders_report.json" # Path to your blunder data file

# Colors specific to the Blunder Trainer GUI
USER_TRIAL_MOVE_COLOR = "#228B22"  # ForestGreen for user's attempted correction
SOLVED_BLUNDER_COLOR = "#32CD32"   # LimeGreen (e.g., for highlighting in a list)
UNSOLVED_BLUNDER_COLOR = "#FF4500" # OrangeRed
ACTUAL_BLUNDER_MOVE_COLOR = "#DC143C" # Crimson Red for the blunder itself

# Default threshold for filtering blunders in the GUI (if you implement filtering later)
DEFAULT_GUI_BLUNDER_THRESHOLD = 0.10 # e.g., only show blunders with >= 10% drop initially

# JSON field names for saving attempt status (if you implement saving progress)
JSON_ATTEMPT_KEY = "user_trainer_attempt"
JSON_SOLVED_9M_KEY = "solved_status_9M"
# JSON_SOLVED_136M_KEY = "solved_status_136M" # Commented out as 136M is not used in trainer
JSON_ATTEMPT_UCI_KEY = "attempted_move_uci"
JSON_ATTEMPT_PWIN_AFTER_9M_KEY = "p_win_after_attempt_9M"
# JSON_ATTEMPT_PWIN_AFTER_136M_KEY = "p_win_after_attempt_136M" # Commented out

# Threshold for considering a blunder "solved" by user's attempt
# e.g., if user's move results in a P(Win) drop less than this from optimal
SOLVED_IMPROVEMENT_THRESHOLD = 0.03 # User's move drop must be < 3% compared to best 9M engine move

# Arrow Styling for Blunder Trainer
BLUNDER_ARROW_WIDTH = ARROW_WIDTH_BASE + 1  # Make blunder arrow slightly thicker
USER_ATTEMPT_ARROW_WIDTH = ARROW_WIDTH_BASE  # Standard width for user attempt
ENGINE_9M_HINT_COLORS = HINT_PALETTE_1 # Use the first hint palette for 9M suggestions

_num_9m_hint_colors = len(ENGINE_9M_HINT_COLORS)
ENGINE_ARROW_WIDTHS = [max(1, ARROW_WIDTH_BASE - j) for j in range(_num_9m_hint_colors)]
if not ENGINE_ARROW_WIDTHS: # Fallback if HINT_PALETTE_1 was empty
    ENGINE_ARROW_WIDTHS = [ARROW_WIDTH_BASE]
