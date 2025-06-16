import chess
import chess.pgn
import argparse
import json
# import logging # Using print for user feedback
import os
import sys
from datetime import datetime

try:
    from engines import SearchlessEngineManager, SEARCHLESS_ENGINES_AVAILABLE
except ImportError:
    print("FATAL: Could not import SearchlessEngineManager from engines.py.")
    print("Ensure engines.py is in PYTHONPATH or in the same directory.")
    sys.exit(1)

# --- Constants ---
DEFAULT_PLAYER_NAME_TO_TRACK = "simsim314"
DEFAULT_BLUNDER_THRESHOLD = 0.05
DEFAULT_NUM_TOP_MOVES_TO_REPORT = 3
SAVE_PROGRESS_EVERY_N_GAMES = 10
PROGRESS_BAR_WIDTH = 50


def print_progress_bar(iteration_val, total_val, prefix='', suffix='', decimals=1, length=100, fill='█', print_end="\r"):
    # (No change from previous version)
    if total_val == 0: percent_str = " N/A "; filled_length = 0
    else:
        percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration_val / float(total_val)))
        percent_str = f"{percent}%"; filled_length = int(length * iteration_val // total_val)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent_str} {suffix}'); sys.stdout.flush()
    if iteration_val >= total_val : sys.stdout.write('\n'); sys.stdout.flush()


def get_pwin_after_move(engine_mgr: SearchlessEngineManager, engine_name_to_use: str,
                        board_after_player_move: chess.Board, player_who_made_move: chess.Color) -> float | None:
    # (No change from previous version)
    if board_after_player_move.is_game_over(claim_draw=True):
        result = board_after_player_move.result(claim_draw=True)
        if result == "1-0": return 1.0 if player_who_made_move == chess.WHITE else 0.0
        elif result == "0-1": return 0.0 if player_who_made_move == chess.WHITE else 1.0
        else: return 0.5
    else:
        top_moves_opponent = engine_mgr.get_top_moves_with_eval(board_after_player_move, engine_name_to_use, num_moves=1)
        if not top_moves_opponent: return None
        p_win_for_opponent = top_moves_opponent[0]['p_win']
        return 1.0 - p_win_for_opponent


def scan_pgn_file(pgn_filepath: str, output_json_path: str, tracked_player: str, 
                  blunder_threshold: float, num_top_moves_to_report: int):
    
    blunders_found_list = [] # Overall list of blunders
    start_game_index_from_resume = 0
    pgn_filepath_abs = os.path.abspath(pgn_filepath)
    total_file_size = 0
    try: total_file_size = os.path.getsize(pgn_filepath_abs)
    except OSError: print(f"Warning: Could not get PGN file size. Progress bar by bytes inactive.")

    if os.path.exists(output_json_path): # (Resume logic unchanged)
        try:
            with open(output_json_path, 'r', encoding='utf-8') as f: report_data = json.load(f)
            if isinstance(report_data,dict) and "scan_progress" in report_data and "blunders" in report_data:
                progress_info = report_data["scan_progress"]
                if progress_info.get("last_pgn_filepath") == pgn_filepath_abs:
                    start_game_index_from_resume = progress_info.get("last_game_index_processed", -1) + 1
                    blunders_found_list = report_data["blunders"]
                    print(f"Resuming scan for '{pgn_filepath_abs}' from game index {start_game_index_from_resume}.")
                    print(f"Loaded {len(blunders_found_list)} existing blunders.")
                else: print(f"Output file '{output_json_path}' exists for a different PGN. Starting fresh scan.")
            else: print(f"Output file '{output_json_path}' has an old or unexpected format. Starting fresh scan.")
        except (json.JSONDecodeError,IOError) as e: print(f"Warning: Could not read report '{output_json_path}': {e}. Starting fresh.")

    engine_manager = SearchlessEngineManager()
    if not SEARCHLESS_ENGINES_AVAILABLE or not engine_manager.load_engines(): print("ERROR: Could not load engines. Aborting."); return None
    if not engine_manager.engine_9M or not engine_manager.engine_136M: print("ERROR: Both 9M and 136M engines required. Aborting."); return None

    print(f"Scanning PGN: {pgn_filepath_abs} for player: {tracked_player}")
    if start_game_index_from_resume > 0: print(f"Attempting to resume from game index: {start_game_index_from_resume}")

    current_game_index = -1; games_processed_in_this_session = 0
    last_saved_game_index = start_game_index_from_resume -1
    
    final_report_data = {
        "scan_progress": {"last_pgn_filepath":pgn_filepath_abs,"last_game_index_processed":start_game_index_from_resume-1},
        "blunders": blunders_found_list}

    try:
        with open(pgn_filepath, 'r', encoding='utf-8-sig') as pgn_file:
            if start_game_index_from_resume > 0: # Skip games logic
                print(f"Skipping to game index {start_game_index_from_resume}...")
                temp_skip_count = 0
                while temp_skip_count < start_game_index_from_resume:
                    if chess.pgn.read_game(pgn_file) is None:
                        print(f"\nWarning: EOF while skipping to game {start_game_index_from_resume}. Resetting scan.")
                        pgn_file.seek(0); start_game_index_from_resume = 0; blunders_found_list = []
                        final_report_data["blunders"]=blunders_found_list; final_report_data["scan_progress"]["last_game_index_processed"]=-1
                        break 
                    temp_skip_count += 1
                current_game_index = start_game_index_from_resume -1

            while True: # Main game processing loop
                current_game_index += 1; current_byte_offset = pgn_file.tell()
                if total_file_size > 0: print_progress_bar(current_byte_offset, total_file_size, prefix=f'Game {current_game_index}', suffix='Complete', length=PROGRESS_BAR_WIDTH)
                else: sys.stdout.write(f'\rProcessing Game {current_game_index}...'); sys.stdout.flush()
                
                game = chess.pgn.read_game(pgn_file)
                if game is None:
                    if total_file_size > 0: print_progress_bar(total_file_size, total_file_size, prefix='Scan', suffix='Complete', length=PROGRESS_BAR_WIDTH)
                    else: sys.stdout.write('\n')
                    break 

                games_processed_in_this_session += 1
                blunders_in_current_game = 0 # Initialize counter for this game

                tracked_player_color = None
                pgn_white=game.headers.get("White","").lower(); pgn_black=game.headers.get("Black","").lower()
                if tracked_player.lower()==pgn_white: tracked_player_color=chess.WHITE
                elif tracked_player.lower()==pgn_black: tracked_player_color=chess.BLACK
                if tracked_player_color is None: 
                    # Clear progress bar line before printing game summary
                    if total_file_size > 0 : sys.stdout.write(f"\r{'':<{PROGRESS_BAR_WIDTH+40}}\r") # Pad to clear
                    print(f"Game {current_game_index}: Tracked player not found. White: '{game.headers.get('White','?')}', Black: '{game.headers.get('Black','?')}'.")
                    sys.stdout.flush()
                    continue

                board = game.board()
                for node in game.mainline():
                    if board.turn != tracked_player_color:
                        board.push(node.move); continue
                    
                    fen_before_move = board.fen(); player_actual_move = node.move
                    
                    # Tier 1: Quick Check with 9M
                    top_moves_9m_optimal = engine_manager.get_top_moves_with_eval(board, "9M", num_moves=1)
                    p_win_optimal_9M = top_moves_9m_optimal[0]['p_win'] if top_moves_9m_optimal else None
                    
                    board_after_player_move_temp = board.copy()
                    board_after_player_move_temp.push(player_actual_move)
                    p_win_after_actual_move_9M = get_pwin_after_move(engine_manager, "9M", board_after_player_move_temp, tracked_player_color)

                    if p_win_optimal_9M is None or p_win_after_actual_move_9M is None:
                        board.push(player_actual_move); continue # Cannot evaluate with 9M

                    p_win_drop_9M = p_win_optimal_9M - p_win_after_actual_move_9M
                    if p_win_drop_9M < blunder_threshold:
                        board.push(player_actual_move); continue # Not a blunder by 9M

                    # Tier 2: Validate with 136M
                    top_moves_136m_optimal = engine_manager.get_top_moves_with_eval(board, "136M", num_moves=1)
                    p_win_optimal_136M = top_moves_136m_optimal[0]['p_win'] if top_moves_136m_optimal else None
                    # board_after_player_move_temp is already set up
                    p_win_after_actual_move_136M = get_pwin_after_move(engine_manager, "136M", board_after_player_move_temp, tracked_player_color)

                    if p_win_optimal_136M is None or p_win_after_actual_move_136M is None:
                        board.push(player_actual_move); continue # Cannot evaluate with 136M
                    
                    p_win_drop_136M = p_win_optimal_136M - p_win_after_actual_move_136M
                    if p_win_drop_136M < blunder_threshold:
                        board.push(player_actual_move); continue # Not a blunder by 136M

                    # Tier 3: Blunder Confirmed - Gather full details
                    top_moves_9m_before_report = engine_manager.get_top_moves_with_eval(board, "9M", num_top_moves_to_report)
                    top_moves_136m_before_report = engine_manager.get_top_moves_with_eval(board, "136M", num_top_moves_to_report)
                    
                    blunder_san = board.san(player_actual_move) if player_actual_move else "N/A"
                    blunder_info = {
                        "game_date": game.headers.get("Date","?"), "game_index_in_pgn_file": current_game_index,
                        "ply_number": board.ply(), "player_color": chess.COLOR_NAMES[tracked_player_color],
                        "fen_before_blunder": fen_before_move, "blunder_move_uci": player_actual_move.uci(),
                        "blunder_move_san": blunder_san, 
                        "p_win_optimal_9M_before": round(p_win_optimal_9M,4), "p_win_after_move_9M": round(p_win_after_actual_move_9M,4), "p_win_drop_9M": round(p_win_drop_9M,4),
                        "p_win_optimal_136M_before": round(p_win_optimal_136M,4), "p_win_after_move_136M": round(p_win_after_actual_move_136M,4), "p_win_drop_136M": round(p_win_drop_136M,4),
                        "top_moves_9M_before_blunder": top_moves_9m_before_report,
                        "top_moves_136M_before_blunder": top_moves_136m_before_report}
                    blunders_found_list.append(blunder_info)
                    blunders_in_current_game += 1
                    # Optional: print immediate blunder notification if desired, after clearing progress bar
                    # sys.stdout.write(f"\r{'':<100}\r") 
                    # print(f"  BLUNDER: Game {current_game_index}, Ply {board.ply()} {blunder_san}, Drop9M:{p_win_drop_9M:.2f}, Drop136M:{p_win_drop_136M:.2f}")
                    
                    board.push(player_actual_move)
                
                # After processing all moves in a game:
                if total_file_size > 0 : sys.stdout.write(f"\r{'':<{PROGRESS_BAR_WIDTH+40}}\r") # Clear progress bar line
                print(f"Game {current_game_index} ({game.headers.get('White','?')} vs {game.headers.get('Black','?')}) analysis complete. Blunders found in this game: {blunders_in_current_game}.")
                sys.stdout.flush()

                last_saved_game_index = current_game_index 
                if games_processed_in_this_session > 0 and games_processed_in_this_session % SAVE_PROGRESS_EVERY_N_GAMES == 0:
                    final_report_data["scan_progress"]["last_game_index_processed"] = last_saved_game_index
                    final_report_data["blunders"] = blunders_found_list
                    try:
                        with open(output_json_path,'w',encoding='utf-8') as f: json.dump(final_report_data,f,indent=2)
                        # print(f"Progress saved after game index {last_saved_game_index}.")
                    except IOError as e: print(f"\nERROR: Could not write progress: {e}")
            
            final_report_data["scan_progress"]["last_game_index_processed"] = last_saved_game_index if last_saved_game_index > -1 else current_game_index 

    except FileNotFoundError: print(f"\nERROR: PGN file not found: {pgn_filepath_abs}"); return None
    except Exception as e: print(f"\nERROR: Unexpected error: {e}"); import traceback; traceback.print_exc();
    if 'final_report_data' in locals(): final_report_data["scan_progress"]["last_game_index_processed"]=current_game_index if 'current_game_index' in locals() else -1; return final_report_data
    return None
    

def main():
    parser = argparse.ArgumentParser(description="Scan PGN for blunders.")
    parser.add_argument("pgn_file", help="Path to the PGN file.")
    parser.add_argument("--player", default=DEFAULT_PLAYER_NAME_TO_TRACK, help=f"Player to track (default: {DEFAULT_PLAYER_NAME_TO_TRACK}).")
    parser.add_argument("--threshold", type=float, default=DEFAULT_BLUNDER_THRESHOLD, help=f"P(Win) drop threshold (default: {DEFAULT_BLUNDER_THRESHOLD}).")
    parser.add_argument("--top_n_moves", type=int, default=DEFAULT_NUM_TOP_MOVES_TO_REPORT, dest="num_top_moves_report", help=f"Number of top alternative moves for report (default: {DEFAULT_NUM_TOP_MOVES_TO_REPORT}).")
    parser.add_argument("--output_json", default="blunders_report.json", help="Output JSON filename (default: blunders_report.json).")

    args = parser.parse_args()

    if not os.path.exists(args.pgn_file): print(f"ERROR: Input PGN file does not exist: {args.pgn_file}"); sys.exit(1)

    start_time = datetime.now(); print(f"Starting blunder scan at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    report_content = scan_pgn_file(args.pgn_file, args.output_json, args.player, args.threshold, args.num_top_moves_report)

    if report_content:
        try:
            with open(args.output_json, 'w', encoding='utf-8') as f: json.dump(report_content, f, indent=2)
            if report_content.get("blunders"): print(f"\nBlunder report saved to {args.output_json}. Found {len(report_content['blunders'])} blunders in total.")
            else: print(f"\nNo new blunders found. Progress report saved to {args.output_json}.")
        except IOError as e: print(f"\nERROR: Could not write JSON output: {e}")
    else: print("\nScan did not complete successfully or no data to report.")
    end_time = datetime.now(); print(f"Blunder scan finished at {end_time.strftime('%Y-%m-%d %H:%M:%S')}"); print(f"Total processing time: {end_time - start_time}")

if __name__ == "__main__":
    main()
