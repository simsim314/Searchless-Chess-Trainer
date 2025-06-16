# ===== START OF FILE game_manager.py =====
import chess
# import logging # Ensure this is removed if present
from engines import SearchlessEngineManager 
from utils import setup_asymmetric_chess960

class GameManager:
    def __init__(self):
        self.board: chess.Board = chess.Board(chess960=True) 
        self.player_color = chess.WHITE 
        self.current_engine_instance = None
        self._is_game_active = False

    def start_new_game(self, player_color: chess.Color = chess.WHITE, engine_instance = None):
        self.board = setup_asymmetric_chess960() 
        self.player_color = player_color
        self.current_engine_instance = engine_instance
        self._is_game_active = True

    def get_board_object(self) -> chess.Board:
        return self.board

    def get_board_fen(self) -> str: 
        return self.board.fen()

    def is_player_turn(self) -> bool:
        return self._is_game_active and self.board.turn == self.player_color

    def get_player_color(self) -> bool:
        return self.player_color

    def set_player_color(self, new_player_color: chess.Color):
        if new_player_color in [chess.WHITE, chess.BLACK]:
            self.player_color = new_player_color
        # else part removed as it only contained a commented-out log

    def make_player_move(self, uci_move: str) -> bool:
        if not self.is_player_turn():
            return False
        
        try:
            move = self.board.parse_uci(uci_move)
        except ValueError: # Simplified: if parse_uci fails, it's an invalid format
            return False

        is_in_legal_moves = move in self.board.legal_moves

        if is_in_legal_moves: 
            self.board.push(move)
            return True
        else:
            return False

    def get_engine_move_uci(self, engine_manager: SearchlessEngineManager, for_color: chess.Color | None = None) -> str | None:
        if not self._is_game_active or not self.current_engine_instance:
            return None

        board_copy_for_analysis = self.board.copy()
        
        num_moves_to_consider_for_anti_draw = 5 
        ANTI_DRAW_P_WIN_THRESHOLD = 0.6 
        
        is_model_engine_needing_anti_draw = self.current_engine_instance == engine_manager.engine_9M # Assuming engine_9M is the model
        
        top_moves_data = engine_manager.get_top_engine_moves_list(
            self.current_engine_instance, board_copy_for_analysis, 
            num_moves=num_moves_to_consider_for_anti_draw if is_model_engine_needing_anti_draw else 1
        )

        if not top_moves_data:
            return None

        if is_model_engine_needing_anti_draw and len(top_moves_data) > 0: # Check len > 0 for safety
            original_top_move_info = top_moves_data[0]
            original_top_move_obj = board_copy_for_analysis.parse_uci(original_top_move_info['uci'])
            
            board_if_top_move = board_copy_for_analysis.copy()
            board_if_top_move.push(original_top_move_obj)
            
            is_repetition_with_top_move = board_if_top_move.is_repetition(3)

            if is_repetition_with_top_move:
                # Search for an alternative non-repeating move that meets the P(Win) threshold
                for alternative_move_info in top_moves_data[1:]: # Skip the original top move
                    alt_move_p_win = alternative_move_info.get('p_win', 0.0)
                    if alt_move_p_win >= ANTI_DRAW_P_WIN_THRESHOLD:
                        alt_move_obj = board_copy_for_analysis.parse_uci(alternative_move_info['uci'])
                        board_if_alt_move = board_copy_for_analysis.copy()
                        board_if_alt_move.push(alt_move_obj)
                        if not board_if_alt_move.is_repetition(3):
                            # Found a suitable non-repeating alternative
                            return alternative_move_info['uci']
                # If no suitable non-repeating alternative found, fall back to the original top move
                return original_top_move_info['uci']
            else:
                # Top move does not lead to repetition, so use it
                return original_top_move_info['uci']
        elif top_moves_data: # Not the model or only one move considered, just return the best one
            return top_moves_data[0]['uci']
        else: # Should be caught by 'if not top_moves_data' earlier, but as a fallback
            return None


    def make_move_on_board(self, uci_move: str) -> bool: 
        if not self._is_game_active:
            return False
        try:
            move = self.board.parse_uci(uci_move)
            if move in self.board.legal_moves: 
                self.board.push(move)
                return True
            else: 
                return False
        except ValueError:
            return False

    def is_game_over(self) -> bool:
        return self.board.is_game_over() if self._is_game_active else False

    def get_game_result(self) -> str | None:
        if not self.is_game_over():
            return None
        
        result = self.board.result(claim_draw=True) 
        if result == "1-0": return "White wins!"
        if result == "0-1": return "Black wins!"
        if result == "1/2-1/2": return "Draw!"
        
        if self.board.is_stalemate(): return "Draw by stalemate!"
        if self.board.is_insufficient_material(): return "Draw by insufficient material!"
        if self.board.is_seventyfive_moves(): return "Draw by 75-move rule!"
        if self.board.is_fivefold_repetition(): return "Draw by fivefold repetition!"
        return "Game over, unknown result." 

    def get_board_orientation_white_pov(self) -> bool:
        return self.player_color == chess.WHITE
        
    def is_active(self) -> bool:
        return self._is_game_active

    def has_moves_to_take_back(self) -> bool:
        return self._is_game_active and len(self.board.move_stack) > 0

    def take_back_move(self) -> bool:
        if not self.has_moves_to_take_back():
            return False

        self.board.pop()

        if self.has_moves_to_take_back() and not self.is_player_turn():
            self.board.pop()
        
        return True

# ===== END OF FILE game_manager.py =====
