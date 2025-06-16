# ===== START OF FILE game_controller.py =====
import chess
import logging
from game_manager import GameManager
from engines import SearchlessEngineManager 

from constants import (
    ENGINE_MOVE_COLOR, PLAYER_MOVE_COLOR, ARROW_WIDTH_BASE,
    HINT_PALETTE_1, HINT_SCORE_TEXT_COLOR,
    HINT_SCORE_FONT_FAMILY, HINT_SCORE_FONT_WEIGHT 
)
from utils import pwin_to_cp, format_score_for_display
import chess_draw_utils as cdu

class GameController:
    def __init__(self, board_widget, feedback_panel, engine_manager,
                 gui_update_buttons_callback=None):
        self.board_widget = board_widget
        self.feedback_panel = feedback_panel
        self.engine_manager = engine_manager
        self.gui_update_buttons_callback = gui_update_buttons_callback
        self.root = None 

        self.game_manager = GameManager()
        # GameController no longer directly holds a board or FEN; it gets the board object from GameManager.
        self.current_interaction_mode = "IDLE"
        self.show_hints_active = False 
        self.display_scores_as_cp = True 

        self.board_widget.on_move_attempted_callback = self._handle_user_move_attempt
        logging.info("GameController initialized.")

    def _transition_to_mode(self, new_mode: str):
        logging.debug(f"GC: Transitioning from {self.current_interaction_mode} to {new_mode}")
        old_mode = self.current_interaction_mode
        self.current_interaction_mode = new_mode

        if new_mode == "PLAYER_TURN":
            self.board_widget.set_interaction_enabled(True)
        else: 
            self.board_widget.set_interaction_enabled(False)

        if self.gui_update_buttons_callback and old_mode != new_mode:
            self.gui_update_buttons_callback()
        
    def action_start_new_game(self, player_color: chess.Color = chess.WHITE):
        logging.info(f"GC: Action Start New Game received. Player as {chess.COLOR_NAMES[player_color]}.")
        self.game_manager.start_new_game(player_color=player_color, engine_instance=self.engine_manager.engine_9M)
        
        current_board_obj = self.game_manager.get_board_object()
        self.board_widget.set_board(current_board_obj) # Pass the board object
        
        if self.board_widget.white_at_bottom != self.game_manager.get_board_orientation_white_pov():
            self.board_widget.flip_board_orientation(redraw_now=True) 
        
        if self.game_manager.is_player_turn(): # Use GameManager's check which uses its board
            self._transition_to_mode("PLAYER_TURN")
            self._redraw_all_visual_cues_for_current_state() 
        else: 
            self._transition_to_mode("ENGINE_TURN")
            self._redraw_all_visual_cues_for_current_state() 
            if self.root: self.root.after(50, self._trigger_engine_move)
            else: self._trigger_engine_move() 
        
        print(f"✅ GC: New game started. Player: {chess.COLOR_NAMES[player_color]}. Mode: {self.current_interaction_mode}")

    def action_play_as_black(self):
        self.action_start_new_game(player_color=chess.BLACK)

    def action_reset_game(self):
        self.action_start_new_game(player_color=chess.WHITE) 

    def _handle_user_move_attempt(self, attempted_move_uci: str):
        print(f"GC DEBUG: _handle_user_move_attempt received UCI: {attempted_move_uci}")
        if self.current_interaction_mode != "PLAYER_TURN":
            print(f"GC DEBUG: Not player's turn (mode: {self.current_interaction_mode}). Ignoring move.")
            return
        if not self.game_manager.is_active():
            print(f"GC DEBUG: Game not active. Ignoring move.")
            return

        current_board_for_log = self.game_manager.get_board_object()
        print(f"GC DEBUG: Current board FEN before making player move: {current_board_for_log.fen()}")
        
        move_successful = self.game_manager.make_player_move(attempted_move_uci)
        print(f"GC DEBUG: game_manager.make_player_move returned: {move_successful}")

        if move_successful:
            # GameManager's board is already updated.
            # Tell BoardWidget to use this updated board object for redraw.
            self.board_widget.set_board(self.game_manager.get_board_object())
            if self.game_manager.is_game_over():
                self._transition_to_mode("GAME_OVER")
                self._redraw_all_visual_cues_for_current_state() 
            else:
                self._transition_to_mode("ENGINE_TURN")
                self._redraw_all_visual_cues_for_current_state() 
                if self.root: self.root.after(50, self._trigger_engine_move)
                else: self._trigger_engine_move()
        else:
            self.feedback_panel.update_feedback(f"Illegal move: {attempted_move_uci}. Try again.")
            print(f"GC DEBUG: Illegal move {attempted_move_uci} reported by GameManager.")
            # BoardWidget still has the old board reference, redraw to show the state before illegal attempt
            self.board_widget.redraw_board_and_pieces() 


    def _trigger_engine_move(self, for_specific_color: chess.Color | None = None):
        is_opponent_move = for_specific_color is None 
        if is_opponent_move and self.current_interaction_mode != "ENGINE_TURN": return
        if not self.game_manager.is_active(): return

        current_board_obj_for_engine = self.game_manager.get_board_object()
        current_turn_color_on_board = current_board_obj_for_engine.turn
        logging.info(f"GC: Triggering engine move for {chess.COLOR_NAMES[current_turn_color_on_board]}...")
        if self.root: self.root.update_idletasks()

        engine_move_uci = self.game_manager.get_engine_move_uci(self.engine_manager) # GameManager uses its own board

        if engine_move_uci:
            self.game_manager.make_move_on_board(engine_move_uci) 
            self.board_widget.set_board(self.game_manager.get_board_object()) # Update widget with new board state
            if self.game_manager.is_game_over():
                self._transition_to_mode("GAME_OVER")
            else:
                if self.game_manager.is_player_turn(): # Check uses GameManager's board
                    self._transition_to_mode("PLAYER_TURN")
                else: 
                    if is_opponent_move: 
                        self._transition_to_mode("PLAYER_TURN") 
                    else: 
                        self._transition_to_mode("ENGINE_TURN")
                        if self.root: self.root.after(50, lambda: self._trigger_engine_move())
                        else: self._trigger_engine_move()
            self._redraw_all_visual_cues_for_current_state()
        else:
            self.feedback_panel.update_feedback(f"Engine error for {chess.COLOR_NAMES[current_turn_color_on_board]}. Player's turn?")
            if self.game_manager.is_active(): self._transition_to_mode("PLAYER_TURN") 
            self._redraw_all_visual_cues_for_current_state()

    def action_flip_board_view(self):
        if not self.game_manager.is_active() and self.current_interaction_mode == "IDLE":
            self.board_widget.flip_board_orientation(redraw_now=True)
            self._update_feedback_for_game_state() 
            return
        
        current_player_color = self.game_manager.get_player_color()
        new_player_color = not current_player_color
        self.game_manager.set_player_color(new_player_color)

        # Board object itself doesn't change on flip, just player perspective and widget orientation
        if self.board_widget.white_at_bottom != self.game_manager.get_board_orientation_white_pov():
            self.board_widget.flip_board_orientation(redraw_now=True) # This will use widget's current board
        
        if self.game_manager.is_player_turn():
            self._transition_to_mode("PLAYER_TURN")
        else: 
            self._transition_to_mode("ENGINE_TURN")
            self._trigger_engine_move() 
        self._redraw_all_visual_cues_for_current_state()

    def action_make_engine_move_for_player(self):
        if not self.game_manager.is_active() or self.current_interaction_mode != "PLAYER_TURN": return
        if self.root: self.root.update_idletasks()
        
        engine_move_uci = self.game_manager.get_engine_move_uci(self.engine_manager)
        if engine_move_uci:
            self.game_manager.make_move_on_board(engine_move_uci) 
            self.board_widget.set_board(self.game_manager.get_board_object())
            if self.game_manager.is_game_over():
                self._transition_to_mode("GAME_OVER")
            else:
                self._transition_to_mode("ENGINE_TURN") 
                if self.root: self.root.after(50, lambda: self._trigger_engine_move()) 
                else: self._trigger_engine_move()
            self._redraw_all_visual_cues_for_current_state()
        else:
            self.feedback_panel.update_feedback("Engine couldn't find a move for you.") 
            self._redraw_all_visual_cues_for_current_state() 

    def action_take_back(self):
        if not self.game_manager.has_moves_to_take_back():
            self.feedback_panel.update_feedback("No moves to take back.")
            return
        self.game_manager.take_back_move()
        self.board_widget.set_board(self.game_manager.get_board_object())
        
        if not self.game_manager.is_active() or len(self.game_manager.get_board_object().move_stack) == 0 :
             self._transition_to_mode("IDLE") 
        elif self.game_manager.is_player_turn():
            self._transition_to_mode("PLAYER_TURN")
        else: 
            # This case might need refinement depending on desired behavior after take_back
            # For now, assume it should become player's turn if game active.
            # GameManager.take_back_move tries to make it player's turn.
             current_board_obj = self.game_manager.get_board_object()
             if current_board_obj.turn != self.game_manager.get_player_color():
                 current_board_obj.turn = self.game_manager.get_player_color() # Force turn if needed. Risky.
                 self.board_widget.set_board(current_board_obj) # Ensure widget knows of forced turn change
             self._transition_to_mode("PLAYER_TURN")
        self._redraw_all_visual_cues_for_current_state()


    def toggle_game_hints(self, show_hints: bool):
        self.show_hints_active = show_hints 
        logging.info(f"GC: Hints toggled via checkbox to {self.show_hints_active}")
        self._redraw_all_visual_cues_for_current_state()

    def _draw_hint_score_on_widget(self, move_uci: str, score_text: str, text_color: str):
        try:
            move = chess.Move.from_uci(move_uci)
            to_sq = move.to_square
            x0, y0, x1, y1 = cdu.sq_to_canvas_coords_oriented(
                to_sq, self.board_widget.white_at_bottom, self.board_widget.square_size_px
            )
            center_x = (x0 + x1) / 2
            center_y = (y0 + y1) / 2
            font_size = max(8, self.board_widget.square_size_px // (5 if len(score_text) < 4 else 6) )
            font_details = (HINT_SCORE_FONT_FAMILY, font_size, "bold") 
            self.board_widget.canvas.create_text(
                center_x, center_y, text=score_text, fill=text_color,
                font=font_details, tags="hint_score_text" 
            )
        except Exception as e:
            logging.error(f"GC: Error drawing hint score text for {move_uci} ('{score_text}'): {e}", exc_info=True)

    def _display_current_hints(self):
        logging.debug("GC: _display_current_hints executing.")
        
        board_for_hints = self.game_manager.get_board_object().copy() # Use a copy for engine analysis
        top_moves = self.engine_manager.get_top_engine_moves_list(
            self.engine_manager.engine_9M, board_for_hints, num_moves=3
        )

        hints_text_for_panel = "Engine Hints (9M):\n"
        if top_moves:
            player_to_move = board_for_hints.turn
            for i, move_info in enumerate(top_moves):
                if 'uci' in move_info and 'san' in move_info:
                    arrow_color = HINT_PALETTE_1[i % len(HINT_PALETTE_1)]
                    self.board_widget.draw_arrow(move_info['uci'], arrow_color, ARROW_WIDTH_BASE - i)
                    
                    p_win_for_mover = move_info.get('p_win')
                    if p_win_for_mover is not None:
                        current_player_pwin = p_win_for_mover 
                        pwin_for_white_display = current_player_pwin if player_to_move == chess.WHITE else (1.0 - current_player_pwin)
                        score_display_str = format_score_for_display(pwin_to_cp(pwin_for_white_display) if self.display_scores_as_cp else current_player_pwin, is_cp=self.display_scores_as_cp)
                        self._draw_hint_score_on_widget(move_info['uci'], score_display_str, HINT_SCORE_TEXT_COLOR)
                        hints_text_for_panel += f"  {i+1}. {move_info['san']} ({('CP' if self.display_scores_as_cp else 'PWin')}: {score_display_str})\n"
                    else:
                         hints_text_for_panel += f"  {i+1}. {move_info['san']} (PWin: N/A)\n"
        else:
            hints_text_for_panel += "  (No hints available or game over)\n"
        self.feedback_panel.update_hints(hints_text_for_panel)

    def _update_feedback_for_game_state(self):
        main_feedback_text = ""
        if not self.game_manager.is_active() and self.current_interaction_mode != "GAME_OVER":
            if self.current_interaction_mode == "IDLE":
                 main_feedback_text = "Choose to play as White or Black."
        elif self.current_interaction_mode == "GAME_OVER":
            result = self.game_manager.get_game_result()
            main_feedback_text = f"Game Over: {result if result else 'Finished.'}"
        elif self.current_interaction_mode == "PLAYER_TURN":
            player_name = "White" if self.game_manager.get_player_color() == chess.WHITE else "Black"
            main_feedback_text = f"Your turn as {player_name}."
        elif self.current_interaction_mode == "ENGINE_TURN":
            engine_color_name = chess.COLOR_NAMES[self.game_manager.get_board_object().turn]
            main_feedback_text = f"Engine (9M) thinking for {engine_color_name}..."
        elif self.current_interaction_mode == "IDLE": 
             main_feedback_text = "Choose to play as White or Black."
        
        if main_feedback_text: 
            self.feedback_panel.update_feedback(main_feedback_text)


    def _redraw_all_visual_cues_for_current_state(self):
        logging.debug(f"GC: Redrawing all cues. Mode: {self.current_interaction_mode}, Hints Active: {self.show_hints_active}")
        self.board_widget.clear_visual_cues()  
        # Ensure board_widget is using the latest board from game_manager before redrawing.
        # This is mostly for safety, as set_board should be called after any GM board change.
        self.board_widget.set_board(self.game_manager.get_board_object())
        self.board_widget.redraw_board_and_pieces() 

        current_board_obj = self.game_manager.get_board_object()
        if self.game_manager.is_active() and current_board_obj.move_stack: 
            last_move = current_board_obj.move_stack[-1]
            # Color is based on whose turn it *is now* (so previous move was by other color)
            color = PLAYER_MOVE_COLOR if current_board_obj.turn != self.game_manager.get_player_color() else ENGINE_MOVE_COLOR
            self.board_widget.draw_arrow(last_move.uci(), color, ARROW_WIDTH_BASE)

        if self.show_hints_active and self.game_manager.is_active() and not self.game_manager.is_game_over():
            self._display_current_hints() 
        else:
            self.board_widget.canvas.delete("hint_score_text") 
            self.feedback_panel.clear_hints() 
        
        self._update_feedback_for_game_state() 
        
        game_board = self.game_manager.get_board_object()
        logging.debug(f"GC: Visual cues redrawn complete. Moves: {len(game_board.move_stack) if game_board else 0}")


    def handle_board_resize(self):
        logging.info("GC: Board widget resized.")
        self._redraw_all_visual_cues_for_current_state()

# ===== END OF FILE game_controller.py =====
