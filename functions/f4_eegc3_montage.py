import numpy as np
from typing import Union

# Predefined montage layouts (equivalent to MATLAB string cases)
PREDEFINED_MONTAGES = {
    "16ch": np.array(
        [
            [0, 0, 1, 0, 0],
            [0, 1, 1, 1, 0],
            [0, 1, 1, 1, 0],
            [1, 1, 1, 1, 1],
            [0, 1, 1, 1, 0],
            [0, 0, 1, 0, 0],
        ]
    ),
    "22ch": np.array(
        [
            [0, 0, 0, 1, 0, 0, 0],
            [0, 1, 1, 1, 1, 1, 0],
            [1, 1, 1, 1, 1, 1, 1],
            [0, 1, 1, 1, 1, 1, 0],
            [0, 0, 1, 1, 1, 0, 0],
            [0, 0, 0, 1, 0, 0, 0],
        ]
    ),
    "24ch": np.array(
        [
            [0, 1, 0, 0, 1, 0, 0, 1, 0],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [0, 1, 0, 0, 1, 0, 0, 1, 0],
        ]
    ),
    "28ch": np.array(
        [
            [0, 0, 0, 1, 0, 0, 0],
            [0, 1, 1, 1, 1, 1, 0],
            [1, 1, 1, 1, 1, 1, 1],
            [0, 1, 1, 1, 1, 1, 0],
            [0, 0, 1, 1, 1, 0, 0],
            [0, 0, 0, 1, 0, 0, 0],
            [1, 1, 1, 0, 1, 1, 1],
        ]
    ),
    "30ch": np.array(
        [
            [0, 0, 0, 1, 1, 1, 0, 0, 0],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
        ]
    ),
    "32ch": np.array(
        [
            [0, 0, 1, 1, 1, 1, 1, 0, 0],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
        ]
    ),
    "58ch": np.array(
        [
            [0, 0, 1, 1, 1, 1, 1, 0, 0],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [0, 0, 1, 1, 1, 1, 1, 0, 0],
            [0, 0, 0, 1, 1, 1, 0, 0, 0],
        ]
    ),
    "60ch": np.array(
        [
            [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
            [0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0],
            [0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0],
            [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0],
            [0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0],
            [0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0],
            [0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
        ]
    ),
}


def f4_eegc3_montage(montage: Union[str, np.ndarray]):
    """
    Compute the Laplacian spatial filter matrix for a given EEG montage.

    Equivalent of f4_eegc3_montage.m (originally getMontage by Brunner/Leeb).

    The Laplacian derivation for a data matrix s (n_samples × n_channels) is:
        s_lap = s @ lap

    Parameters
    ----------
    montage : str or np.ndarray
        - str  : one of '16ch','22ch','24ch','28ch','30ch','32ch','58ch','60ch'
        - array: matrix of electrode positions.
                 Values of 1 (binary) or electrode numbers (sequential order).
                 Zeros indicate empty positions.

    Returns
    -------
    lap         : np.ndarray, shape (n_electrodes, n_electrodes)
                  Laplacian filter matrix.
    plot_index  : np.ndarray — flat (column-major) indices of active electrodes
    n_rows      : int
    n_cols      : int
    """
    # --- Resolve montage matrix ---
    if isinstance(montage, str):
        if montage not in PREDEFINED_MONTAGES:
            raise ValueError(
                f'Unknown predefined montage: "{montage}". '
                f"Choose from {list(PREDEFINED_MONTAGES.keys())}"
            )
        temp = PREDEFINED_MONTAGES[montage].copy()
    else:
        temp = np.array(montage, dtype=float).copy()

    n_rows, n_cols = temp.shape

    # Column-major (Fortran order) flat indices of active electrodes
    # MATLAB's find(temp' >= 1) → transpose then find nonzero
    temp_T = temp.T
    plot_index = np.flatnonzero(temp_T >= 1)  # 0-based

    # --- Handle numbered electrode positions ---
    # If montage contains electrode numbers (not just 0/1), reorder later
    positions = None
    if temp.sum() != (temp > 0).sum():
        # Electrode numbers present — extract sorted order
        nonzero_vals = temp[temp > 0]
        positions = np.argsort(nonzero_vals)  # reorder indices
        temp = (temp > 0).astype(float)
        temp_T = temp.T

    # --- Build sequential electrode index map (column-major) ---
    lap_map = np.zeros_like(temp_T, dtype=int)
    counter = 1
    for k in range(lap_map.size):
        if temp_T.flat[k] == 1:
            lap_map.flat[k] = counter
            counter += 1
    n_electrodes = counter - 1

    # --- Find neighbours for each electrode ---
    # lap_map is (n_cols, n_rows) — column-major traversal matches MATLAB
    nrows_lm, ncols_lm = lap_map.shape  # (n_cols, n_rows) after transpose

    neighbors = np.full((n_electrodes, 4), np.nan)
    electrode = 0

    for k in range(lap_map.size):
        if lap_map.flat[k] != 0:
            col_ptr = 0
            electrode += 1
            row = k % nrows_lm
            col = k // nrows_lm

            # Top (k - nrows_lm in MATLAB's column-major)
            if col > 0 and lap_map[row, col - 1] != 0:
                neighbors[electrode - 1, col_ptr] = lap_map[row, col - 1]
                col_ptr += 1

            # Left (k+1 in MATLAB, next row)
            if row + 1 < nrows_lm and lap_map[row + 1, col] != 0:
                neighbors[electrode - 1, col_ptr] = lap_map[row + 1, col]
                col_ptr += 1

            # Right (k-1 in MATLAB, previous row)
            if row - 1 >= 0 and lap_map[row - 1, col] != 0:
                neighbors[electrode - 1, col_ptr] = lap_map[row - 1, col]
                col_ptr += 1

            # Bottom (k + nrows_lm in MATLAB)
            if col + 1 < ncols_lm and lap_map[row, col + 1] != 0:
                neighbors[electrode - 1, col_ptr] = lap_map[row, col + 1]
                col_ptr += 1

    # --- Build Laplacian matrix ---
    lap = np.eye(n_electrodes)
    for k in range(n_electrodes):
        valid = neighbors[k, ~np.isnan(neighbors[k])]
        valid = valid.astype(int) - 1  # convert to 0-based indices
        if len(valid) > 0:
            lap[k, valid] = -1.0 / len(valid)

    # --- Reorder if electrode numbers were given ---
    if positions is not None:
        lap = lap[np.ix_(positions, positions)]

    lap = lap.T  # matches MATLAB's final lap = lap'

    return lap, plot_index, n_rows, n_cols
