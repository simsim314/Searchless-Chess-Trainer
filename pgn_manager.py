# ===== START OF FILE pgn_manager.py =====
import chess
import chess.pgn
import io
import logging

class PgnManager:
    def __init__(self):
        self.game: chess.pgn.Game | None = None
        self.current_node: chess.pgn.GameNode | None = None # Current node being viewed
        self.board_at_current_node: chess.Board | None = None # Board state for current_node

    def load_pgn_from_string(self, pgn_string: str) -> bool:
        try:
            pgn_file = io.StringIO(pgn_string)
            self.game = chess.pgn.read_game(pgn_file)
            if self.game:
                self.go_to_start()
                logging.info("PGN game loaded successfully.")
                return True
            else:
                logging.error("No game found in PGN string.")
                self.game = None; self.current_node = None; self.board_at_current_node = None
                return False
        except Exception as e:
            logging.error(f"Error loading PGN from string: {e}")
            self.game = None; self.current_node = None; self.board_at_current_node = None
            return False

    def is_game_loaded(self) -> bool:
        return self.game is not None

    def _update_board_for_current_node(self):
        if self.current_node:
            self.board_at_current_node = self.current_node.board()
        else:
            self.board_at_current_node = None # Should not happen if current_node is always valid from game

    def go_to_start(self):
        if not self.game: return
        self.current_node = self.game # The game object itself is the starting node
        self._update_board_for_current_node()
        logging.debug("PGN: Navigated to start.")

    def go_to_end(self):
        if not self.game: return
        self.current_node = self.game.end()
        self._update_board_for_current_node()
        logging.debug("PGN: Navigated to end.")

    def next_move(self) -> bool: # Returns True if successful, False if no next move
        if not self.current_node or self.current_node.is_end():
            logging.debug("PGN: Already at end or no next move.")
            return False
        # main_variation() gives the primary next move from this node
        # In PGN, a node can have multiple variations. We'll focus on the main one for now.
        if self.current_node.variations:
            self.current_node = self.current_node.variations[0]
            self._update_board_for_current_node()
            logging.debug(f"PGN: Moved to next: {self.get_current_move_san() if self.current_node.move else 'N/A'}")
            return True
        return False

    def previous_move(self) -> bool: # Returns True if successful, False if no previous
        if not self.current_node or self.current_node.parent is None: # game is its own parent effectively for start
            logging.debug("PGN: Already at start or no parent.")
            return False
        self.current_node = self.current_node.parent
        self._update_board_for_current_node()
        logging.debug(f"PGN: Moved to previous. Current move leading to this board: {self.get_current_move_san() if self.current_node.move else 'Initial'}")
        return True

    def get_current_board_fen(self) -> str | None:
        if self.board_at_current_node:
            return self.board_at_current_node.fen()
        return None
    
    def get_current_board_for_analysis(self) -> chess.Board | None:
        """Returns a copy of the board at the current node for analysis (e.g., hint generation)."""
        if self.board_at_current_node:
            return self.board_at_current_node.copy()
        return None

    def get_current_move_san(self) -> str | None:
        """Returns the SAN of the move that LED to the current_node's board state."""
        if self.current_node and self.current_node.move:
            # The SAN is stored on the node *relative to its parent's board*
            # We need the parent's board to correctly generate SAN for the current move.
            parent_board = self.current_node.parent.board() if self.current_node.parent else chess.Board() # Base board if no parent
            try:
                return parent_board.san(self.current_node.move)
            except Exception as e:
                logging.warning(f"PGN: Error generating SAN for move {self.current_node.move.uci()}: {e}")
                return self.current_node.move.uci() # Fallback to UCI
        return None # If at the start or no move

    def get_headers(self) -> chess.pgn.Headers:
        return self.game.headers if self.game else chess.pgn.Headers()

    def get_total_plies_mainline(self) -> int:
        if not self.game: return 0
        # self.game.ply() returns 0 after loading. We must go to the end.
        return self.game.end().ply()

    def get_current_ply_number(self) -> int:
        """Returns the ply number of the board position *after* current_node.move is made."""
        if self.current_node:
            return self.current_node.ply()
        return 0
# ===== END OF FILE pgn_manager.py =====