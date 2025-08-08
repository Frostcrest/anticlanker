# synth_audio.py
import pyttsx3, os
from pathlib import Path

def synth_to_wav(text, out_path, rate=180, voice_name=None):
    """
    Generate a WAV file via pyttsx3 only (no pydub/ffmpeg dependency).
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    engine = pyttsx3.init()
    engine.setProperty('rate', rate)
    if voice_name:
        voices = engine.getProperty('voices')
        for v in voices:
            if voice_name.lower() in v.name.lower():
                engine.setProperty('voice', v.id)
                break

    tmp = str(out_path) + ".tmp.wav"
    engine.save_to_file(text, tmp)
    engine.runAndWait()

    # Move temp wav to final path
    if os.path.exists(tmp):
        os.replace(tmp, str(out_path))
    return out_path

if __name__ == "__main__":
    p = Path("output/sample.wav")
    synth_to_wav("Hello from the robot.", p)
    print("Saved", p)
