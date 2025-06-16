# File: /mnt/pacer/Projects/chess_trainer/web_player_folder/searchless_chess/src/engines/constants.py

# Copyright 2025 DeepMind Technologies Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

"""Constants for the engines."""

import functools
import os
import sys # Import sys for the flush

import chess
import chess.engine
import chess.pgn
from jax import random as jrandom  # <<< ENSURE THIS MODULE-LEVEL IMPORT IS PRESENT
import numpy as np

# These imports will now resolve relative to web_player_folder/searchless_chess/src/
from searchless_chess.src import tokenizer
from searchless_chess.src import training_utils
from searchless_chess.src import transformer
from searchless_chess.src import utils
from searchless_chess.src.engines import lc0_engine
from searchless_chess.src.engines import neural_engines
from searchless_chess.src.engines import stockfish_engine

# --- START OF IDENTIFICATION AND MODIFICATION ---
print("="*50, flush=True)
print(">>> EXECUTING MODIFIED web_player_folder/searchless_chess/src/engines/constants.py (SIMSIM314's VERSION V2 - FULL) <<<", flush=True)
print(f">>> Current __file__ for this constants.py: {os.path.abspath(__file__)} <<<", flush=True)
print("="*50, flush=True)

_THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
print(f">>> DEBUG: _THIS_FILE_DIR = {_THIS_FILE_DIR}", flush=True)

_SEARCHLESS_CHESS_ROOT_DIR = os.path.dirname(os.path.dirname(_THIS_FILE_DIR))
print(f">>> DEBUG: _SEARCHLESS_CHESS_ROOT_DIR = {_SEARCHLESS_CHESS_ROOT_DIR}", flush=True)

_CHECKPOINTS_BASE_DIR = os.path.join(_SEARCHLESS_CHESS_ROOT_DIR, "checkpoints")
print(f">>> DEBUG: _CHECKPOINTS_BASE_DIR = {_CHECKPOINTS_BASE_DIR}", flush=True)
# --- END OF IDENTIFICATION AND MODIFICATION ---


def _build_neural_engine(
    model_name: str,
    checkpoint_step: int = -1,
) -> neural_engines.NeuralEngine:
  """Returns a neural engine."""
  print(f">>> INSIDE _build_neural_engine (from web_player_folder version) for model: {model_name} <<<", flush=True)

  # --- TEMPORARY DEBUG IMPORT ---
  print(">>> DEBUG: Attempting to import jax.random as jrandom_local INSIDE _build_neural_engine <<<", flush=True)
  jrandom_local_imported_successfully = False
  try:
    from jax import random as jrandom_local # Use a different alias
    print(">>> DEBUG: Successfully imported jrandom_local INSIDE function <<<", flush=True)
    jrandom_local_imported_successfully = True
  except Exception as e:
    print(f">>> DEBUG: FAILED to import jrandom_local INSIDE function: {e} <<<", flush=True)
  # --- END TEMPORARY DEBUG IMPORT ---

  # Check if the module-level jrandom is defined
  if 'jrandom' in globals() or 'jrandom' in locals():
      print(">>> DEBUG: Module-level 'jrandom' IS defined before use. <<<", flush=True)
  else:
      print(">>> DEBUG: Module-level 'jrandom' IS NOT defined before use. THIS IS THE PROBLEM. <<<", flush=True)


  match model_name:
    case '9M':
      policy = 'action_value'
      num_layers = 8
      embedding_dim = 256
      num_heads = 8
    case '136M':
      policy = 'action_value'
      num_layers = 8
      embedding_dim = 1024
      num_heads = 8
    case '270M':
      policy = 'action_value'
      num_layers = 16
      embedding_dim = 1024
      num_heads = 8
    case 'local':
      policy = 'action_value'
      num_layers = 4
      embedding_dim = 64
      num_heads = 4
    case _:
      raise ValueError(f'Unknown model: {model_name}')

  num_return_buckets = 128

  match policy:
    case 'action_value':
      output_size = num_return_buckets
    case 'behavioral_cloning':
      output_size = utils.NUM_ACTIONS
    case 'state_value':
      output_size = num_return_buckets

  predictor_config = transformer.TransformerConfig(
      vocab_size=utils.NUM_ACTIONS,
      output_size=output_size,
      pos_encodings=transformer.PositionalEncodings.LEARNED,
      max_sequence_length=tokenizer.SEQUENCE_LENGTH + 2,
      num_heads=num_heads,
      num_layers=num_layers,
      embedding_dim=embedding_dim,
      apply_post_ln=True,
      apply_qk_layernorm=False,
      use_causal_mask=False,
  )

  predictor = transformer.build_transformer_predictor(config=predictor_config)

  print(f">>> DEBUG _build_neural_engine: _CHECKPOINTS_BASE_DIR = {_CHECKPOINTS_BASE_DIR}", flush=True)
  print(f">>> DEBUG _build_neural_engine: model_name = {model_name}", flush=True)

  checkpoint_dir = os.path.join(
      _CHECKPOINTS_BASE_DIR,
      model_name,
  )
  print(f">>> DEBUG _build_neural_engine: Attempting checkpoint_dir = {checkpoint_dir}", flush=True)


  if not os.path.exists(checkpoint_dir):
      print(f"!!! ERROR (web_player_folder version): Checkpoint directory NOT FOUND: {checkpoint_dir}", flush=True)
      raise FileNotFoundError(
          f"CRITICAL ERROR IN MODIFIED 'web_player_folder/searchless_chess/src/engines/constants.py': "
          f"Constructed checkpoint_dir does not exist: {checkpoint_dir}. "
          f"_SEARCHLESS_CHESS_ROOT_DIR was: {_SEARCHLESS_CHESS_ROOT_DIR}"
      )
  else:
      print(f"--- SUCCESS (web_player_folder version): Checkpoint directory FOUND: {checkpoint_dir}", flush=True)

  print(">>> DEBUG: About to call training_utils.load_parameters <<<", flush=True)
  
  # Determine which jrandom to use for the call
  # Prioritize the module-level one if it's somehow defined, otherwise try the local one
  # This is purely for debugging this strange NameError
  rng_key_source = None
  if 'jrandom' in globals() or 'jrandom' in locals():
      rng_key_source = jrandom.PRNGKey(1)
      print(">>> DEBUG: Using module-level jrandom for PRNGKey <<<", flush=True)
  elif jrandom_local_imported_successfully:
      rng_key_source = jrandom_local.PRNGKey(1)
      print(">>> DEBUG: Using function-local jrandom_local for PRNGKey <<<", flush=True)
  else:
      print(">>> DEBUG: NEITHER jrandom NOR jrandom_local is available for PRNGKey. Expecting NameError. <<<", flush=True)
      # Let the NameError happen naturally if neither is defined.
      # If we force jrandom here and it's not defined, it will raise the NameError we're trying to debug.

  # If rng_key_source is still None, the original NameError for 'jrandom' will occur here if it was truly undefined
  # Or, if we used jrandom_local, and that was also undefined (e.g. import failed), an error would occur.
  try:
    params = training_utils.load_parameters(
        checkpoint_dir=checkpoint_dir,
        params=predictor.initial_params(
            rng=jrandom.PRNGKey(1), # Explicitly use the module-level jrandom to test its definition
            targets=np.ones((1, 1), dtype=np.uint32),
        ),
        step=checkpoint_step,
    )
  except NameError as ne:
    print(f">>> DEBUG: CAUGHT NameError during predictor.initial_params or load_parameters: {ne} <<<", flush=True)
    if 'jrandom' in str(ne):
        print(">>> DEBUG: The NameError is for 'jrandom'. This confirms the module-level import is not working/visible here.", flush=True)
    if jrandom_local_imported_successfully:
        print(">>> DEBUG: Trying again with jrandom_local... <<<", flush=True)
        params = training_utils.load_parameters(
            checkpoint_dir=checkpoint_dir,
            params=predictor.initial_params(
                rng=jrandom_local.PRNGKey(1), 
                targets=np.ones((1, 1), dtype=np.uint32),
            ),
            step=checkpoint_step,
        )
        print(">>> DEBUG: Successfully used jrandom_local. <<<", flush=True)
    else:
        raise ne # Re-raise the original error if local import also failed

  _, return_buckets_values = utils.get_uniform_buckets_edges_values(
      num_return_buckets
  )
  return neural_engines.ENGINE_FROM_POLICY[policy](
      return_buckets_values=return_buckets_values,
      predict_fn=neural_engines.wrap_predict_fn(
          predictor=predictor,
          params=params,
          batch_size=1,
      ),
  )


ENGINE_BUILDERS = {
    'local': functools.partial(_build_neural_engine, model_name='local'),
    '9M': functools.partial(
        _build_neural_engine, model_name='9M', checkpoint_step=6_400_000
    ),
    '136M': functools.partial(
        _build_neural_engine, model_name='136M', checkpoint_step=6_400_000
    ),
    '270M': functools.partial(
        _build_neural_engine, model_name='270M', checkpoint_step=6_400_000
    ),
    'stockfish': lambda: stockfish_engine.StockfishEngine(
        limit=chess.engine.Limit(time=0.05)
    ),
    'stockfish_all_moves': lambda: stockfish_engine.AllMovesStockfishEngine(
        limit=chess.engine.Limit(time=0.05)
    ),
    'leela_chess_zero_depth_1': lambda: lc0_engine.AllMovesLc0Engine(
        limit=chess.engine.Limit(nodes=1),
    ),
    'leela_chess_zero_policy_net': lambda: lc0_engine.Lc0Engine(
        limit=chess.engine.Limit(nodes=1),
    ),
    'leela_chess_zero_400_sims': lambda: lc0_engine.Lc0Engine(
        limit=chess.engine.Limit(nodes=400),
    ),
}

print(">>> FINISHED LOADING MODIFIED web_player_folder/searchless_chess/src/engines/constants.py (SIMSIM314's VERSION V2 - FULL) <<<", flush=True)
print("="*50, flush=True)
