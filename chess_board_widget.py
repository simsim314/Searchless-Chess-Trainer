# ===== START OF FILE chess_board_widget.py =====
import tkinter as tk
from tkinter import ttk
import chess
import chess_draw_utils as cdu 
from constants import (
    IMAGE_PATH, DEFAULT_BOARD_SIZE_PX, MIN_BOARD_SIZE_PX,
    SELECTED_SQUARE_HIGHLIGHT_COLOR, DRAG_TARGET_HIGHLIGHT_COLOR,
    HINT_SCORE_FONT_FAMILY
)
import logging

class ChessBoardWidget:
    def __init__(self, parent, board_size_px=DEFAULT_BOARD_SIZE_PX,
                 image_path=IMAGE_PATH, white_at_bottom=True,
                 on_resize_callback=None):
        self.parent = parent
        self.board_size_px = board_size_px
        self.square_size_px = board_size_px // 8
        self.white_at_bottom = white_at_bottom
        self.image_path = image_path
        self.on_resize_callback = on_resize_callback

        self.board: chess.Board = chess.Board(chess960=True) 
        self.interaction_enabled = True

        self.drag_info = {"piece_obj": None, "from_sq": None, "canvas_item_id": None, "is_dragging": False}
        self.first_click_square = None

        self.on_move_attempted_callback = None

        self.piece_images = {}
        self._create_canvas() 
        cdu.draw_board_squares(self.canvas, self.white_at_bottom, self.square_size_px)
        self._load_piece_images()
        self._setup_event_bindings()
        self.redraw_board_and_pieces()

    def _create_canvas(self):
        self.frame = ttk.Frame(self.parent)
        self.frame.pack(fill=tk.BOTH, expand=True) 

        self.canvas = tk.Canvas(self.frame,
                               width=self.board_size_px,
                               height=self.board_size_px,
                               bg="lightgrey", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True) 

    def _load_piece_images(self):
        if self.square_size_px <=0:
            self.piece_images = {}
            return
        self.piece_images = cdu.load_and_resize_piece_images(
            self.image_path, self.square_size_px)

    def _setup_event_bindings(self):
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def set_board(self, board_object: chess.Board):
        self.board = board_object
        self.redraw_board_and_pieces()

    def set_position(self, fen: str):
        self.board = chess.Board(fen, chess960=self.board.chess960) 
        self.redraw_board_and_pieces()

    def flip_board_orientation(self, redraw_now=True): 
        self.white_at_bottom = not self.white_at_bottom
        cdu.draw_board_squares(self.canvas, self.white_at_bottom, self.square_size_px)
        if redraw_now:
            self.redraw_board_and_pieces()

    def set_interaction_enabled(self, enabled: bool):
        self.interaction_enabled = enabled
        if not enabled:
            self._clear_internal_interaction_visuals()
            self._reset_drag_state()

    def redraw_board_and_pieces(self):
        self.canvas.delete("piece") 
        if self.drag_info.get("canvas_item_id"): 
            self.canvas.delete(self.drag_info["canvas_item_id"])
            self.drag_info["canvas_item_id"] = None 
        
        square_to_skip_drawing = self.drag_info["from_sq"] if self.drag_info["is_dragging"] else None
        
        cdu.draw_pieces(self.canvas, self.board.fen(), self.piece_images,
                       self.white_at_bottom, self.square_size_px,
                       square_to_skip_drawing=square_to_skip_drawing)

    def redraw_pieces_only(self): 
        self.redraw_board_and_pieces()

    def clear_visual_cues(self):
        self.canvas.delete("highlight")
        self.canvas.delete("drag_target_highlight")
        self.canvas.delete("arrow")
        self.canvas.delete("possible_move_dot")
        self.canvas.delete("hint_score_text") 
        if self.drag_info.get("canvas_item_id"): 
            self.canvas.delete(self.drag_info["canvas_item_id"])
        self.first_click_square = None 

    def _clear_internal_interaction_visuals(self):
        self.canvas.delete("highlight") 
        self.canvas.delete("drag_target_highlight") 
        if self.drag_info.get("canvas_item_id"):
            self.canvas.delete(self.drag_info["canvas_item_id"])
            self.drag_info["canvas_item_id"] = None

    def _reset_drag_state(self):
        if self.drag_info.get("canvas_item_id"): 
            self.canvas.delete(self.drag_info["canvas_item_id"])
        self.drag_info = {"piece_obj": None, "from_sq": None, "canvas_item_id": None, "is_dragging": False}

    def draw_arrow(self, move_uci: str, color: str, width: int):
        cdu.draw_arrow(self.canvas, move_uci, color, width,
                      self.white_at_bottom, self.square_size_px)

    def draw_text_on_square(self, square: chess.Square, text: str, color: str):
        x0, y0, x1, y1 = cdu.sq_to_canvas_coords_oriented(
            square, self.white_at_bottom, self.square_size_px
        )
        center_x = (x0 + x1) / 2
        center_y = (y0 + y1) / 2
        
        base_font_size = max(10, self.square_size_px // 5)
        font_size = int(base_font_size * 1.2)
        
        self.canvas.create_text(
            center_x, center_y, text=text, fill=color,
            font=(HINT_SCORE_FONT_FAMILY, font_size, "bold"),
            justify=tk.CENTER,  # This will center multi-line text
            tags="hint_score_text"
        )

    def highlight_square(self, square: chess.Square, color: str, tag:str ="highlight"):
        if tag == "highlight": 
            self.canvas.delete("highlight")
        cdu.draw_square_highlight(self.canvas, square, color,
                                 self.white_at_bottom, self.square_size_px, tag=tag)

    def _on_mouse_down(self, event):
        if not self.interaction_enabled: return
        self._clear_internal_interaction_visuals() 
        self._reset_drag_state() 
        self.first_click_square = None 

        clicked_sq = cdu.canvas_coords_to_sq_oriented(event.x, event.y, self.white_at_bottom, self.board_size_px, self.square_size_px)
        if clicked_sq is None: return
        piece = self.board.piece_at(clicked_sq)

        if piece and piece.color == self.board.turn: 
            self.drag_info["piece_obj"] = piece
            self.drag_info["from_sq"] = clicked_sq
            self.first_click_square = clicked_sq 
            self.highlight_square(clicked_sq, SELECTED_SQUARE_HIGHLIGHT_COLOR) 

    def _on_mouse_drag(self, event):
        if not self.interaction_enabled or not self.drag_info["piece_obj"] or self.drag_info["from_sq"] is None:
            return

        current_board_size = self.board_size_px 
        if not (0 <= event.x < current_board_size and 0 <= event.y < current_board_size):
            return

        if not self.drag_info["is_dragging"]: 
            self.drag_info["is_dragging"] = True
            self.first_click_square = None 
            
            self.redraw_board_and_pieces() 
            if self.drag_info["from_sq"]: 
                 self.highlight_square(self.drag_info["from_sq"], SELECTED_SQUARE_HIGHLIGHT_COLOR)

            photo_img = self.piece_images.get(
                (self.drag_info["piece_obj"].piece_type, self.drag_info["piece_obj"].color))
            if photo_img:
                self.drag_info["canvas_item_id"] = self.canvas.create_image(
                    event.x, event.y, image=photo_img, tags=("dragged_piece", "piece"), anchor="center"
                )
        
        if self.drag_info["canvas_item_id"]: 
            self.canvas.coords(self.drag_info["canvas_item_id"], event.x, event.y) 
            
            self.canvas.delete("drag_target_highlight") 
            target_sq = cdu.canvas_coords_to_sq_oriented(event.x, event.y, self.white_at_bottom, self.board_size_px, self.square_size_px)
            
            if (target_sq is not None and target_sq != self.drag_info["from_sq"] and
                self._is_potential_legal_move(self.drag_info["from_sq"], target_sq)):
                self.highlight_square(target_sq, DRAG_TARGET_HIGHLIGHT_COLOR, tag="drag_target_highlight")

    def _on_mouse_up(self, event):
        if not self.interaction_enabled:
            return

        to_sq = cdu.canvas_coords_to_sq_oriented(event.x, event.y, self.white_at_bottom, self.board_size_px, self.square_size_px)
        move_uci_to_attempt = None
        
        was_dragging = self.drag_info["is_dragging"]
        from_sq_for_attempt = None

        if was_dragging:
            from_sq_for_attempt = self.drag_info["from_sq"]
        elif self.first_click_square is not None: 
            from_sq_for_attempt = self.first_click_square
        
        if from_sq_for_attempt is not None and to_sq is not None and to_sq != from_sq_for_attempt:
            move_uci_to_attempt = self._create_move_uci(from_sq_for_attempt, to_sq)

        self._clear_internal_interaction_visuals()
        self._reset_drag_state() 
        
        if move_uci_to_attempt and self.on_move_attempted_callback:
            self.first_click_square = None 
            self.on_move_attempted_callback(move_uci_to_attempt)
        else:
            self.redraw_board_and_pieces() 
            self.first_click_square = None 

    def _create_move_uci(self, from_sq: chess.Square, to_sq: chess.Square) -> str | None:
        move = chess.Move(from_sq, to_sq)
        
        piece_type_moving = self.board.piece_type_at(from_sq)
        if piece_type_moving == chess.PAWN:
            target_rank = chess.square_rank(to_sq)
            if (self.board.turn == chess.WHITE and target_rank == 7) or \
               (self.board.turn == chess.BLACK and target_rank == 0):
                move.promotion = chess.QUEEN 
        
        if self.board.is_legal(move):
            return move.uci()
        
        return None

    def _is_potential_legal_move(self, from_sq: chess.Square, to_sq: chess.Square) -> bool:
        move = chess.Move(from_sq, to_sq)
        piece_type_moving = self.board.piece_type_at(from_sq)
        if piece_type_moving == chess.PAWN:
            target_rank = chess.square_rank(to_sq)
            if (self.board.turn == chess.WHITE and target_rank == 7) or \
               (self.board.turn == chess.BLACK and target_rank == 0):
                move.promotion = chess.QUEEN 
        return self.board.is_legal(move)

    def _on_canvas_configure(self, event):
        new_width = event.width
        new_height = event.height
        new_board_draw_size = max(MIN_BOARD_SIZE_PX, min(new_width, new_height))

        if abs(new_board_draw_size - self.board_size_px) > 1:
            self.board_size_px = new_board_draw_size
            self.square_size_px = self.board_size_px // 8

            self.canvas.config(width=self.board_size_px, height=self.board_size_px)

            self._load_piece_images()
            cdu.draw_board_squares(self.canvas, self.white_at_bottom, self.square_size_px)
            self.redraw_board_and_pieces() 

            if self.on_resize_callback:
                self.on_resize_callback() 

    def clear_arrows_by_color_filter(self, color_list: list):
        if not color_list:
            return
        arrow_items = self.canvas.find_withtag("arrow")
        for item_id in arrow_items:
            item_color = self.canvas.itemcget(item_id, "fill")
            if item_color and item_color.lower() in [c.lower() for c in color_list]:
                self.canvas.delete(item_id)

    def clear_text_by_tag(self, tag_to_clear: str):
        if tag_to_clear:
            self.canvas.delete(tag_to_clear)

# ===== END OF FILE chess_board_widget.py =====