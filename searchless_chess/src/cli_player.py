# Copyright 2025 DeepMind Technologies Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");

from absl import app
from absl import flags
import chess

from searchless_chess.src.engines import constants

_AGENT = flags.DEFINE_enum(
    name='agent',
    default=None,
    enum_values=[
        'local',
        '9M',
        '136M',
        '270M',
        'stockfish',
        'stockfish_all_moves',
        'leela_chess_zero_depth_1',
        'leela_chess_zero_policy_net',
        'leela_chess_zero_400_sims',
    ],
    help='The agent to play against.',
    required=True,
)

def print_board(board: chess.Board):
    print("\n" + board.unicode())
    print(f"\nFEN: {board.fen()}")
    print(f"Turn: {'White' if board.turn else 'Black'}\n")

def play_game(engine) -> None:
    board = chess.Board()

    while not board.is_game_over():
        print_board(board)

        if board.turn:  # Human (White)
            move_input = input("Your move (UCI, e.g. e2e4): ").strip()
            try:
                move = chess.Move.from_uci(move_input)
                if move in board.legal_moves:
                    board.push(move)
                else:
                    print("Illegal move. Try again.")
            except Exception:
                print("Invalid format. Try UCI like e2e4.")
        else:  # Engine (Black)
            print("Engine thinking...")
            move_uci = engine.play(board=board).uci()
            print(f"Engine plays: {move_uci}")
            board.push(chess.Move.from_uci(move_uci))

    print_board(board)
    print("Game over.")
    print(f"Result: {board.result()}")

def main(argv):
    if len(argv) > 1:
        raise app.UsageError("Too many command-line arguments.")

    engine = constants.ENGINE_BUILDERS[_AGENT.value]()
    play_game(engine)

if __name__ == "__main__":
    app.run(main)

