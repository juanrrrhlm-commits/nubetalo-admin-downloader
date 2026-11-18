"""Generate an original short completion chime, with no external audio dependency."""
from array import array
import math
from pathlib import Path
import wave

root = Path(__file__).resolve().parent.parent
rate, duration = 44100, .65
samples = array('h')
for i in range(int(rate * duration)):
    t = i / rate
    signal = 0
    for start, frequency in [(0, 783.99), (.12, 987.77), (.24, 1318.51)]:
        local = t - start
        if 0 <= local < .4:
            envelope = min(1, local / .008) * math.exp(-local * 10) * min(1, (.4 - local) / .04)
            signal += math.sin(2 * math.pi * frequency * local) * envelope * .23
    samples.append(int(max(-1, min(1, signal)) * 32767))
with wave.open(str(root / 'assets/complete.wav'), 'wb') as output:
    output.setnchannels(1)
    output.setsampwidth(2)
    output.setframerate(rate)
    output.writeframes(samples.tobytes())
print('Completion chime: 650ms, PCM mono 44.1kHz')
