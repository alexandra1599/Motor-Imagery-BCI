"""
m0_initializeParams.py
=======================
ndf_main_adap.py already constructs a StreamBuffer instance
itself (StreamBuffer(n_ch=..., n_bip=..., buffer_seconds=..., ...)) and
then calls:

    initialize_params(decoder, stream)

So this version takes the EXISTING `stream` object and mutates its
attributes directly, matching that call site exactly (2 positional args,
no fs/frame_size — those are read off `stream` itself, which already
knows its own fs and frame_size from how ndf_main_adap.py constructed it).

NOTE -- channel count discrepancy (resolved):
  The original MATLAB sets stream.num_BIPchannels = 4, but your actual
  EOG checker (EOG.py: eog_checker) expects exactly 3 columns
  (h_eog = col1-col0, v_eog from col2 vs cols0:2, both built on a 3-column
  input), and ndf_main_adap.py / ndf_shared.py were built around 3 EOG
  channels (AUX7-8-9, confirmed earlier in this project as the only
  valid EOG-bearing channels in the XDF stream). This conversion does
  NOT overwrite stream.num_BIPchannels if it's already set on the
  incoming stream object (i.e. it preserves whatever ndf_main_adap.py's
  StreamBuffer(n_bip=3, ...) already configured) rather than blindly
  forcing it to the MATLAB literal 4 -- forcing 4 here would silently
  break eog_checker's column slicing 2 calls later.
"""

import numpy as np


def initialize_params(decoder: dict, stream, n_emg_channels: int = 1):
    """
    Initialize/augment an existing stream buffer object's parameters,
    mirroring m0_initializeParams.m's field-by-field setup -- but mutating
    the `stream` object already constructed by ndf_main_adap.py
    (a StreamBuffer instance) rather than building a fresh dict.

    Parameters
    ----------
    decoder : dict
        Decoder dict (same structure al0_builddecoder.py produces / loads).
        Must contain (or these are skipped gracefully if absent):
          decoder['sessionDetails']['durEpoch']            -- float, seconds
          decoder['fs']                                     -- float, Hz
          decoder['classification']['model']['ClassNames']  -- list/array
    stream : object
        The StreamBuffer instance already constructed in ndf_main_adap.py
        (has .fs/.fsamp, .frame_size, .num_channels, .num_BIPchannels,
        .eeg, .exg already set from its own __init__). This function adds
        the MATLAB-equivalent fields that StreamBuffer.__init__ doesn't
        already set (cycle_freq, cycle_time, previous_label, posterior,
        trigger), and leaves num_channels/num_BIPchannels/eeg/exg alone
        since those are already correctly sized by StreamBuffer.__init__.
    n_emg_channels : int, default 1
        Number of EMG channels (set but not otherwise used downstream in
        the original MATLAB, kept for fidelity / future use).

    Returns
    -------
    stream : the same object passed in, mutated in place.
    """
    # fsamp / fs: StreamBuffer already stores this as `stream.fs`.
    # Add the MATLAB-named alias too, in case other code expects `fsamp`.
    fsamp = getattr(stream, 'fs', None) or getattr(stream, 'fsamp', None)
    if fsamp is None:
        raise AttributeError(
            'stream object has neither .fs nor .fsamp set -- '
            'construct the StreamBuffer before calling initialize_params().')
    stream.fsamp = float(fsamp)

    frame_size = getattr(stream, 'frame_size', None)
    if frame_size is None:
        raise AttributeError(
            'stream object has no .frame_size set -- '
            'construct the StreamBuffer with frame_size before calling '
            'initialize_params().')

    stream.cycle_freq = round(stream.fsamp / frame_size)
    stream.cycle_time = frame_size / stream.fsamp

    # num_EMGchannels: not set by StreamBuffer.__init__, add it here
    # (kept for fidelity with the MATLAB struct; unused downstream so far).
    stream.num_EMGchannels = int(n_emg_channels)

    # Filter-state init flags -- StreamBuffer.__init__ already sets
    # init_filter / init_filter_eog to True via its own lazy-zi logic,
    # but set them explicitly here too for MATLAB fidelity / in case a
    # plain object (not StreamBuffer) is passed in.
    if not hasattr(stream, 'init_filter'):
        stream.init_filter = True
    if not hasattr(stream, 'init_filter_eog'):
        stream.init_filter_eog = True

    stream.previous_label = 0

    # MATLAB also reset a fixed-length, NaN-filled buffer sized to one
    # epoch duration here. ndf_main_adap.py's StreamBuffer instead keeps a
    # rolling BUFFER_SEC window — a deliberately different (and already
    # correctly NaN-initialized) buffering strategy, so we do NOT
    # overwrite stream.eeg / stream.exg here; doing so would clobber the
    # rolling buffer StreamBuffer.__init__ already allocated at the right
    # size. We only add `stream.trigger`, which StreamBuffer doesn't
    # currently provide.
    if 'sessionDetails' in decoder and 'durEpoch' in decoder['sessionDetails']:
        max_sample    = decoder['sessionDetails']['durEpoch'] * decoder.get('fs', stream.fsamp)
        signal_length = int(np.ceil(max_sample / frame_size) * frame_size)
    else:
        # Fall back to the stream's own buffer length if epoch duration
        # isn't present in this decoder (e.g. decoders built by
        # al0_builddecoder.py don't currently store sessionDetails).
        signal_length = stream.eeg.shape[0] if hasattr(stream, 'eeg') else int(stream.fsamp)

    stream.trigger = np.full((signal_length, 1), np.nan)

    # posterior buffer, sized to the decoder's class count
    n_classes = len(decoder['classification']['model']['ClassNames'])
    stream.posterior = np.zeros((10, n_classes))

    return stream
