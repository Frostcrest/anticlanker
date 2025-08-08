# audio_envelope.py
from pathlib import Path
import numpy as np
import soundfile as sf

def audio_to_envelope(wav_path: Path, n_frames: int, fps: int = 12, floor: float = 0.15, ceil: float = 1.0):
    """
    Returns an array of length n_frames with normalized mouth amplitudes [0..1]
    based on short-time RMS over the audio. Works with mono/stereo WAV.
    """
    wav_path = Path(wav_path)
    y, sr = sf.read(str(wav_path))  # shape (n,) or (n,2)
    if y.ndim == 2:
        y = y.mean(axis=1)

    # total duration and frame window size
    total_dur = len(y) / sr
    frame_dur = 1.0 / fps
    win_size = int(frame_dur * sr)
    amps = []
    for i in range(n_frames):
        start = int(i * win_size)
        end = start + win_size
        seg = y[start:end]
        if len(seg) == 0:
            val = 0.0
        else:
            # RMS -> normalize
            rms = np.sqrt(np.mean(seg**2)) if np.any(seg) else 0.0
            val = float(rms)
        amps.append(val)

    # normalize to [floor..ceil]
    a = np.array(amps, dtype=np.float32)
    if a.max() > 0:
        a = (a - a.min()) / (a.max() - a.min() + 1e-12)
    else:
        a[:] = 0.0
    a = floor + (ceil - floor) * a
    return a.tolist()
