# ===== START OF FILE blunder_trainer_controller.py =====
import chess
import logging
import chess_draw_utils # Ensure this is present
from utils import pwin_to_cp, format_score_for_display # Ensure utils.py is present

from constants_blunder_trainer import (
    ACTUAL_BLUNDER_MOVE_COLOR, BLUNDER_ARROW_WIDTH,
    USER_TRIAL_MOVE_COLOR, USER_ATTEMPT_ARROW_WIDTH,
    SOLVED_IMPROVEMENT_THRESHOLD,
    ENGINE_9M_HINT_COLORS, ENGINE_ARROW_WIDTHS,
    JSON_ATTEMPT_KEY, JSON_SOLVED_9M_KEY,
    JSON_ATTEMPT_UCI_KEY, JSON_ATTEMPT_PWIN_AFTER_9M_KEY
)
from constants import (
    SELECTED_SQUARE_HIGHLIGHT_COLOR,
    HINT_PALETTE_1, HINT_PALETTE_2, HINT_COMBINED_COLOR, ARROW_WIDTH_BASE,
    HINT_SCORE_TEXT_COLOR, HINT_SCORE_FONT_FAMILY, HINT_SCORE_FONT_WEIGHT,
    ENGINE_MOVE_COLOR, PLAYER_MOVE_COLOR
)

ENGINE_136M_HINT_COLORS = HINT_PALETTE_2
_num_136m_hint_colors = len(ENGINE_136M_HINT_COLORS)
ENGINE_136M_ARROW_WIDTHS = [max(1, ARROW_WIDTH_BASE - j) for j in range(_num_136m_hint_colors)]
if not ENGINE_136M_ARROW_WIDTHS: ENGINE_136M_ARROW_WIDTHS = [ARROW_WIDTH_BASE]


class BlunderTrainerController:
    def __init__(self, board_widget, feedback_panel, data_manager, engine_manager,
                 gui_update_buttons_callback=None):
        self.board_widget = board_widget
        self.feedback_panel = feedback_panel
        self.data_manager = data_manager
        self.engine_manager = engine_manager
        self.gui_update_buttons_callback = gui_update_buttons_callback

        self.current_interaction_mode = "waiting_for_blunder"
        self.current_blunder_data_active = None
        self.board_for_play_mode = None
        self.player_color_in_play_mode = None
        self.show_hints_in_play_mode_var_tk = None
        self.display_scores_as_cp = True

        self.board_widget.on_move_attempted_callback = self._handle_user_move_attempt

    def set_show_hints_in_play_mode_var(self, tk_bool_var):
        self.show_hints_in_play_mode_var_tk = tk_bool_var

    def _transition_to_mode(self, new_mode: str):
        logging.debug(f"Controller: Transitioning from {self.current_interaction_mode} to {new_mode}")
        old_mode = self.current_interaction_mode
        self.current_interaction_mode = new_mode

        if new_mode == "user_input" or new_mode == "playing_from_blunder_player_turn":
            self.board_widget.set_interaction_enabled(True)
        elif new_mode == "showing_feedback" or new_mode == "waiting_for_blunder" or new_mode == "playing_from_blunder_engine_turn":
            self.board_widget.set_interaction_enabled(False)

        if self.gui_update_buttons_callback and old_mode != new_mode:
            self.gui_update_buttons_callback()

    def load_and_display_current_blunder(self) -> bool:
        self.board_for_play_mode = None
        self.current_blunder_data_active = self.data_manager.get_current_blunder()

        if self.current_blunder_data_active and JSON_ATTEMPT_KEY in self.current_blunder_data_active:
             del self.current_blunder_data_active[JSON_ATTEMPT_KEY]

        if not self.current_blunder_data_active:
            self.feedback_panel.update_blunder_info(None, use_cp_display=self.display_scores_as_cp)
            self.feedback_panel.update_feedback("No blunders available for training in the current filter.")
            self.board_widget.set_position(chess.STARTING_FEN)
            self.board_widget.clear_visual_cues()
            self._transition_to_mode("waiting_for_blunder")
            return False

        fen_before_blunder = self.current_blunder_data_active['fen_before_blunder']
        self.board_widget.set_position(fen_before_blunder)

        temp_board_for_orientation = chess.Board(fen_before_blunder)
        player_who_blundered_color = temp_board_for_orientation.turn
        new_white_at_bottom = (player_who_blundered_color == chess.WHITE)
        if self.board_widget.white_at_bottom != new_white_at_bottom:
            self.board_widget.flip_board_orientation()

        self.board_widget.clear_visual_cues()
        self.board_widget.redraw_pieces_only()

        actual_blunder_uci = self.current_blunder_data_active['blunder_move_uci']
        self.board_widget.draw_arrow(actual_blunder_uci, ACTUAL_BLUNDER_MOVE_COLOR,
                                   BLUNDER_ARROW_WIDTH)

        self.feedback_panel.update_blunder_info(self.current_blunder_data_active, use_cp_display=self.display_scores_as_cp)
        self.feedback_panel.update_feedback("Your turn! Find a better move.")
        self.feedback_panel.clear_hints()
        self._transition_to_mode("user_input")
        return True

    def _handle_user_move_attempt(self, attempted_move_uci: str):
        if self.current_interaction_mode == "user_input" and self.current_blunder_data_active:
            self._handle_user_blunder_fix_attempt(attempted_move_uci)
        elif self.current_interaction_mode == "playing_from_blunder_player_turn" and self.board_for_play_mode:
            self._handle_user_move_in_play_mode(attempted_move_uci)
        else:
            logging.warning(f"Controller: Move attempt in unexpected mode: {self.current_interaction_mode} or missing data.")
            return

    def _handle_user_blunder_fix_attempt(self, attempted_move_uci: str):
        board_at_blunder_pos = chess.Board(self.current_blunder_data_active['fen_before_blunder'])
        try:
            user_trial_move_obj = board_at_blunder_pos.parse_uci(attempted_move_uci)
        except ValueError:
            logging.error(f"Controller: Invalid UCI received for blunder fix: {attempted_move_uci}")
            self.feedback_panel.update_feedback("Invalid move format. Try again.")
            return

        if user_trial_move_obj in board_at_blunder_pos.legal_moves:
            self._evaluate_and_display_user_attempt(user_trial_move_obj)
        else:
            self.feedback_panel.update_feedback(f"Illegal move: {attempted_move_uci}. Try again.")
            self.board_widget.clear_visual_cues()
            self.board_widget.redraw_pieces_only()
            self.board_widget.draw_arrow(self.current_blunder_data_active['blunder_move_uci'], ACTUAL_BLUNDER_MOVE_COLOR, BLUNDER_ARROW_WIDTH)

    def _find_move_in_precalculated_list(self, uci_to_find: str, move_list: list):
        """Helper to find a move in a list of precalculated move dicts (checks top 3)."""
        if not move_list: return None
        for move_info in move_list[:3]: # Only check top 3 as per typical hint display
            if isinstance(move_info, dict) and move_info.get('uci') == uci_to_find:
                return move_info
        return None

    def _evaluate_and_display_user_attempt(self, user_trial_move_obj: chess.Move):
        original_board_state = chess.Board(self.current_blunder_data_active['fen_before_blunder'])
        user_move_san = original_board_state.san(user_trial_move_obj)
        user_move_uci = user_trial_move_obj.uci()

        self.feedback_panel.update_feedback(f"You tried: {user_move_san}. Evaluating...")
        self._transition_to_mode("showing_feedback")

        pwin_val_for_player_after_user_attempt = 0.5 # Default
        player_who_blundered = original_board_state.turn
        evaluation_source = "Unknown" 
        is_solved_overall = False
        
        top_moves_9M_data = self.current_blunder_data_active.get('top_moves_9M_before_blunder', [])
        top_moves_136M_data = self.current_blunder_data_active.get('top_moves_136M_before_blunder', [])

        matched_9m_move_info = self._find_move_in_precalculated_list(user_move_uci, top_moves_9M_data)
        matched_136m_move_info = self._find_move_in_precalculated_list(user_move_uci, top_moves_136M_data)

        optimal_pwin_9m_from_data = top_moves_9M_data[0]['p_win'] if (top_moves_9M_data and isinstance(top_moves_9M_data[0], dict) and 'p_win' in top_moves_9M_data[0]) else None
        optimal_pwin_136m_from_data = top_moves_136M_data[0]['p_win'] if (top_moves_136M_data and isinstance(top_moves_136M_data[0], dict) and 'p_win' in top_moves_136M_data[0]) else None

        if matched_9m_move_info and 'p_win' in matched_9m_move_info:
            pwin_val_for_player_after_user_attempt = matched_9m_move_info['p_win']
            evaluation_source = "Pre-calculated 9M"
            if optimal_pwin_9m_from_data is not None and \
               pwin_val_for_player_after_user_attempt >= (optimal_pwin_9m_from_data - SOLVED_IMPROVEMENT_THRESHOLD):
                is_solved_overall = True
                logging.info(f"Solved based on pre-calculated 9M data. User Pwin: {pwin_val_for_player_after_user_attempt}, Optimal 9M Pwin: {optimal_pwin_9m_from_data}")
        
        if not is_solved_overall and matched_136m_move_info and 'p_win' in matched_136m_move_info:
            # If not already considered solved by 9M match, and 9M didn't match or we prefer 136M's PWin if it also matched
            if evaluation_source == "Unknown" or (not matched_9m_move_info and matched_136m_move_info) :
                 pwin_val_for_player_after_user_attempt = matched_136m_move_info['p_win']
                 evaluation_source = "Pre-calculated 136M" # Update source if we use its P(Win)
            
            if optimal_pwin_136m_from_data is not None and \
               pwin_val_for_player_after_user_attempt >= (optimal_pwin_136m_from_data - SOLVED_IMPROVEMENT_THRESHOLD):
                is_solved_overall = True
                evaluation_source = "Pre-calculated 136M" # Ensure source reflects what solved it
                logging.info(f"Solved based on pre-calculated 136M data. User Pwin: {pwin_val_for_player_after_user_attempt}, Optimal 136M Pwin: {optimal_pwin_136m_from_data}")

        if evaluation_source == "Unknown": # User's move was not in any pre-calculated top N lists
            evaluation_source = "Live Engine 9M"
            if self.engine_manager.engine_9M:
                # A) Get P(Win) after user's move (live)
                board_after_user_attempt = original_board_state.copy()
                board_after_user_attempt.push(user_trial_move_obj)
                analysis_after_user_attempt = self.engine_manager.get_engine_analysis(self.engine_manager.engine_9M, board_after_user_attempt)
                live_pwin_after_user_attempt = self.engine_manager.calculate_p_win_for_player(
                    self.engine_manager.engine_9M, board_after_user_attempt, player_who_blundered,
                    analysis_output=analysis_after_user_attempt
                )
                if live_pwin_after_user_attempt is not None:
                    pwin_val_for_player_after_user_attempt = live_pwin_after_user_attempt
                
                # B) Get P(Win) of optimal move (according to live 9M engine) from original position
                live_top_moves_optimal_list = self.engine_manager.get_top_engine_moves_list( # Renamed for clarity
                    self.engine_manager.engine_9M, original_board_state.copy(), num_moves=1
                )
                live_pwin_optimal_from_engine = None
                if live_top_moves_optimal_list and 'p_win' in live_top_moves_optimal_list[0]:
                    live_pwin_optimal_from_engine = live_top_moves_optimal_list[0]['p_win']

                if live_pwin_optimal_from_engine is not None and \
                   isinstance(pwin_val_for_player_after_user_attempt, float) and \
                   pwin_val_for_player_after_user_attempt >= (live_pwin_optimal_from_engine - SOLVED_IMPROVEMENT_THRESHOLD):
                    is_solved_overall = True
                    logging.info(f"Solved based on live 9M data. User Pwin: {pwin_val_for_player_after_user_attempt}, Live Optimal 9M Pwin: {live_pwin_optimal_from_engine}")
                
                logging.debug(f"User move {user_move_uci} evaluated live by 9M. P(Win): {pwin_val_for_player_after_user_attempt}")
            else:
                logging.warning("Live 9M engine not available for fallback evaluation.")


        pwin_for_white = pwin_val_for_player_after_user_attempt if player_who_blundered == chess.WHITE else \
                         (1.0 - pwin_val_for_player_after_user_attempt if pwin_val_for_player_after_user_attempt is not None else 0.5)
        cp_value_white_perspective = pwin_to_cp(pwin_for_white)
        display_score_val_final = cp_value_white_perspective if self.display_scores_as_cp else pwin_val_for_player_after_user_attempt
        display_score_str = format_score_for_display(display_score_val_final, is_cp=self.display_scores_as_cp)
        
        score_unit_label_base = "Eval (pawns, White's persp.)" if self.display_scores_as_cp else \
                                f"P(Win for {chess.COLOR_NAMES[player_who_blundered]})"
        engine_src_label_part = evaluation_source.split(" ")[-1] if evaluation_source != "Unknown" else "9M" # Get "9M" or "136M"
        final_score_label = f"{score_unit_label_base} [{engine_src_label_part}]"

        feedback_message = f"After {user_move_san}: {final_score_label} = {display_score_str}"
        
        if is_solved_overall:
            feedback_message += f" - Excellent! (Solved by {evaluation_source} criteria)."
        elif isinstance(pwin_val_for_player_after_user_attempt, float) and \
             pwin_val_for_player_after_user_attempt > (self.current_blunder_data_active.get('p_win_after_move_9M', -1.0) + 0.01):
            feedback_message += " - Better than the original blunder."
        else:
            feedback_message += " - Still not the best path."
            
        self.feedback_panel.update_feedback(feedback_message)

        self.data_manager.record_attempt_for_current_blunder(
            attempted_uci=user_move_uci,
            pwin_after_attempt=pwin_val_for_player_after_user_attempt,
            is_solved_this_attempt=is_solved_overall
        )

        if self.current_blunder_data_active:
            if JSON_ATTEMPT_KEY not in self.current_blunder_data_active:
                self.current_blunder_data_active[JSON_ATTEMPT_KEY] = {}
            self.current_blunder_data_active[JSON_ATTEMPT_KEY][JSON_ATTEMPT_UCI_KEY] = user_move_uci
            self.current_blunder_data_active[JSON_ATTEMPT_KEY][JSON_ATTEMPT_PWIN_AFTER_9M_KEY] = pwin_val_for_player_after_user_attempt
            self.current_blunder_data_active[JSON_ATTEMPT_KEY][JSON_SOLVED_9M_KEY] = is_solved_overall

        self.board_widget.clear_visual_cues()
        self.board_widget.redraw_pieces_only()
        self.board_widget.draw_arrow(self.current_blunder_data_active['blunder_move_uci'], ACTUAL_BLUNDER_MOVE_COLOR, BLUNDER_ARROW_WIDTH)
        self.board_widget.draw_arrow(user_move_uci, USER_TRIAL_MOVE_COLOR, USER_ATTEMPT_ARROW_WIDTH)
        self._display_engine_hints_for_original_position()

    def _display_engine_hints_for_original_position(self):
        if not self.current_blunder_data_active:
            self.feedback_panel.update_hints("No blunder data loaded to show hints.")
            return

        hints_text_for_panel = "Engine Suggestions (for original blunder position):\n"
        player_at_blunder_pos = chess.Board(self.current_blunder_data_active['fen_before_blunder']).turn
        score_unit_label = "Eval (pawns, White's persp.)" if self.display_scores_as_cp else f"P(Win for {chess.COLOR_NAMES[player_at_blunder_pos]})"

        original_top_moves_9m = self.current_blunder_data_active.get('top_moves_9M_before_blunder', [])
        if original_top_moves_9m:
            hints_text_for_panel += "--- 9M Engine (from scan data) ---\n"
            for i, move_info in enumerate(original_top_moves_9m[:min(3, len(original_top_moves_9m))]):
                if isinstance(move_info, dict) and 'uci' in move_info and 'p_win' in move_info:
                    p_win_for_mover = move_info['p_win']
                    pwin_for_white_display = p_win_for_mover if player_at_blunder_pos == chess.WHITE else (1.0 - p_win_for_mover if p_win_for_mover is not None else 0.5)
                    cp_for_white_display = pwin_to_cp(pwin_for_white_display)
                    display_score_val = cp_for_white_display if self.display_scores_as_cp else p_win_for_mover
                    display_score_str = format_score_for_display(display_score_val, is_cp=self.display_scores_as_cp)
                    self.board_widget.draw_arrow(move_info['uci'], ENGINE_9M_HINT_COLORS[i % len(ENGINE_9M_HINT_COLORS)], ENGINE_ARROW_WIDTHS[i % len(ENGINE_ARROW_WIDTHS)])
                    self._draw_hint_score_on_square(move_info['uci'], display_score_str, ENGINE_9M_HINT_COLORS[i % len(ENGINE_9M_HINT_COLORS)])
                    hints_text_for_panel += f"  9M: {move_info.get('san','N/A')} ({score_unit_label}: {display_score_str})\n"
        else:
             hints_text_for_panel += "  (No 9M top moves found in blunder data for this position)\n"

        original_top_moves_136m = self.current_blunder_data_active.get('top_moves_136M_before_blunder', [])
        if original_top_moves_136m:
            hints_text_for_panel += "--- 136M Engine (from scan data) ---\n"
            for i, move_info in enumerate(original_top_moves_136m[:min(3, len(original_top_moves_136m))]):
                if isinstance(move_info, dict) and 'uci' in move_info and 'p_win' in move_info:
                    p_win_for_mover = move_info['p_win']
                    pwin_for_white_display = p_win_for_mover if player_at_blunder_pos == chess.WHITE else (1.0 - p_win_for_mover if p_win_for_mover is not None else 0.5)
                    cp_for_white_display = pwin_to_cp(pwin_for_white_display)
                    display_score_val = cp_for_white_display if self.display_scores_as_cp else p_win_for_mover
                    display_score_str = format_score_for_display(display_score_val, is_cp=self.display_scores_as_cp)
                    is_combined = False
                    if original_top_moves_9m:
                        for top_9m_move in original_top_moves_9m[:min(3, len(original_top_moves_9m))]:
                            if isinstance(top_9m_move, dict) and top_9m_move.get('uci') == move_info['uci']:
                                is_combined = True; break
                    arrow_color = ENGINE_136M_HINT_COLORS[i % len(ENGINE_136M_HINT_COLORS)]; text_color = arrow_color
                    if is_combined: arrow_color = HINT_COMBINED_COLOR; text_color = HINT_COMBINED_COLOR
                    self.board_widget.draw_arrow(move_info['uci'], arrow_color, ENGINE_136M_ARROW_WIDTHS[i % len(ENGINE_136M_ARROW_WIDTHS)])
                    self._draw_hint_score_on_square(move_info['uci'], display_score_str, text_color)
                    hints_text_for_panel += f"  136M: {move_info.get('san', 'N/A')} ({score_unit_label}: {display_score_str})\n"
        else:
            hints_text_for_panel += "  (No 136M top moves found in blunder data for this position)\n"
        if not original_top_moves_9m and not original_top_moves_136m:
             hints_text_for_panel = "No engine suggestions available in loaded blunder data."
        self.feedback_panel.update_hints(hints_text_for_panel)

    def _draw_hint_score_on_square(self, move_uci: str, score_text_to_display: str, text_color: str):
        if not self.board_widget or not hasattr(self.board_widget, 'canvas'): return
        try:
            move = chess.Move.from_uci(move_uci)
            to_sq = move.to_square
            x0, y0, x1, y1 = chess_draw_utils.sq_to_canvas_coords_oriented(
                to_sq, self.board_widget.white_at_bottom, self.board_widget.square_size_px
            )
            center_x = (x0 + x1) / 2; center_y = (y0 + y1) / 2
            font_size = max(12, self.board_widget.square_size_px // 4)
            self.board_widget.canvas.create_text(
                center_x, center_y, text=score_text_to_display, fill=text_color,
                font=(HINT_SCORE_FONT_FAMILY, font_size, "bold"),
                tags="hint_score_text"
            )
        except Exception as e:
            logging.error(f"Controller: Error drawing hint score text for {move_uci}: {e}")

    def action_select_next_blunder(self) -> bool:
        if self.current_interaction_mode.startswith("playing_from_blunder"):
            self._return_to_training_feedback_state(load_new_blunder=True)
        self.data_manager.next_blunder()
        return self.load_and_display_current_blunder()

    def action_select_prev_blunder(self) -> bool:
        if self.current_interaction_mode.startswith("playing_from_blunder"):
            self._return_to_training_feedback_state(load_new_blunder=True)
        self.data_manager.prev_blunder()
        return self.load_and_display_current_blunder()

    def action_flip_board_view(self):
        self.board_widget.flip_board_orientation()
        self._redraw_all_visual_cues_for_current_state()

    def handle_board_resize(self):
        logging.info("Controller: Board widget resized, redrawing cues.")
        self._redraw_all_visual_cues_for_current_state()

    def _redraw_all_visual_cues_for_current_state(self):
        self.board_widget.clear_visual_cues()
        if self.current_interaction_mode == "showing_feedback" and self.current_blunder_data_active:
            self.board_widget.draw_arrow(self.current_blunder_data_active['blunder_move_uci'], ACTUAL_BLUNDER_MOVE_COLOR, BLUNDER_ARROW_WIDTH)
            attempt_info = self.current_blunder_data_active.get(JSON_ATTEMPT_KEY, {})
            user_attempt_uci = attempt_info.get(JSON_ATTEMPT_UCI_KEY)
            if user_attempt_uci:
                self.board_widget.draw_arrow(user_attempt_uci, USER_TRIAL_MOVE_COLOR, USER_ATTEMPT_ARROW_WIDTH)
            self._display_engine_hints_for_original_position()
        elif self.current_interaction_mode == "user_input" and self.current_blunder_data_active:
            self.board_widget.draw_arrow(self.current_blunder_data_active['blunder_move_uci'], ACTUAL_BLUNDER_MOVE_COLOR, BLUNDER_ARROW_WIDTH)
        elif self.current_interaction_mode.startswith("playing_from_blunder") and self.board_for_play_mode:
            if self.board_for_play_mode.move_stack:
                last_move = self.board_for_play_mode.move_stack[-1]
                color = PLAYER_MOVE_COLOR if self.board_for_play_mode.turn != self.player_color_in_play_mode else ENGINE_MOVE_COLOR
                self.board_widget.draw_arrow(last_move.uci(), color, ARROW_WIDTH_BASE)
            if self.current_interaction_mode == "playing_from_blunder_player_turn" and \
               self.show_hints_in_play_mode_var_tk and self.show_hints_in_play_mode_var_tk.get():
                self._display_hints_for_play_mode()

    def action_retry_current_blunder(self):
        if not self.current_blunder_data_active: return
        if self.current_interaction_mode.startswith("playing_from_blunder"):
             self._return_to_training_feedback_state(load_new_blunder=False)
        if JSON_ATTEMPT_KEY in self.current_blunder_data_active:
            del self.current_blunder_data_active[JSON_ATTEMPT_KEY]
        self.board_widget.clear_visual_cues()
        self.board_widget.set_position(self.current_blunder_data_active['fen_before_blunder'])
        self.board_widget.redraw_pieces_only()
        self.board_widget.draw_arrow(self.current_blunder_data_active['blunder_move_uci'], ACTUAL_BLUNDER_MOVE_COLOR, BLUNDER_ARROW_WIDTH)
        self.feedback_panel.update_blunder_info(self.current_blunder_data_active, use_cp_display=self.display_scores_as_cp)
        self.feedback_panel.update_feedback("Retry: Your turn! Find a better move.")
        self.feedback_panel.clear_hints()
        self._transition_to_mode("user_input")

    def action_play_from_blunder_position(self):
        if not self.current_blunder_data_active or not self.engine_manager.engine_9M:
            self.feedback_panel.update_feedback("Cannot start play: Blunder or engine not ready.")
            return
        fen_to_play_from = self.current_blunder_data_active['fen_before_blunder']
        self.board_for_play_mode = chess.Board(fen_to_play_from)
        self.player_color_in_play_mode = self.board_for_play_mode.turn
        self.board_widget.set_position(self.board_for_play_mode.fen())
        self.board_widget.clear_visual_cues()
        new_white_at_bottom = (self.player_color_in_play_mode == chess.WHITE)
        if self.board_widget.white_at_bottom != new_white_at_bottom:
            self.board_widget.flip_board_orientation()
        self.feedback_panel.update_blunder_info(None, use_cp_display=self.display_scores_as_cp)
        self.feedback_panel.update_feedback(f"Playing vs Engine. Your turn as {chess.COLOR_NAMES[self.player_color_in_play_mode]}.")
        self.feedback_panel.clear_hints()
        self._transition_to_mode("playing_from_blunder_player_turn")
        if self.show_hints_in_play_mode_var_tk and self.show_hints_in_play_mode_var_tk.get():
            self._display_hints_for_play_mode()

    def _handle_user_move_in_play_mode(self, attempted_move_uci: str):
        if not self.board_for_play_mode or self.board_for_play_mode.turn != self.player_color_in_play_mode: return
        try: move_obj = self.board_for_play_mode.parse_uci(attempted_move_uci)
        except ValueError: self.feedback_panel.update_feedback("Invalid move format."); return
        if move_obj in self.board_for_play_mode.legal_moves:
            self.board_for_play_mode.push(move_obj)
            self.board_widget.set_position(self.board_for_play_mode.fen())
            self.board_widget.clear_visual_cues()
            self.board_widget.draw_arrow(move_obj.uci(), PLAYER_MOVE_COLOR, ARROW_WIDTH_BASE)
            self.feedback_panel.clear_hints()
            if self.board_for_play_mode.is_game_over(): self._handle_game_over_in_play_mode()
            else:
                self.feedback_panel.update_feedback("Engine (9M) thinking...")
                self._transition_to_mode("playing_from_blunder_engine_turn")
                if hasattr(self.board_widget, 'parent') and self.board_widget.parent:
                    self.board_widget.parent.after(100, self._request_engine_move_for_play_mode)
                else: self._request_engine_move_for_play_mode()
        else: self.feedback_panel.update_feedback(f"Illegal move: {attempted_move_uci}. Try again.")

    def _request_engine_move_for_play_mode(self):
        if not self.board_for_play_mode or self.board_for_play_mode.turn == self.player_color_in_play_mode or \
           not self.engine_manager.engine_9M:
            if self.board_for_play_mode: self._transition_to_mode("playing_from_blunder_player_turn")
            return
        top_moves = self.engine_manager.get_top_engine_moves_list(self.engine_manager.engine_9M, self.board_for_play_mode.copy(), num_moves=1)
        if top_moves:
            engine_move_obj = self.board_for_play_mode.parse_uci(top_moves[0]['uci'])
            self.board_for_play_mode.push(engine_move_obj)
            self.board_widget.set_position(self.board_for_play_mode.fen())
            self.board_widget.clear_visual_cues()
            self.board_widget.draw_arrow(engine_move_obj.uci(), ENGINE_MOVE_COLOR, ARROW_WIDTH_BASE)
            self.feedback_panel.clear_hints()
            if self.board_for_play_mode.is_game_over(): self._handle_game_over_in_play_mode()
            else:
                self.feedback_panel.update_feedback(f"Engine played {top_moves[0]['san']}. Your turn.")
                self._transition_to_mode("playing_from_blunder_player_turn")
                if self.show_hints_in_play_mode_var_tk and self.show_hints_in_play_mode_var_tk.get():
                    self._display_hints_for_play_mode()
        else:
            self.feedback_panel.update_feedback("Engine error. Your turn again?")
            if self.board_for_play_mode and self.board_for_play_mode.is_game_over(): self._handle_game_over_in_play_mode()
            else: self._transition_to_mode("playing_from_blunder_player_turn")

    def _handle_game_over_in_play_mode(self):
        result_str = "Game Over: "
        if self.board_for_play_mode.is_checkmate(): winner = "White" if self.board_for_play_mode.turn == chess.BLACK else "Black"; result_str += f"Checkmate! {winner} wins."
        elif self.board_for_play_mode.is_stalemate(): result_str += "Stalemate."
        elif self.board_for_play_mode.is_insufficient_material(): result_str += "Draw by insufficient material."
        elif self.board_for_play_mode.is_seventyfive_moves(): result_str += "Draw by 75-move rule."
        elif self.board_for_play_mode.is_fivefold_repetition(): result_str += "Draw by fivefold repetition."
        else: result_str += "Draw."
        self.feedback_panel.update_feedback(result_str)
        self._transition_to_mode("playing_from_blunder_game_over")

    def action_return_to_training(self): self._return_to_training_feedback_state()

    def _return_to_training_feedback_state(self, load_new_blunder=False):
        self.board_for_play_mode = None
        if load_new_blunder: return
        if not self.current_blunder_data_active:
            self._transition_to_mode("waiting_for_blunder"); self.board_widget.set_position(chess.STARTING_FEN)
            self.board_widget.clear_visual_cues(); self.feedback_panel.update_blunder_info(None, use_cp_display=self.display_scores_as_cp)
            self.feedback_panel.update_feedback("No blunder loaded."); self.feedback_panel.clear_hints()
            return
        fen_before_blunder = self.current_blunder_data_active['fen_before_blunder']
        self.board_widget.set_position(fen_before_blunder)
        temp_board_orient = chess.Board(fen_before_blunder)
        if self.board_widget.white_at_bottom != (temp_board_orient.turn == chess.WHITE):
            self.board_widget.flip_board_orientation()
        self._restore_feedback_for_current_blunder()

    def _restore_feedback_for_current_blunder(self):
        if not self.current_blunder_data_active: return
        self.board_widget.clear_visual_cues()
        
        player_who_blundered = chess.Board(self.current_blunder_data_active['fen_before_blunder']).turn
        score_unit_label = "Eval (pawns, White's persp.)" if self.display_scores_as_cp else f"P(Win for {chess.COLOR_NAMES[player_who_blundered]})"


        if JSON_ATTEMPT_KEY in self.current_blunder_data_active:
            self._transition_to_mode("showing_feedback")
            
            attempt_data = self.current_blunder_data_active[JSON_ATTEMPT_KEY]
            user_attempt_uci = attempt_data.get(JSON_ATTEMPT_UCI_KEY)
            pwin_val_for_player = attempt_data.get(JSON_ATTEMPT_PWIN_AFTER_9M_KEY, 0.5)
            is_solved_overall = attempt_data.get(JSON_SOLVED_9M_KEY, False)
            
            user_move_san = "N/A"
            try:
                if user_attempt_uci: user_move_san = chess.Board(self.current_blunder_data_active['fen_before_blunder']).san(chess.Move.from_uci(user_attempt_uci))
            except Exception: pass
            
            pwin_for_white_display = pwin_val_for_player if player_who_blundered == chess.WHITE else (1.0 - pwin_val_for_player if pwin_val_for_player is not None else 0.5)
            cp_for_white_display = pwin_to_cp(pwin_for_white_display)
            
            display_score_val = cp_for_white_display if self.display_scores_as_cp else pwin_val_for_player
            display_score_str = format_score_for_display(display_score_val, is_cp=self.display_scores_as_cp)
            
            # Determine evaluation source label for feedback
            # This part needs to be robust if JSON_ATTEMPT_KEY doesn't store the eval source.
            # For simplicity, if it was a stored attempt, we assume it might have been from any source.
            # The 'is_solved_overall' reflects the complex criteria.
            # We might need to store evaluation_source in JSON_ATTEMPT_KEY if we want to display it accurately here.
            # For now, let's use a generic label or infer from 'is_solved_overall'.
            
            feedback_message = f"Last attempt: {user_move_san}, Your {score_unit_label} [User Attempt] = {display_score_str}"
            
            if is_solved_overall:
                feedback_message += " - Excellent! (Solved by engine criteria)."
            elif isinstance(pwin_val_for_player, float) and \
                 pwin_val_for_player > (self.current_blunder_data_active.get('p_win_after_move_9M', -1.0) + 0.01):
                feedback_message += " - Better than the original blunder."
            else:
                feedback_message += " - Still not the best path."
            self.feedback_panel.update_feedback(feedback_message)
            self._redraw_all_visual_cues_for_current_state()
        else:
            self._transition_to_mode("user_input")
            self._redraw_all_visual_cues_for_current_state()
            self.feedback_panel.update_feedback("Your turn! Find a better move.")
            self.feedback_panel.clear_hints()
        self.feedback_panel.update_blunder_info(self.current_blunder_data_active, use_cp_display=self.display_scores_as_cp)

    def toggle_hints_in_play_mode(self):
        if self.current_interaction_mode == "playing_from_blunder_player_turn":
            if self.show_hints_in_play_mode_var_tk and self.show_hints_in_play_mode_var_tk.get():
                self._display_hints_for_play_mode()
            else:
                self.board_widget.clear_visual_cues()
                if self.board_for_play_mode and self.board_for_play_mode.move_stack:
                    last_move = self.board_for_play_mode.move_stack[-1]
                    color = PLAYER_MOVE_COLOR if self.board_for_play_mode.turn != self.player_color_in_play_mode else ENGINE_MOVE_COLOR
                    self.board_widget.draw_arrow(last_move.uci(), color, ARROW_WIDTH_BASE)
                self.feedback_panel.clear_hints()

    def _display_hints_for_play_mode(self):
        if not self.board_for_play_mode or not self.engine_manager.engine_9M: return
        self.board_widget.clear_visual_cues()
        if self.board_for_play_mode.move_stack:
            last_move_obj = self.board_for_play_mode.move_stack[-1]
            last_move_color = ENGINE_MOVE_COLOR if self.board_for_play_mode.turn == self.player_color_in_play_mode else PLAYER_MOVE_COLOR
            self.board_widget.draw_arrow(last_move_obj.uci(), last_move_color, ARROW_WIDTH_BASE)

        hints_text_for_panel = "Hints for current play position (9M Engine):\n"
        current_player_in_play_mode = self.board_for_play_mode.turn
        score_unit_label = "Eval (pawns, White's persp.)" if self.display_scores_as_cp else f"P(Win for {chess.COLOR_NAMES[current_player_in_play_mode]})"

        top_moves = self.engine_manager.get_top_engine_moves_list(self.engine_manager.engine_9M, self.board_for_play_mode.copy(), num_moves=3)
        if top_moves:
            for i, move_info in enumerate(top_moves):
                p_win_for_mover = move_info['p_win']
                pwin_for_white_display = p_win_for_mover if current_player_in_play_mode == chess.WHITE else (1.0 - p_win_for_mover if p_win_for_mover is not None else 0.5)
                cp_for_white_display = pwin_to_cp(pwin_for_white_display)
                display_score_val = cp_for_white_display if self.display_scores_as_cp else p_win_for_mover
                display_score_str = format_score_for_display(display_score_val, is_cp=self.display_scores_as_cp)
                self.board_widget.draw_arrow(move_info['uci'], ENGINE_9M_HINT_COLORS[i % len(ENGINE_9M_HINT_COLORS)], ENGINE_ARROW_WIDTHS[i % len(ENGINE_ARROW_WIDTHS)])
                self._draw_hint_score_on_square(move_info['uci'], display_score_str, ENGINE_9M_HINT_COLORS[i % len(ENGINE_9M_HINT_COLORS)])
                hints_text_for_panel += f"  9M: {move_info.get('san','N/A')} ({score_unit_label}: {display_score_str})\n"
        else: hints_text_for_panel += "  (No moves found or game over)\n"
        self.feedback_panel.update_hints(hints_text_for_panel)
# ===== END OF FILE blunder_trainer_controller.py =====
