# ===== START OF FILE blunder_feedback_panel.py =====
import tkinter as tk
from tkinter import ttk, scrolledtext
from utils import pwin_to_cp, format_score_for_display # IMPORT FROM UTILS

class BlunderFeedbackPanel:
    """Panel for displaying blunder information and feedback"""

    def __init__(self, parent):
        self.parent = parent
        self._create_widgets()

    def _create_widgets(self):
        # Blunder info section
        self.blunder_frame = ttk.LabelFrame(self.parent, text="Blunder Details", padding=10)
        self.blunder_frame.pack(fill=tk.X, pady=5, side=tk.TOP, anchor=tk.N)

        self.ply_var = tk.StringVar(value="Ply: N/A")
        ttk.Label(self.blunder_frame, textvariable=self.ply_var).pack(anchor=tk.W)

        self.move_var = tk.StringVar(value="Blunder: N/A")
        ttk.Label(self.blunder_frame, textvariable=self.move_var).pack(anchor=tk.W)

        self.drop_var = tk.StringVar(value="Eval Drop: N/A") # Default label text
        ttk.Label(self.blunder_frame, textvariable=self.drop_var).pack(anchor=tk.W)

        # User attempt feedback
        self.attempt_frame = ttk.LabelFrame(self.parent, text="Your Attempt", padding=10)
        self.attempt_frame.pack(fill=tk.X, pady=5, side=tk.TOP, anchor=tk.N)

        self.feedback_var = tk.StringVar(value="Make your move on the board.")
        feedback_label = ttk.Label(self.attempt_frame, textvariable=self.feedback_var, wraplength=350)
        feedback_label.pack(anchor=tk.W, fill=tk.X, expand=True)


        # Engine hints
        self.hints_frame = ttk.LabelFrame(self.parent, text="Engine Suggestions", padding=10)
        self.hints_frame.pack(fill=tk.BOTH, expand=True, pady=5, side=tk.TOP)


        self.hints_text = scrolledtext.ScrolledText(
            self.hints_frame, height=8, width=40, wrap=tk.WORD,
            state=tk.DISABLED, font=("Courier New", 13, "bold"))
        self.hints_text.pack(fill=tk.BOTH, expand=True)

    def update_blunder_info(self, blunder_data, use_cp_display=False):
        if not blunder_data:
            self.ply_var.set("Ply: N/A")
            self.move_var.set("Blunder: N/A")
            self.drop_var.set("Eval Drop: N/A" if use_cp_display else "P(Win) Drop: N/A")
            return

        self.ply_var.set(f"Ply: {blunder_data.get('ply_number', 'N/A')}")
        self.move_var.set(f"Blunder: {blunder_data.get('blunder_move_san', 'N/A')}")

        p_win_drop_from_json = blunder_data.get('p_win_drop_9M') # This is always a P(Win) delta

        if use_cp_display:
            cp_drop_display_str = "N/A"
            # Try to calculate CP drop from absolute P(Win) values if available
            top_moves_9m = blunder_data.get('top_moves_9M_before_blunder', [])
            p_win_after_actual_blunder = blunder_data.get('p_win_after_move_9M')

            pwin_optimal = None
            if top_moves_9m and isinstance(top_moves_9m, list) and len(top_moves_9m) > 0 and \
               isinstance(top_moves_9m[0], dict) and 'p_win' in top_moves_9m[0]:
                pwin_optimal = top_moves_9m[0]['p_win']

            if pwin_optimal is not None and p_win_after_actual_blunder is not None:
                cp_optimal = pwin_to_cp(pwin_optimal)
                cp_after_blunder = pwin_to_cp(p_win_after_actual_blunder)

                if cp_optimal is not None and cp_after_blunder is not None:
                    actual_cp_drop_val = cp_optimal - cp_after_blunder # This is in centipawns
                    cp_drop_display_str = format_score_for_display(actual_cp_drop_val, is_cp=True) + " pawns"
                else:
                    cp_drop_display_str = "N/A (PWin to CP conversion error)"
            else:
                # Fallback if absolute P(Win) values for drop calculation are missing
                cp_drop_display_str = "N/A (incomplete data for CP drop)"
                if p_win_drop_from_json is not None:
                     cp_drop_display_str += f" (P(Win) Drop: {p_win_drop_from_json:.3f})"


            self.drop_var.set(f"Eval Drop (9M): {cp_drop_display_str}")
        else: # Display as P(Win) drop
            p_win_drop_str = format_score_for_display(p_win_drop_from_json, is_cp=False)
            self.drop_var.set(f"P(Win) Drop (9M): {p_win_drop_str}")


    def update_feedback(self, message):
        self.feedback_var.set(message)

    def update_hints(self, hints_text_content):
        self.hints_text.config(state=tk.NORMAL)
        self.hints_text.delete('1.0', tk.END)
        self.hints_text.insert('1.0', hints_text_content)
        self.hints_text.config(state=tk.DISABLED)

    def clear_hints(self):
        self.update_hints("")
# ===== END OF FILE blunder_feedback_panel.py =====
