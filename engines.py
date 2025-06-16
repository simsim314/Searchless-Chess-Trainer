# engine_manager.py

import chess
import numpy as np
import logging

try:
    from searchless_chess.src.engines import constants as engine_constants_module
    from searchless_chess.src.engines import neural_engines
    from searchless_chess.src.engines import engine as searchless_engine_module
    SEARCHLESS_ENGINES_AVAILABLE = True
except ImportError as e:
    SEARCHLESS_ENGINES_AVAILABLE = False
    logging.critical(f"Failed to import searchless_chess components in engine_manager: {e}")


class SearchlessEngineManager:
    def __init__(self):
        self.engine_9M = None
        self.engine_136M = None
        if not SEARCHLESS_ENGINES_AVAILABLE:
            logging.warning("Searchless_chess library not available. Engines cannot be loaded.")

    def load_engines(self, load_136m_flag: bool = True): # Parameter with default True
        """
        Loads the searchless_chess engines.
        By default, attempts to load both 9M and 136M engines.
        Set load_136m_flag to False to only attempt loading the 9M engine.
        """
        if not SEARCHLESS_ENGINES_AVAILABLE:
            logging.error("Cannot load engines: searchless_chess components are not available.")
            return False # Indicate failure to load any engine

        loaded_9M_successfully = False
        if self.engine_9M is None: # Only load if not already loaded
            try:
                logging.info("Attempting to load 9M engine...")
                self.engine_9M = engine_constants_module.ENGINE_BUILDERS['9M']()
                #self.engine_9M = engine_constants_module.ENGINE_BUILDERS['270M']()
                logging.info("9M engine loaded successfully.")
                loaded_9M_successfully = True
            except KeyError:
                logging.error("9M engine builder key not found in searchless_chess constants.")
            except Exception as e:
                logging.error(f"Failed to load 9M engine: {e}", exc_info=True)
        else:
            logging.info("9M engine already loaded.")
            loaded_9M_successfully = True # Considered successful if already there

        loaded_136M_successfully = False
        if load_136m_flag:
            if self.engine_136M is None: # Only load if not already loaded
                if '136M' in engine_constants_module.ENGINE_BUILDERS:
                    try:
                        logging.info("Attempting to load 136M engine...")
                        self.engine_136M = engine_constants_module.ENGINE_BUILDERS['136M']()
                        logging.info("136M engine loaded successfully.")
                        loaded_136M_successfully = True
                    except KeyError: # Should be caught by 'in' check ideally
                        logging.error("136M engine builder key was present but failed on access.")
                    except Exception as e:
                        logging.error(f"Failed to load 136M engine: {e}", exc_info=True)
                else:
                    logging.warning("136M engine builder not found in searchless_chess constants. Cannot load.")
            else:
                logging.info("136M engine already loaded.")
                loaded_136M_successfully = True # Considered successful if already there
        else:
            self.engine_136M = None # Explicitly ensure 136M is None if flag is false
            logging.info("136M engine loading intentionally skipped due to load_136m_flag=False.")

        # Determine overall success based on what was attempted and what succeeded
        if not loaded_9M_successfully:
            if load_136m_flag and not loaded_136M_successfully:
                logging.warning("Failed to load any engines (9M failed, 136M attempt also failed or skipped).")
                return False
            elif not load_136m_flag:
                logging.warning("Failed to load 9M engine (136M loading was skipped). No engines available.")
                return False
        
        return True # At least 9M loaded, or 136M loaded if 9M failed but 136M was attempted

    def get_engine_analysis(self, engine_instance, board_state: chess.Board):
            return engine_instance.analyse(board_state)
        

    def _get_p_win_from_analysis_output(self, engine_instance, analysis_output, board_state: chess.Board, player_to_evaluate: chess.Color):
        if not analysis_output or not engine_instance: return 0.5
        if analysis_output.get('is_terminal'):
            current_board_copy = board_state.copy() 
            if current_board_copy.is_checkmate():
                return 0.0 if current_board_copy.turn == player_to_evaluate else 1.0
            return 0.5 
        log_probs_per_action_bucket = analysis_output.get('log_probs')
        if log_probs_per_action_bucket is None or \
           log_probs_per_action_bucket.shape[0] == 0 or \
           not hasattr(engine_instance, '_return_buckets_values') or \
           engine_instance._return_buckets_values is None:
            logging.warning(f"P(Win) calc: Missing data for FEN: {board_state.fen()}. Output: {analysis_output}")
            current_board_copy = board_state.copy()
            if current_board_copy.is_game_over(claim_draw=True):
                result = current_board_copy.result(claim_draw=True)
                if result == "1-0": return 1.0 if player_to_evaluate == chess.WHITE else 0.0
                elif result == "0-1": return 0.0 if player_to_evaluate == chess.WHITE else 1.0
                else: return 0.5
            return 0.5 
        return_buckets_probs = np.exp(log_probs_per_action_bucket)
        safe_sum = np.sum(return_buckets_probs, axis=1, keepdims=True)
        safe_sum[safe_sum == 0] = 1e-9 
        normalized_bucket_probs_per_action = return_buckets_probs / safe_sum
        action_win_probabilities = np.sum(normalized_bucket_probs_per_action * engine_instance._return_buckets_values, axis=1)
        p_win_for_player_to_move_on_board = np.max(action_win_probabilities) if len(action_win_probabilities) > 0 else 0.5
        if board_state.turn == player_to_evaluate:
            return float(p_win_for_player_to_move_on_board)
        else:
            return float(1.0 - p_win_for_player_to_move_on_board)

    def _get_top_moves_from_analysis_output(self, engine_instance, analysis_output, board_state: chess.Board, num_moves=3):
        top_moves_info = []
        if not analysis_output or not engine_instance: return top_moves_info
        log_probs = analysis_output.get('log_probs')
        if log_probs is not None and log_probs.shape[0] > 0 and \
           hasattr(engine_instance, '_return_buckets_values') and \
           engine_instance._return_buckets_values is not None:
            return_buckets_probs = np.exp(log_probs)
            safe_sum = np.sum(return_buckets_probs, axis=1, keepdims=True); safe_sum[safe_sum == 0] = 1e-9
            normalized_bucket_probs_per_action = return_buckets_probs / safe_sum
            action_p_wins = np.sum(normalized_bucket_probs_per_action * engine_instance._return_buckets_values, axis=1)
            legal_moves = searchless_engine_module.get_ordered_legal_moves(board_state.copy())
            if len(legal_moves) == len(action_p_wins):
                moves_with_scores = []
                temp_board_for_san = board_state.copy()
                for i, move in enumerate(legal_moves):
                    try: san = temp_board_for_san.san(move)
                    except ValueError: san = move.uci() + " (SAN Error)"
                    moves_with_scores.append({'san': san, 'uci': move.uci(), 'p_win': float(action_p_wins[i])})
                moves_with_scores.sort(key=lambda x: x['p_win'], reverse=True)
                top_moves_info = moves_with_scores[:num_moves]
            else: logging.warning(f"Mismatched moves ({len(legal_moves)}) and p_wins ({len(action_p_wins)}) for FEN: {board_state.fen()}.")
        else: logging.warning(f"Could not get top moves: Missing data for FEN: {board_state.fen()}. AO: {analysis_output}")
        return top_moves_info

    def calculate_p_win_for_player(self, engine_instance, board_state: chess.Board, player_to_evaluate: chess.Color, analysis_output=None):
        if not engine_instance: return 0.5
        current_board_copy = board_state.copy()
        if current_board_copy.is_game_over(claim_draw=True):
            result = current_board_copy.result(claim_draw=True)
            if result == "1-0": return 1.0 if player_to_evaluate == chess.WHITE else 0.0
            elif result == "0-1": return 0.0 if player_to_evaluate == chess.WHITE else 1.0
            else: return 0.5
        if analysis_output is None: 
            analysis_output = self.get_engine_analysis(engine_instance, current_board_copy)
        return self._get_p_win_from_analysis_output(engine_instance, analysis_output, current_board_copy, player_to_evaluate)

    def get_top_engine_moves_list(self, engine_instance, board_state: chess.Board, num_moves=3, analysis_output=None):
        if not engine_instance: return []
        current_board_copy = board_state.copy()
        if current_board_copy.is_game_over(claim_draw=True): return []
        if analysis_output is None: 
            analysis_output = self.get_engine_analysis(engine_instance, current_board_copy)
        return self._get_top_moves_from_analysis_output(engine_instance, analysis_output, current_board_copy, num_moves)
