# ===== START OF FILE learned_blunder_tracker.py =====
import json
import os
import logging
import time
from constants_blunder_trainer import JSON_ATTEMPT_KEY, JSON_SOLVED_9M_KEY, JSON_ATTEMPT_UCI_KEY, JSON_ATTEMPT_PWIN_AFTER_9M_KEY

LEARNED_BLUNDERS_FILENAME = "learned_blunders_progress.json" # Ensure this is in constants_blunder_trainer or defined here

class LearnedBlunderTracker:
    def __init__(self, filename=LEARNED_BLUNDERS_FILENAME):
        self.filename = filename
        # Key: FEN_before_blunder (str)
        # Value: dict {
        #    "attempts": list of dicts [{"uci": str, "pwin_after_9M": float, "solved_criteria_met": bool, "timestamp": float}],
        #    "is_marked_overall_solved": bool, # True if any attempt met solved_criteria_met
        #    "last_attempt_timestamp": float,
        #    "original_blunder_move_uci": str, # Store for reference
        #    "original_p_win_drop_9M": float   # Store for reference
        # }
        self.learned_data = {}
        self.has_unsaved_changes = False
        self._load_progress()

    def _get_filepath(self):
        if not os.path.isabs(self.filename):
            try:
                # Try to put it in the same directory as the script running this
                script_dir = os.path.dirname(os.path.abspath(__file__))
            except NameError: # Fallback if __file__ is not defined (e.g. interactive)
                script_dir = os.getcwd()
            return os.path.join(script_dir, self.filename)
        return self.filename

    def _load_progress(self):
        filepath = self._get_filepath()
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    self.learned_data = json.load(f)
                logging.info(f"LearnedBlunderTracker: Loaded progress from {filepath} for {len(self.learned_data)} FENs.")
            except json.JSONDecodeError:
                logging.error(f"LearnedBlunderTracker: Error decoding JSON from {filepath}. Starting fresh.")
                self.learned_data = {}
            except Exception as e:
                logging.error(f"LearnedBlunderTracker: Error loading progress file {filepath}: {e}")
                self.learned_data = {}
        else:
            logging.info(f"LearnedBlunderTracker: No progress file found at {filepath}. Starting fresh.")
            self.learned_data = {}
        self.has_unsaved_changes = False


    def record_attempt(self, fen_before_blunder: str,
                       original_blunder_move_uci: str, original_p_win_drop_9M: float,
                       attempted_uci: str, pwin_after_attempt: float, is_solved_this_attempt: bool):
        """Records an attempt for a given blunder FEN."""
        if fen_before_blunder not in self.learned_data:
            self.learned_data[fen_before_blunder] = {
                "attempts": [],
                "is_marked_overall_solved": False,
                "last_attempt_timestamp": None,
                "original_blunder_move_uci": original_blunder_move_uci,
                "original_p_win_drop_9M": original_p_win_drop_9M
            }
        
        entry = self.learned_data[fen_before_blunder]
        
        attempt_record = {
            "uci": attempted_uci,
            "pwin_after_9M": pwin_after_attempt,
            "solved_criteria_met": is_solved_this_attempt,
            "timestamp": time.time()
        }
        entry["attempts"].append(attempt_record)
        entry["last_attempt_timestamp"] = time.time()

        # Update overall solved status if this attempt solved it and it wasn't already solved
        if is_solved_this_attempt and not entry["is_marked_overall_solved"]:
            entry["is_marked_overall_solved"] = True
            logging.info(f"LearnedBlunderTracker: FEN {fen_before_blunder[:20]}... marked as SOLVED.")
            
        self.has_unsaved_changes = True
        logging.info(f"LearnedBlunderTracker: Recorded attempt for FEN {fen_before_blunder[:20]}...: {attempted_uci}, Solved this time: {is_solved_this_attempt}")

    def get_blunder_status(self, fen_before_blunder: str) -> dict | None:
        """Returns the learning status for a given FEN, or None."""
        return self.learned_data.get(fen_before_blunder)

    def is_blunder_solved(self, fen_before_blunder: str) -> bool:
        status = self.get_blunder_status(fen_before_blunder)
        return status.get("is_marked_overall_solved", False) if status else False

    def save_progress(self) -> bool:
        if not self.has_unsaved_changes:
            logging.info("LearnedBlunderTracker: No unsaved changes to save.")
            return True
            
        filepath = self._get_filepath()
        try:
            # Create directory if it doesn't exist
            dir_name = os.path.dirname(filepath)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name)
                logging.info(f"LearnedBlunderTracker: Created directory {dir_name}")

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.learned_data, f, indent=2)
            logging.info(f"LearnedBlunderTracker: Saved progress to {filepath}.")
            self.has_unsaved_changes = False
            return True
        except Exception as e:
            logging.error(f"LearnedBlunderTracker: Error saving progress to {filepath}: {e}")
            return False

    def reset_blunder_solved_status(self, fen_before_blunder: str):
        """Allows un-solving a blunder for review."""
        if fen_before_blunder in self.learned_data:
            if self.learned_data[fen_before_blunder]["is_marked_overall_solved"]:
                self.learned_data[fen_before_blunder]["is_marked_overall_solved"] = False
                self.has_unsaved_changes = True
                logging.info(f"LearnedBlunderTracker: Reset solved status for FEN {fen_before_blunder[:20]}...")
        else:
            logging.warning(f"LearnedBlunderTracker: Attempted to reset status for unknown FEN {fen_before_blunder[:20]}...")


# ===== END OF FILE learned_blunder_tracker.py =====
