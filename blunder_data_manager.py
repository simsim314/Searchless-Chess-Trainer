import json
import os
import logging
from constants_blunder_trainer import BLUNDER_REPORT_FILE, DEFAULT_GUI_BLUNDER_THRESHOLD
from learned_blunder_tracker import LearnedBlunderTracker

NEGLIGIBLE_PWIN_DROP_FOR_FAKE_BLUNDER_CHECK = 0.01

class BlunderDataManager:
    def __init__(self, blunder_file=BLUNDER_REPORT_FILE,
                 threshold=DEFAULT_GUI_BLUNDER_THRESHOLD):
        self.blunder_file = blunder_file
        self.threshold = threshold
        self.all_blunders_from_file = []
        self.training_blunders = []
        self.current_index = -1
        self.learned_tracker = LearnedBlunderTracker()
        self.show_only_unsolved = True # This flag will now cover both "solved by PWin" and "solved by finding engine's #1"

    def load_blunders(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, self.blunder_file)

        if not os.path.exists(file_path):
            logging.error(f"Blunder file not found: {file_path}")
            return False

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.all_blunders_from_file = data.get("blunders", [])
            self._filter_and_sort_training_blunders()
            #logging.info(f"Loaded {len(self.all_blunders_from_file)} blunders from file. "
            #             f"{len(self.training_blunders)} selected for current training session.")
            return True
        except Exception as e:
            logging.error(f"Error loading blunders: {e}")
            return False

    def _filter_and_sort_training_blunders(self):
        candidate_blunders = []
        skipped_count = {
            "malformed": 0,
            "fake_blunder_uci_is_engine_top_and_negligible_drop": 0,
            "fake_blunder_uci_is_engine_top_but_drop_is_significant_warning": 0,
            "below_threshold": 0,
            "solved_by_pwin_improvement": 0,
            "solved_by_finding_engine_top_move": 0
        }

        for b_idx, b_data in enumerate(self.all_blunders_from_file):
            # Basic data integrity check
            required_keys = ['p_win_drop_9M', 'fen_before_blunder', 'blunder_move_uci', 'top_moves_9M_before_blunder']
            if not (isinstance(b_data, dict) and all(key in b_data for key in required_keys)):
                #logging.warning(f"Skipping malformed blunder data (missing keys) at index {b_idx}: {str(b_data)[:100]}...")
                skipped_count["malformed"] += 1
                continue

            fen = b_data['fen_before_blunder']
            blunder_move_uci = b_data['blunder_move_uci']
            p_win_drop = b_data['p_win_drop_9M']
            top_moves_9m_for_original_pos = b_data.get('top_moves_9M_before_blunder', [])

            # 1. Check for "fake" blunders (reported blunder_move_uci is engine's best)
            is_blunder_move_engines_top = False
            engine_top_move_uci_original = None
            if top_moves_9m_for_original_pos and isinstance(top_moves_9m_for_original_pos, list) and \
               len(top_moves_9m_for_original_pos) > 0 and isinstance(top_moves_9m_for_original_pos[0], dict):
                engine_top_move_uci_original = top_moves_9m_for_original_pos[0].get('uci')
                if engine_top_move_uci_original == blunder_move_uci:
                    is_blunder_move_engines_top = True

            if is_blunder_move_engines_top:
                if p_win_drop < NEGLIGIBLE_PWIN_DROP_FOR_FAKE_BLUNDER_CHECK:
                    #logging.info(f"Skipping 'fake' blunder (blunder_move is engine's top AND p_win_drop negligible): FEN {fen[:20]}..., Blunder: {blunder_move_uci}, p_win_drop: {p_win_drop:.3f}")
                    skipped_count["fake_blunder_uci_is_engine_top_and_negligible_drop"] += 1
                    continue
                else:
                    #logging.warning(f"Data Anomaly & Skipping: Blunder UCI ({blunder_move_uci}) matches engine's top UCI ({engine_top_move_uci_original}), but p_win_drop ({p_win_drop:.3f}) is significant. FEN {fen[:20]}... This suggests an issue in source data. Skipping.")
                    skipped_count["fake_blunder_uci_is_engine_top_but_drop_is_significant_warning"] +=1
                    continue

            # 2. Apply p_win_drop threshold (if not already skipped as fake)
            if p_win_drop < self.threshold:
                skipped_count["below_threshold"] += 1
                continue

            # 3. Apply learning status filter if show_only_unsolved is True
            if self.show_only_unsolved:
                # 3a. Check if overall solved by PWin improvement criteria
                if self.learned_tracker.is_blunder_solved(fen):
                    #logging.debug(f"Skipping blunder (marked overall solved by PWin improvement): FEN {fen[:20]}...")
                    skipped_count["solved_by_pwin_improvement"] += 1
                    continue

                # 3b. NEW CHECK: Check if user previously found the engine's #1 move for this FEN
                blunder_status_from_tracker = self.learned_tracker.get_blunder_status(fen)
                if blunder_status_from_tracker and engine_top_move_uci_original:
                    user_found_engine_top_move = False
                    for attempt in blunder_status_from_tracker.get("attempts", []):
                        if attempt.get("uci") == engine_top_move_uci_original:
                            user_found_engine_top_move = True
                            break
                    if user_found_engine_top_move:
                        #logging.debug(f"Skipping blunder (user previously found engine's #1 move '{engine_top_move_uci_original}'): FEN {fen[:20]}...")
                        skipped_count["solved_by_finding_engine_top_move"] += 1
                        continue
            
            candidate_blunders.append(b_data)

        self.training_blunders = candidate_blunders
        logging.info(f"Filtering complete. Candidates for training: {len(self.training_blunders)}. Skipped counts: {skipped_count}")

        if not self.training_blunders and self.all_blunders_from_file:
            logging.warning("No blunders meet the current training criteria after all filters.")

    def record_attempt_for_current_blunder(self, attempted_uci: str, pwin_after_attempt: float, is_solved_this_attempt: bool):
        current_blunder = self.get_current_blunder()
        if current_blunder:
            fen = current_blunder['fen_before_blunder']
            original_uci = current_blunder['blunder_move_uci']
            original_drop = current_blunder['p_win_drop_9M']
            self.learned_tracker.record_attempt(fen, original_uci, original_drop,
                                                attempted_uci, pwin_after_attempt, is_solved_this_attempt)
            # No dynamic removal from self.training_blunders here. Filter is applied at load time.

    def save_learning_progress(self):
        self.learned_tracker.save_progress()

    def set_show_only_unsolved(self, show_unsolved: bool):
        if self.show_only_unsolved != show_unsolved:
            self.show_only_unsolved = show_unsolved
            self.current_index = -1 # Reset index
            self._filter_and_sort_training_blunders() # Re-apply all filters
            logging.info(f"Filter 'show_only_unsolved' changed to {self.show_only_unsolved}. "
                         f"Refiltered. {len(self.training_blunders)} blunders now available for training.")

    def get_current_blunder(self):
        if 0 <= self.current_index < len(self.training_blunders):
            return self.training_blunders[self.current_index]
        return None

    def next_blunder(self):
        if self.training_blunders: # Check if the list is not empty
            self.current_index = (self.current_index + 1) % len(self.training_blunders)
        else:
            self.current_index = -1 # No blunders to cycle through

    def prev_blunder(self):
        if self.training_blunders: # Check if the list is not empty
            self.current_index = (self.current_index - 1 + len(self.training_blunders)) % len(self.training_blunders)
        else:
            self.current_index = -1

    def has_blunders(self):
        return len(self.training_blunders) > 0

    def get_blunder_count(self):
        return len(self.training_blunders)

    def get_current_index_display(self):
        return self.current_index + 1 if self.has_blunders() else 0

# ===== END OF FILE blunder_data_manager.py =====
