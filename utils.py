# ===== START OF FILE utils.py =====
import math
import logging
from typing import Dict, List, Tuple, Optional, Any, Callable, NamedTuple, Union 
import chess
import chess.variant
import random

def generate_random_chess960_rank():
    """Generate a valid Chess960 starting back rank as a string."""
    positions = [None] * 8

    # Place bishops on opposite color squares
    light_squares = [i for i in range(0, 8, 2)]
    dark_squares = [i for i in range(1, 8, 2)]
    positions[random.choice(light_squares)] = 'B'
    positions[random.choice(dark_squares)] = 'B'

    # Place queen
    empty = [i for i, x in enumerate(positions) if x is None]
    positions[random.choice(empty)] = 'Q'

    # Place knights
    empty = [i for i, x in enumerate(positions) if x is None]
    for _ in range(2):
        idx = random.choice(empty)
        positions[idx] = 'N'
        empty.remove(idx)

    # Place rooks and king (rook-king-rook order)
    empty = [i for i, x in enumerate(positions) if x is None]
    empty.sort()
    positions[empty[0]] = 'R'
    positions[empty[1]] = 'K'
    positions[empty[2]] = 'R'

    return ''.join(positions)

def setup_asymmetric_chess960():

    white_rank = generate_random_chess960_rank()
    black_rank = generate_random_chess960_rank()

    board = chess.Board(None, chess960=True)

    # Setup White
    for i, piece in enumerate(white_rank):
        board.set_piece_at(chess.square(i, 7), chess.Piece.from_symbol(piece.lower()))
        board.set_piece_at(chess.square(i, 6), chess.Piece.from_symbol('p'))

    # Setup Black
    for i, piece in enumerate(black_rank):
        board.set_piece_at(chess.square(i, 0), chess.Piece.from_symbol(piece.upper()))
        board.set_piece_at(chess.square(i, 1), chess.Piece.from_symbol('P'))
    
    board.clear_stack()
    board.turn = chess.WHITE
    board.set_castling_fen("KQkq")

    return board

def cp_to_pwin(centipawns: Optional[int]) -> Optional[float]:
    if centipawns is None:
        return None
    if not isinstance(centipawns, int):
        logging.warning(f"cp_to_pwin: Invalid centipawns type {type(centipawns)}, value {centipawns}. Returning None.")
        return None

    lichess_scaling_factor = 0.004
    
    exponent = -lichess_scaling_factor * float(centipawns)
    
    prob = 1.0 / (1.0 + math.exp(exponent))
    return prob
    
def pwin_to_cp(prob, a=0.4):
    """Converts P(Win) probability to centipawn evaluation.

    Args:
        prob (float or None): Probability of winning (0.0 to 1.0).
        a (float): Scaling factor for the conversion.

    Returns:
        int or None: Centipawn evaluation, or None if input is invalid.
                     Returns a capped value (-1500 or 1500) for probabilities
                     very close to 0 or 1.
    """
    if prob is None:
        return None
    if not isinstance(prob, (float, int)):
        logging.warning(f"pwin_to_cp: Invalid probability type {type(prob)}, value {prob}. Returning None.")
        return None

    epsilon = 1e-9  # Small value to prevent log(0) or division by zero

    # Normalize prob to be strictly within (epsilon, 1-epsilon) for log calculation
    if prob <= epsilon:
        return -1500  # Cap for extremely low P(Win)
    if prob >= 1.0 - epsilon:
        return 1500   # Cap for extremely high P(Win)

    try:
        # Formula: (1/a) * log(P / (1-P)) gives evaluation in pawns
        # Multiply by 100 to get centipawns
        pawns = (1 / a) * math.log(prob / (1.0 - prob))
        centipawns = round(pawns * 100)
        return centipawns
    except (ValueError, TypeError, OverflowError) as e:
        # This block should ideally not be reached if epsilon checks are done right,
        # but it's a safeguard.
        logging.error(f"Error in pwin_to_cp with prob={prob}, a={a}: {e}")
        if prob > 0.5: return 1500
        elif prob < 0.5: return -1500
        return 0 # Default for true errors or prob == 0.5 exactly

def format_score_for_display(score_value, is_cp=False):
    """Formats a score (either P(Win) or CP) for display."""
    if score_value is None:
        return "N/A"
    if is_cp:
        # score_value is already in centipawns, convert to pawns for display
        return f"{score_value / 100.0:.2f}"
    else:
        # score_value is P(Win)
        return f"{score_value:.3f}"

def test_cp_pwin_conversion():
    print("\n--- Testing cp_to_pwin and pwin_to_cp Conversions ---")
    all_tests_passed = True

    cp_to_pwin_cases = [
        ("CP: 0 to PWin", 0, 0.5),
        ("CP: +100 to PWin", 100, 0.637745),
        ("CP: -100 to PWin", -100, 0.362255),
        ("CP: +800 to PWin", 800, 0.950014),
        ("CP: -800 to PWin", -800, 0.049986),
        ("CP: None to PWin", None, None),
        ("CP: Large Positive (near 1.0 PWin)", 1500, 0.99999996),
        ("CP: Large Negative (near 0.0 PWin)", -1500, 0.00000003),
    ]

    print("\n  --- Testing cp_to_pwin ---")
    for desc, cp_val, expected_pwin in cp_to_pwin_cases:
        # Removed try-except OverflowError as cp_to_pwin does not handle it internally.
        # If an OverflowError occurs for an extreme cp_val, it will propagate and fail the test.
        actual_pwin = cp_to_pwin(cp_val)
        if actual_pwin is None and expected_pwin is None:
            print(f"    ✅ {desc}: Input CP={cp_val}, Expected PWin=None, Got=None -> PASS")
        elif actual_pwin is not None and expected_pwin is not None:
            if math.isclose(actual_pwin, expected_pwin, rel_tol=1e-5, abs_tol=1e-5):
                print(f"    ✅ {desc}: Input CP={cp_val}, Expected PWin={expected_pwin:.6f}, Got={actual_pwin:.6f} -> PASS")
            else:
                print(f"    ❌ {desc}: Input CP={cp_val}, Expected PWin={expected_pwin:.6f}, Got={actual_pwin:.6f} -> FAIL")
                all_tests_passed = False
        else: 
            print(f"    ❌ {desc}: Input CP={cp_val}, Expected PWin={expected_pwin}, Got={actual_pwin} -> FAIL (Mismatch None/Value)")
            all_tests_passed = False

    pwin_to_cp_cases = [
        ("PWin: 0.5 to CP", 0.5, 0),
        ("PWin: 0.637745 to CP", 0.637745, 100),
        ("PWin: 0.362255 to CP", 0.362255, -100),
        ("PWin: 0.95 to CP", 0.95, 799),
        ("PWin: 0.05 to CP", 0.05, -799),
        ("PWin: None to CP", None, None),
        ("PWin: 0.0 (near min_cp)", 0.0, -1500),
        ("PWin: 1.0 (near max_cp)", 1.0, 1500),
        ("PWin: 1e-10 (very low)", 1e-10, -1500),
        ("PWin: 1.0 - 1e-10 (very high)", 1.0 - 1e-10, 1500),
    ]

    print("\n  --- Testing pwin_to_cp ---")
    for desc, pwin_val, expected_cp in pwin_to_cp_cases:
        actual_cp = pwin_to_cp(pwin_val) 
        if actual_cp == expected_cp: 
            print(f"    ✅ {desc}: Input PWin={pwin_val}, Expected CP={expected_cp}, Got={actual_cp} -> PASS")
        else:
            print(f"    ❌ {desc}: Input PWin={pwin_val}, Expected CP={expected_cp}, Got={actual_cp} -> FAIL")
            all_tests_passed = False

    if all_tests_passed:
        print("\n✅ All cp_to_pwin and pwin_to_cp conversion tests passed.")
    else:
        print("\n❌ Some cp_to_pwin and pwin_to_cp conversion tests FAILED.")
    print("-" * 50)
    return all_tests_passed
 
if __name__ == "__main__":
     test_cp_pwin_conversion()
     print(setup_asymmetric_chess960().fen())
# ===== END OF FILE utils.py =====
