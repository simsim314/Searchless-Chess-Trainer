# ===== START OF FILE pgn_analyzer_controller.py =====
import chess
import chess.pgn
import logging
from typing import List, Dict, Any
import time

from engines import SearchlessEngineManager
from pgn_manager import PgnManager
from utils import pwin_to_cp, format_score_for_display
from constants import (
    HINT_PALETTE_1, HINT_PALETTE_2, HINT_COMBINED_COLOR,
    ARROW_WIDTH_BASE, USER_PGN_MOVE_COLOR, PGN_MAINLINE_MOVE_COLOR,
    PLAYER_MOVE_COLOR, ENGINE_MOVE_COLOR
)
import chess_draw_utils as cdu

# (Constants for move quality symbols remain the same)
MOVE_QUALITY_BEST = "!\n"
MOVE_QUALITY_GOOD = "👍\n"
MOVE_QUALITY_INTERESTING = "!?\n"
MOVE_QUALITY_WEAK = "?\n"
MOVE_QUALITY_BLUNDER = "??\n"
MOVE_QUALITY_UNKNOWN = ""
BLUNDER_THRESHOLD = 0.15
WEAK_MOVE_THRESHOLD = 0.05
INTERESTING_MOVE_MAX_DROP = 0.05
GOOD_MOVE_MAX_DROP = 0.03
INTERESTING_MOVE_TOP_N_THRESHOLD = 5
GOOD_MOVE_TOP_N_THRESHOLD = 3

class PgnAnalyzerController:
    def __init__(self, board_widget, feedback_panel, engine_manager, gui_callback_manager=None):
        self.board_widget = board_widget
        self.feedback_panel = feedback_panel
        self.engine_manager = engine_manager
        self.gui_callbacks = gui_callback_manager

        self.pgn_manager = PgnManager()
        self.analysis_results: List[Dict[str, Any]] = []
        self.current_move_index = -1
        self.tracked_player_name = ""
        self.tracked_player_color = None
        self.total_plies = 0

        self.interaction_mode = 'analysis' # 'analysis' or 'play'
        self.board_for_play_mode: chess.Board | None = None
        
        self.board_widget.on_move_attempted_callback = self._handle_user_move_attempt
        self.hint_colors_9m = HINT_PALETTE_1
        self.hint_colors_136m = HINT_PALETTE_2

    def load_and_analyze_pgn(self, pgn_string: str, tracked_player_name: str):
        print("🔄 Starting PGN analysis...")
        self.tracked_player_name = tracked_player_name.lower()
        self.analysis_results = []
        self.current_move_index = -1
        self.total_plies = 0

        if not self.engine_manager.engine_9M or not self.engine_manager.engine_136M:
            if self.gui_callbacks: self.gui_callbacks['show_error']("Engine Error", "Both engines required."); return

        if not self.pgn_manager.load_pgn_from_string(pgn_string):
            if self.gui_callbacks: self.gui_callbacks['show_error']("PGN Error", "Could not parse PGN."); return
        
        self.total_plies = self.pgn_manager.get_total_plies_mainline()
        self._determine_player_color()
        if self.tracked_player_color is None:
            if self.gui_callbacks: self.gui_callbacks['show_error']("Player Not Found", f"Player '{tracked_player_name}' not in PGN."); return

        self._perform_full_game_analysis()
        if self.gui_callbacks: self.gui_callbacks['populate_move_list'](self.analysis_results)
        
        if self.analysis_results:
            self.navigate_to_move(0)
        print("✅ PGN analysis complete.")

    def _determine_player_color(self):
        headers = self.pgn_manager.get_headers()
        if headers.get("White", "").lower() == self.tracked_player_name: self.tracked_player_color = chess.WHITE
        elif headers.get("Black", "").lower() == self.tracked_player_name: self.tracked_player_color = chess.BLACK
        else: self.tracked_player_color = None

    def _get_pwin_for_mover(self, engine, board_after_move, player_who_moved):
        if board_after_move.is_game_over(claim_draw=True):
            result = board_after_move.result(claim_draw=True)
            if result == "1-0": return 1.0 if player_who_moved == chess.WHITE else 0.0
            if result == "0-1": return 0.0 if player_who_moved == chess.WHITE else 1.0
            return 0.5
        pwin_for_opponent = self.engine_manager.calculate_p_win_for_player(engine, board_after_move, board_after_move.turn)
        return 1.0 - pwin_for_opponent

    def _get_cp_for_mover(self, pwin_for_mover: float, board_before_move: chess.Board):
        pwin_for_white = pwin_for_mover if board_before_move.turn == chess.WHITE else (1.0 - pwin_for_mover)
        return pwin_to_cp(pwin_for_white)

    def _perform_full_game_analysis(self):
        if self.gui_callbacks: self.gui_callbacks['update_status']("Analyzing game...")
        node = self.pgn_manager.game
        while node.variations:
            node = node.variations[0]; move = node.move; board_before_move = node.parent.board()
            move_num_str = f"{(node.ply() + 1) // 2}.{'..' if node.ply() % 2 == 0 else ''}"
            print(f"🔄 Analyzing move {node.ply()}/{self.total_plies} ({move_num_str} {board_before_move.san(move)})")
            
            analysis_entry = { "ply": node.ply(), "move_san": board_before_move.san(move), "move_uci": move.uci(), "fen_before_move": board_before_move.fen(), "is_tracked_player_move": board_before_move.turn == self.tracked_player_color, "quality_symbol": MOVE_QUALITY_UNKNOWN, }
            analysis_entry["top_moves_9m"] = self.engine_manager.get_top_engine_moves_list(self.engine_manager.engine_9M, board_before_move, num_moves=5)
            analysis_entry["top_moves_136m"] = self.engine_manager.get_top_engine_moves_list(self.engine_manager.engine_136M, board_before_move, num_moves=5)
            
            board_after_actual_move = board_before_move.copy(); board_after_actual_move.push(move)
            analysis_entry["pwin_after_move_136m"] = self._get_pwin_for_mover(self.engine_manager.engine_136M, board_after_actual_move, board_before_move.turn)
            analysis_entry["pwin_after_move_9m"] = self._get_pwin_for_mover(self.engine_manager.engine_9M, board_after_actual_move, board_before_move.turn)

            if analysis_entry["is_tracked_player_move"] and analysis_entry["top_moves_136m"]:
                pwin_optimal_136m = analysis_entry["top_moves_136m"][0]['p_win']
                pwin_drop = pwin_optimal_136m - analysis_entry["pwin_after_move_136m"]
                analysis_entry["pwin_drop_136m"] = pwin_drop
                cp_optimal = self._get_cp_for_mover(pwin_optimal_136m, board_before_move)
                cp_after_actual = self._get_cp_for_mover(analysis_entry["pwin_after_move_136m"], board_before_move)
                analysis_entry["cp_loss"] = cp_optimal - cp_after_actual
                move_rank = next((i for i, m in enumerate(analysis_entry["top_moves_136m"]) if m['uci'] == move.uci()), -1)
                if pwin_drop > BLUNDER_THRESHOLD: analysis_entry["quality_symbol"] = MOVE_QUALITY_BLUNDER
                elif pwin_drop > WEAK_MOVE_THRESHOLD: analysis_entry["quality_symbol"] = MOVE_QUALITY_WEAK
                elif move_rank == 0: analysis_entry["quality_symbol"] = MOVE_QUALITY_BEST
                elif pwin_drop <= GOOD_MOVE_MAX_DROP and 0 < move_rank < GOOD_MOVE_TOP_N_THRESHOLD: analysis_entry["quality_symbol"] = MOVE_QUALITY_GOOD
                elif pwin_drop <= INTERESTING_MOVE_MAX_DROP and (move_rank == -1 or move_rank >= INTERESTING_MOVE_TOP_N_THRESHOLD): analysis_entry["quality_symbol"] = MOVE_QUALITY_INTERESTING
                else: analysis_entry["quality_symbol"] = MOVE_QUALITY_GOOD
            self.analysis_results.append(analysis_entry)
            if self.gui_callbacks: self.gui_callbacks['update_progress'](node.ply(), self.total_plies)
        if self.gui_callbacks: self.gui_callbacks['update_status']("Analysis complete.")
        if self.gui_callbacks and self.analysis_results: self.gui_callbacks['update_move_selection'](self.current_move_index if self.current_move_index != -1 else 0)

    def _handle_user_move_attempt(self, uci: str):
        if self.interaction_mode == 'play':
            self._handle_play_mode_move(uci)

    def _handle_play_mode_move(self, uci: str):
        move = chess.Move.from_uci(uci)
        if move in self.board_for_play_mode.legal_moves:
            self.board_for_play_mode.push(move)
            self.board_widget.set_position(self.board_for_play_mode.fen())
            self._redraw_visuals_for_current_move()
            if self.board_for_play_mode.is_game_over():
                self.feedback_panel.update_feedback(f"Game Over: {self.board_for_play_mode.result()}")
                self.board_widget.set_interaction_enabled(False)
            else:
                self.feedback_panel.update_feedback("Engine thinking...")
                self.board_widget.set_interaction_enabled(False)
                if self.gui_callbacks: self.gui_callbacks['update_button_states']()
                self.board_widget.parent.after(100, self._trigger_engine_move_for_play_mode)
    
    def _trigger_engine_move_for_play_mode(self):
        top_moves = self.engine_manager.get_top_engine_moves_list(self.engine_manager.engine_9M, self.board_for_play_mode, 1)
        if top_moves:
            engine_move = chess.Move.from_uci(top_moves[0]['uci'])
            self.board_for_play_mode.push(engine_move)
            self.board_widget.set_position(self.board_for_play_mode.fen())
            self._redraw_visuals_for_current_move()
        self.board_widget.set_interaction_enabled(True)
        if self.gui_callbacks: self.gui_callbacks['update_button_states']()

    def action_play_from_here(self):
        if self.interaction_mode != 'analysis' or self.current_move_index < 0: return
        self.interaction_mode = 'play'
        fen = self.analysis_results[self.current_move_index]['fen_before_move']
        self.board_for_play_mode = chess.Board(fen)
        self.board_widget.set_interaction_enabled(True)
        self._redraw_visuals_for_current_move()
        if self.gui_callbacks: self.gui_callbacks['update_button_states']()

    def action_return_to_analysis(self):
        if self.interaction_mode != 'play': return
        self.interaction_mode = 'analysis'
        self.board_for_play_mode = None
        self.board_widget.set_interaction_enabled(False)
        self._redraw_visuals_for_current_move()
        if self.gui_callbacks: self.gui_callbacks['update_button_states']()

    def navigate_to_move(self, index: int):
        if self.interaction_mode != 'analysis' or not (0 <= index < len(self.analysis_results)): return
        self.current_move_index = index
        self._redraw_visuals_for_current_move()
        if self.gui_callbacks: self.gui_callbacks['update_move_selection'](index)

    def _draw_hint_on_board(self, move_uci: str, cp_val_for_mover: int, color: str, width: int):
        self.board_widget.draw_arrow(move_uci, color, width)
        move = chess.Move.from_uci(move_uci)
        cp_text = format_score_for_display(cp_val_for_mover, is_cp=True)
        self.board_widget.draw_text_on_square(move.to_square, cp_text, color)

    def _redraw_visuals_for_current_move(self):
        if self.interaction_mode == 'analysis':
            self._redraw_for_analysis_mode()
        elif self.interaction_mode == 'play':
            self._redraw_for_play_mode()

    def _redraw_for_analysis_mode(self):
        move_data = self.analysis_results[self.current_move_index]
        board_before_move = chess.Board(move_data["fen_before_move"])
        self.board_widget.set_position(move_data["fen_before_move"])
        if self.board_widget.white_at_bottom != (self.tracked_player_color == chess.WHITE): self.board_widget.flip_board_orientation()
        else: self.board_widget.clear_visual_cues(); self.board_widget.redraw_pieces_only()
        
        top_moves_9m = {m['uci']: m for m in move_data.get("top_moves_9m", [])[:3]}
        top_moves_136m = {m['uci']: m for m in move_data.get("top_moves_136m", [])[:3]}
        hints_panel_text = ""
        
        pwin_9m_after = move_data.get("pwin_after_move_9m", 0.5); pwin_136m_after = move_data.get("pwin_after_move_136m", 0.5)
        cp_9m_after = self._get_cp_for_mover(pwin_9m_after, board_before_move); cp_136m_after = self._get_cp_for_mover(pwin_136m_after, board_before_move)
        
        if move_data["is_tracked_player_move"]:
            cp_loss_str = format_score_for_display(move_data.get("cp_loss", 0), True)
            feedback_str = f"Your move: {move_data['move_san']} ({move_data['quality_symbol']})\nCP Loss (vs 136M best): {cp_loss_str}"
            label_text = f"{move_data['quality_symbol']} ({format_score_for_display(cp_136m_after, True)})"
            hints_panel_text = f"Your Move: {move_data['move_san']}\n  - 9M: {format_score_for_display(cp_9m_after, True)}  |  136M: {format_score_for_display(cp_136m_after, True)}\n"
        else:
            feedback_str = f"Opponent's move: {move_data['move_san']}"
            label_text = format_score_for_display(cp_136m_after, True)
            hints_panel_text = f"Opponent's Move: {move_data['move_san']}\n  - 9M: {format_score_for_display(cp_9m_after, True)}  |  136M: {format_score_for_display(cp_136m_after, True)}\n"

        self.board_widget.draw_arrow(move_data["move_uci"], USER_PGN_MOVE_COLOR, ARROW_WIDTH_BASE + 1)
        self.board_widget.draw_text_on_square(chess.Move.from_uci(move_data["move_uci"]).to_square, label_text, USER_PGN_MOVE_COLOR)
        self.feedback_panel.update_feedback(feedback_str)
        
        all_ucis = set(top_moves_9m.keys()) | set(top_moves_136m.keys())
        if move_data["move_uci"] in all_ucis: all_ucis.remove(move_data["move_uci"])

        processed_hints = [{'uci': uci, 'san': top_moves_136m.get(uci, {}).get('san') or top_moves_9m.get(uci, {}).get('san', uci), 'p_win_9m': top_moves_9m[uci]['p_win'] if uci in top_moves_9m else None, 'p_win_136m': top_moves_136m[uci]['p_win'] if uci in top_moves_136m else None} for uci in all_ucis]
        
        # The engine's p_win is always for the side to move, so higher is always better.
        processed_hints.sort(key=lambda x: x['p_win_136m'] if x['p_win_136m'] is not None else x['p_win_9m'], reverse=True)
        
        hints_panel_text += "\n---Suggestions---\n"
        for i, hint in enumerate(processed_hints[:4]):
            width = max(1, ARROW_WIDTH_BASE - 1 - i)
            cp_9m = self._get_cp_for_mover(hint['p_win_9m'], board_before_move) if hint['p_win_9m'] is not None else None
            cp_136m = self._get_cp_for_mover(hint['p_win_136m'], board_before_move) if hint['p_win_136m'] is not None else None
            if cp_9m is not None and cp_136m is not None:
                hints_panel_text += f"  - [Both] {hint['san']} (9M: {format_score_for_display(cp_9m, True)}, 136M: {format_score_for_display(cp_136m, True)})\n"
                self._draw_hint_on_board(hint['uci'], cp_136m, HINT_COMBINED_COLOR, width)
            elif cp_136m is not None:
                hints_panel_text += f"  - [136M] {hint['san']} (CP: {format_score_for_display(cp_136m, True)})\n"
                self._draw_hint_on_board(hint['uci'], cp_136m, self.hint_colors_136m[0], width)
            elif cp_9m is not None:
                hints_panel_text += f"  - [9M]   {hint['san']} (CP: {format_score_for_display(cp_9m, True)})\n"
                self._draw_hint_on_board(hint['uci'], cp_9m, self.hint_colors_9m[0], width)
        self.feedback_panel.update_hints(hints_panel_text)

    def _redraw_for_play_mode(self):
        self.board_widget.clear_visual_cues()
        if self.board_for_play_mode.move_stack:
            last_move = self.board_for_play_mode.move_stack[-1]
            color = ENGINE_MOVE_COLOR if self.board_for_play_mode.turn == self.tracked_player_color else PLAYER_MOVE_COLOR
            self.board_widget.draw_arrow(last_move.uci(), color, ARROW_WIDTH_BASE)
        
        self.feedback_panel.update_feedback(f"Play Mode: {chess.COLOR_NAMES[self.board_for_play_mode.turn]}'s turn to move.")

        top_moves_9m = {m['uci']: m for m in self.engine_manager.get_top_engine_moves_list(self.engine_manager.engine_9M, self.board_for_play_mode, num_moves=3)}
        top_moves_136m = {m['uci']: m for m in self.engine_manager.get_top_engine_moves_list(self.engine_manager.engine_136M, self.board_for_play_mode, num_moves=3)}
        all_ucis = set(top_moves_9m.keys()) | set(top_moves_136m.keys())

        processed_hints = [{'uci': uci, 'san': top_moves_136m.get(uci, {}).get('san') or top_moves_9m.get(uci, {}).get('san', uci), 'p_win_9m': top_moves_9m[uci]['p_win'] if uci in top_moves_9m else None, 'p_win_136m': top_moves_136m[uci]['p_win'] if uci in top_moves_136m else None} for uci in all_ucis]
        
        # The engine's p_win is always for the side to move, so higher is always better.
        processed_hints.sort(key=lambda x: x['p_win_136m'] if x['p_win_136m'] is not None else x['p_win_9m'], reverse=True)
        
        hints_panel_text = "--- Play Mode Hints ---\n"
        for i, hint in enumerate(processed_hints[:4]):
            width = max(1, ARROW_WIDTH_BASE - 1 - i)
            cp_9m = self._get_cp_for_mover(hint['p_win_9m'], self.board_for_play_mode) if hint['p_win_9m'] is not None else None
            cp_136m = self._get_cp_for_mover(hint['p_win_136m'], self.board_for_play_mode) if hint['p_win_136m'] is not None else None
            
            if cp_9m is not None and cp_136m is not None:
                hints_panel_text += f"  - [Both] {hint['san']} (9M: {format_score_for_display(cp_9m, True)}, 136M: {format_score_for_display(cp_136m, True)})\n"
                self._draw_hint_on_board(hint['uci'], cp_136m, HINT_COMBINED_COLOR, width)
            elif cp_136m is not None:
                hints_panel_text += f"  - [136M] {hint['san']} (CP: {format_score_for_display(cp_136m, True)})\n"
                self._draw_hint_on_board(hint['uci'], cp_136m, self.hint_colors_136m[0], width)
            elif cp_9m is not None:
                hints_panel_text += f"  - [9M]   {hint['san']} (CP: {format_score_for_display(cp_9m, True)})\n"
                self._draw_hint_on_board(hint['uci'], cp_9m, self.hint_colors_9m[0], width)
        self.feedback_panel.update_hints(hints_panel_text)

    def handle_board_resize(self):
        self._redraw_visuals_for_current_move()
# ===== END OF FILE pgn_analyzer_controller.py =====