import pyttsx3, os
from pathlib import Path
from pydub import AudioSegment

def synth_to_wav(text, out_path, rate=180, voice_name=None):
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
    audio = AudioSegment.from_wav(tmp)
    audio.export(str(out_path), format="wav")
    os.remove(tmp)
    return out_path

if __name__ == "__main__":
    import sys
    t = " ".join(sys.argv[1:]) if len(sys.argv)>1 else "Hello world"
    out = Path("output/sample.wav")
    out.parent.mkdir(parents=True, exist_ok=True)
    synth_to_wav(t, out)
    print("Saved", out)
