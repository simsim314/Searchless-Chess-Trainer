# ===== START OF FILE chess_draw_utils.py =====
import tkinter as tk
import chess
import logging
from PIL import Image, ImageTk
import os
import math

from constants import (
    MIN_BOARD_SIZE_PX,
    HINT_SCORE_FONT_FAMILY, HINT_SCORE_FONT_WEIGHT, HINT_SCORE_TEXT_COLOR,
    PIECE_IMAGE_FILENAMES,
    LIGHT_SQUARE_COLOR, DARK_SQUARE_COLOR
)

# --- Coordinate Conversion Utilities ---
def sq_to_canvas_coords_oriented(sq: chess.Square, board_orientation_white_pov: bool, current_square_size_px: int):
    file = chess.square_file(sq); rank = chess.square_rank(sq)
    if not board_orientation_white_pov: file = 7 - file; rank = 7 - rank
    x0 = file * current_square_size_px; y0 = (7 - rank) * current_square_size_px
    return x0, y0, x0 + current_square_size_px, y0 + current_square_size_px

def canvas_coords_to_sq_oriented(canvas_x: int, canvas_y: int, board_orientation_white_pov: bool, current_board_size_px: int, current_square_size_px: int) -> chess.Square | None:
    if not (0 <= canvas_x < current_board_size_px and 0 <= canvas_y < current_board_size_px): return None
    file_gui = canvas_x // current_square_size_px; rank_gui = canvas_y // current_square_size_px
    if board_orientation_white_pov: chess_file, chess_rank = file_gui, 7 - rank_gui
    else: chess_file, chess_rank = 7 - file_gui, rank_gui
    if 0 <= chess_file <= 7 and 0 <= chess_rank <= 7: return chess.square(chess_file, chess_rank)
    return None

# --- Canvas Drawing Functions ---
def draw_board_squares(canvas: tk.Canvas, board_orientation_white_pov: bool, current_square_size_px: int):
    canvas.delete("square")
    for r_gui in range(8):
        for f_gui in range(8):
            chess_r_for_color, chess_f_for_color = (7-r_gui,f_gui) if board_orientation_white_pov else (r_gui,7-f_gui)
            color = LIGHT_SQUARE_COLOR if (chess_r_for_color + chess_f_for_color) % 2 == 1 else DARK_SQUARE_COLOR
            x0_c, y0_c = f_gui*current_square_size_px, r_gui*current_square_size_px
            canvas.create_rectangle(x0_c,y0_c,x0_c+current_square_size_px,y0_c+current_square_size_px,fill=color,outline=color,tags="square")

def draw_pieces(canvas: tk.Canvas, board_fen: str, resized_photo_images: dict,
                board_orientation_white_pov: bool, current_square_size_px: int,
                square_to_skip_drawing: chess.Square | None = None):
    canvas.delete("piece")
    current_board = chess.Board(board_fen)
    for sq in chess.SQUARES:
        if sq == square_to_skip_drawing: continue
        piece = current_board.piece_at(sq)
        if piece:
            photo_img = resized_photo_images.get((piece.piece_type, piece.color))
            if photo_img:
                x0_sq_c, y0_sq_c, _, _ = sq_to_canvas_coords_oriented(sq, board_orientation_white_pov, current_square_size_px)
                canvas.create_image(x0_sq_c + current_square_size_px / 2, y0_sq_c + current_square_size_px / 2, image=photo_img, tags="piece")

def draw_arrow(canvas: tk.Canvas, uci_move: str, color: str, width: int, board_orientation_white_pov: bool, current_square_size_px: int):
    if len(uci_move) < 4: logging.warning(f"cdu: Invalid UCI (too short) for arrow: {uci_move}"); return # Added length check
    try:
        move = chess.Move.from_uci(uci_move[:4]) # Use only first 4 chars for basic move
    except ValueError:
        logging.warning(f"cdu: Invalid UCI for arrow: {uci_move}")
        return

    x0f,y0f,_,_=sq_to_canvas_coords_oriented(move.from_square,board_orientation_white_pov,current_square_size_px)
    x0t,y0t,_,_=sq_to_canvas_coords_oriented(move.to_square,board_orientation_white_pov,current_square_size_px)
    x1c,y1c=x0f+current_square_size_px/2,y0f+current_square_size_px/2
    x2c,y2c=x0t+current_square_size_px/2,y0t+current_square_size_px/2
    arrow_shape=(max(8,width*2.5),max(10,width*3),max(4,width*1.25)) # Standard arrow shape

    # MODIFICATION: Add stipple='gray50' for all arrows
    canvas.create_line(x1c, y1c, x2c, y2c,
                       fill=color,
                       width=width,
                       arrow=tk.LAST,
                       tags="arrow",
                       arrowshape=arrow_shape,
                       stipple='gray50') # ADDED STIPPLE OPTION

def draw_square_highlight(canvas: tk.Canvas, sq: chess.Square, color: str, board_orientation_white_pov: bool, current_square_size_px: int, tag="highlight"):
    x0,y0,x1,y1=sq_to_canvas_coords_oriented(sq,board_orientation_white_pov,current_square_size_px)
    canvas.create_rectangle(x0,y0,x1,y1,outline=color,width=max(2,current_square_size_px//20),tags=tag)

def draw_possible_move_dot(canvas: tk.Canvas, sq: chess.Square, color: str, board_orientation_white_pov: bool, current_square_size_px: int):
    x0,y0,_,_=sq_to_canvas_coords_oriented(sq,board_orientation_white_pov,current_square_size_px)
    cx,cy=x0+current_square_size_px/2,y0+current_square_size_px/2
    radius=max(3,current_square_size_px//10)
    canvas.create_oval(cx-radius,cy-radius,cx+radius,cy+radius,fill=color,outline="",tags="possible_move_dot")

def draw_hint_score_text(canvas: tk.Canvas,
                         from_sq_coords_center: tuple[float, float],
                         to_sq_coords_center: tuple[float, float],
                         text_to_draw: str, text_color: str,
                         current_square_size_px: int,
                         label_offset_index: int = 0,
                         existing_labels_on_target_sq: int = 0):
    # This function is for drawing text, not lines, so stipple doesn't apply here.
    # Its appearance is controlled by its font and color.
    (x1, y1) = from_sq_coords_center
    (x2, y2) = to_sq_coords_center

    dx = x2 - x1; dy = y2 - y1
    arrow_length = math.sqrt(dx*dx + dy*dy)
    if arrow_length < 1.0: # Avoid division by zero for very short/zero length arrows
        udx, udy = 0, 0
    else:
        udx, udy = dx / arrow_length, dy / arrow_length

    pdx, pdy = -udy, udx # Normalized perpendicular vector

    font_size = max(8, current_square_size_px // 5) # Keep this as is or adjust as needed

    # Logic for placing text relative to arrow (from previous versions)
    # This logic aims to place text near the arrow tip or slightly beyond.
    # For example, placing text near the target square center if using that approach for scores.
    # The example from previous controller:
    #   center_x = (x0_target_sq_corner + x1_target_sq_corner) / 2
    #   center_y = (y0_target_sq_corner + y1_target_sq_corner) / 2
    #   canvas.create_text(center_x, center_y, text=text_to_draw, fill=text_color, ...)
    # Let's stick to placing it at the center of the target square for simplicity,
    # which is what the controller's _draw_hint_score_on_square currently does.
    # This function (draw_hint_score_text) might be redundant if the controller handles text placement directly.
    # However, if it were to be used to place text *along* the arrow, the logic would be different.

    # Assuming the controller's _draw_hint_score_on_square is the one actually used for placing scores on squares:
    # This function (draw_hint_score_text) might not be directly called by the controller in the current setup
    # for the on-square scores. If it IS used elsewhere, ensure its text placement logic is correct for that context.
    # For now, just ensure it doesn't error.
    # A simple placement at the target square center:
    final_label_x = x2
    final_label_y = y2
    text_anchor = "center"

    canvas.create_text(final_label_x, final_label_y, text=text_to_draw, fill=text_color,
                       font=(HINT_SCORE_FONT_FAMILY, font_size, HINT_SCORE_FONT_WEIGHT), # Using global HINT_SCORE_FONT_WEIGHT
                       anchor=text_anchor, tags="hint_score_text")


def draw_dragged_piece(canvas: tk.Canvas, photo_image, mouse_x: int, mouse_y: int, current_square_size_px: int):
    if photo_image:
        canvas.create_image(mouse_x,mouse_y,image=photo_image,tags="dragged_piece",anchor="center")

def clear_all_dynamic_elements(canvas: tk.Canvas):
    tags_to_clear=["piece","arrow","highlight","possible_move_dot","hint_score_text","dragged_piece"]
    for tag in tags_to_clear: canvas.delete(tag)

def load_and_resize_piece_images(base_image_path: str, target_square_size: int) -> dict:
    resized_images={};
    if target_square_size<=0: return resized_images
    logging.info(f"cdu: Loading images from base: {os.path.abspath(base_image_path)} sz: {target_square_size}")
    for (piece_type,color),filename in PIECE_IMAGE_FILENAMES.items():
        file_path=os.path.join(base_image_path,filename)
        try:
            if not os.path.exists(file_path): logging.warning(f"cdu: Not found: {file_path}"); continue
            img=Image.open(file_path).convert("RGBA"); img_resized=img.resize((target_square_size,target_square_size),Image.LANCZOS)
            resized_images[(piece_type,color)]=ImageTk.PhotoImage(img_resized)
        except Exception as e: logging.error(f"cdu: Err load/resize {file_path}: {e}")
    if not resized_images: logging.warning(f"cdu: No images loaded from {os.path.abspath(base_image_path)}.")
    else: logging.info(f"cdu: Loaded/resized {len(resized_images)} images.")
    return resized_images

# ===== END OF FILE chess_draw_utils.py =====
