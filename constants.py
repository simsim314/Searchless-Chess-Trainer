# ===== START OF FILE constants.py =====
import os
import chess

# --- Paths and Sizes ---
APP_NAME = "Chess Analyzer & Player"
APP_VERSION = "0.3.1" # Incremented
IMAGE_PATH = 'Images/60'
MIN_BOARD_SIZE_PX = 320
DEFAULT_BOARD_SIZE_PX = 480

# --- Piece Images ---
PIECE_IMAGE_FILENAMES = {
    (chess.PAWN, chess.WHITE): 'wP.png', (chess.PAWN, chess.BLACK): 'bP.png',
    (chess.KNIGHT, chess.WHITE): 'wN.png', (chess.KNIGHT, chess.BLACK): 'bN.png',
    (chess.BISHOP, chess.WHITE): 'wB.png', (chess.BISHOP, chess.BLACK): 'bB.png',
    (chess.ROOK, chess.WHITE): 'wR.png', (chess.ROOK, chess.BLACK): 'bR.png',
    (chess.QUEEN, chess.WHITE): 'wQ.png', (chess.QUEEN, chess.BLACK): 'bQ.png',
    (chess.KING, chess.WHITE): 'wK.png', (chess.KING, chess.BLACK): 'bK.png',
}

# --- Board Colors ---
LIGHT_SQUARE_COLOR = "#F0D9B5"
DARK_SQUARE_COLOR = "#B58863"

# --- Arrow Styling ---
ENGINE_MOVE_COLOR = "#0000CD"
PLAYER_MOVE_COLOR = "#006400"
PGN_MAINLINE_MOVE_COLOR = "#4B0082"
USER_PGN_MOVE_COLOR = "#228B22" # ForestGreen for user's actual move
SELECTED_SQUARE_HIGHLIGHT_COLOR = "#D2691E"
DRAG_TARGET_HIGHLIGHT_COLOR = "red"
ARROW_WIDTH_BASE = 12

# --- Hint Styling ---
HINT_PALETTE_1 = ["#FF8C00", "#BEBEBE", "#808080"]
HINT_PALETTE_2 = ["#0000CD", "#1E90FF", "#00BFFF"]
HINT_COMBINED_COLOR = "#9400D3"
HINT_SCORE_FONT_FAMILY = "Arial"
HINT_SCORE_FONT_SIZE_BASE = 10
HINT_SCORE_FONT_WEIGHT = "bold"
HINT_SCORE_TEXT_COLOR = "#FFFFFF" # White for better contrast on colored arrows

# --- Graph Styling ---
GRAPH_PRIMARY_ENGINE_COLOR = "#007ACC" # A distinct blue for the primary engine's P(Win) line
GRAPH_FIG_SIZE = (4, 2.5) # (width, height) in inches for the graph figure

# --- Logging ---
LOG_FORMAT = '%(asctime)s :: %(funcName)s :: line: %(lineno)d :: %(levelname)s :: %(message)s'
LOG_FILENAME = 'chess_analyzer_gui.log'

# --- Game Defaults ---
DEFAULT_PLAYER_NAME_TO_TRACK = "simsim314" # Your default player name
DEFAULT_PLAYER_SIDE = chess.WHITE
DEFAULT_ENGINE_NAME = "9M"

# --- Application Modes ---
APP_MODE_PLAYING = "PLAYING"
APP_MODE_ANALYZING_PGN = "ANALYZING_PGN"
# ===== END OF FILE constants.py =====