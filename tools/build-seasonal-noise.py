"""Build gapless, mono seasonal noise assets from approved post-sign-off tails."""
import json
import subprocess
from pathlib import Path
from urllib.parse import quote

import numpy as np
from scipy import ndimage, signal

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app/heritage-h60/audio/seasonal"
OUT.mkdir(parents=True, exist_ok=True)
SR = 16000
LOOP_SECONDS = 75
FADE_SECONDS = 3
SOURCES = {
    "winter": {
        "identifier": "wtww.-bob-biermann-and-glenn-hauser.-fri.-2025-12-06-t-04-51-00-z-5085.0k-hz",
        "filename": "WTWW. Bob biermann and Glenn Hauser. Fri. 2025-12-06T04_51_00Z_5085.0kHz.mp3",
        "offsetSeconds": 5700,
        "recordingDateLabel": "2025-12-06 UTC",
        "frequencyKHz": 5085,
    },
    "summer": {
        "identifier": "wrmi-muffled-audio.-glenn-hauser-then-signoff.-2026-08-22-t-03-40-08-z-5085.0k-hz",
        "filename": "WRMI, muffled audio. Glenn Hauser then signoff. 2026-08-22T03_40_08Z_5085.0kHz.mp3",
        "offsetSeconds": 1200,
        "recordingDateLabel": "2026-08-22 UTC",
        "frequencyKHz": 5085,
    },
    "autumn": {
        "identifier": "wbcq.-auto-recording-so-there-is-dead-air-at-the-end.-sun.-2025-11-10-t-04-36-43-z-5130.0k-hz",
        "filename": "WBCQ. Auto recording so there is dead air at the end. Sun. 2025-11-10T04_36_43Z_5130.0kHz.mp3",
        "offsetSeconds": 5400,
        "recordingDateLabel": "2025-11-10 UTC",
        "frequencyKHz": 5130,
    },
}


def run(args, data=None):
    result = subprocess.run(args, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout


def read_tail(source):
    url = "https://archive.org/download/" + source["identifier"] + "/" + quote(source["filename"])
    raw = run([
        "ffmpeg", "-v", "error", "-rw_timeout", "20000000",
        "-ss", str(source["offsetSeconds"]), "-i", url,
        "-t", str(LOOP_SECONDS + FADE_SECONDS), "-ac", "1", "-ar", str(SR),
        "-f", "f32le", "pipe:1",
    ])
    samples = np.frombuffer(raw, dtype="<f4").astype(np.float64)
    if len(samples) < (LOOP_SECONDS + FADE_SECONDS) * SR:
        raise RuntimeError("Source tail was shorter than the requested window")
    return samples[: (LOOP_SECONDS + FADE_SECONDS) * SR]


def encode(name, samples):
    target = OUT / name
    run([
        "ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR),
        "-ac", "1", "-i", "pipe:0", "-c:a", "libmp3lame", "-b:a", "64k",
        "-write_xing", "1", "-id3v2_version", "3", str(target),
    ], np.asarray(samples, dtype="<f4").tobytes())
    # Measure the actual encoded/decoded audio, not just the pre-encode samples.
    decoded = np.frombuffer(run([
        "ffmpeg", "-v", "error", "-i", str(target), "-ac", "1", "-ar", str(SR),
        "-f", "f32le", "pipe:1",
    ]), dtype="<f4").astype(np.float64)
    rms = np.sqrt(np.mean(decoded ** 2))
    return {
        "file": name, "durationSeconds": len(decoded) / SR,
        "rms": float(rms), "peak": float(np.max(np.abs(decoded))),
        "bytes": target.stat().st_size,
        "seamStep": float(abs(decoded[-1] - decoded[0])),
        "ordinaryStepP999": float(np.quantile(np.abs(np.diff(decoded)), 0.999)),
    }


def harmonic_energy(samples):
    frequencies, power = signal.welch(samples, fs=SR, nperseg=SR * 2)
    bands = np.zeros(len(frequencies), dtype=bool)
    for hz in np.arange(59.94, 5000, 59.94):
        bands |= abs(frequencies - hz) <= 1
    return float(power[bands].sum() / max(power.sum(), 1e-15))


manifest = {
    "schemaVersion": 1,
    "loopSeconds": LOOP_SECONDS,
    "sampleRate": SR,
    "format": "mono MP3; decoded gapless buffer loop",
    "dateBasis": "America/New_York",
    "levelsDb": {"winter": 0, "spring": 1, "summer": 2, "autumn": 1},
    "crashesPerMinute": {"winter": 1, "spring": 10, "summer": 20, "autumn": 10},
    "seasonBeds": {"winter": "winter", "spring": "autumn", "summer": "summer", "autumn": "autumn"},
    "credit": "J. Christie (Internet Archive uploader zardoz12) / NA5B WebSDR, Washington, DC",
    "rightsLabel": "Noise-only tails from uploads marked Public Domain Mark 1.0; not broadcast program excerpts",
    "licenseUrl": "https://creativecommons.org/publicdomain/mark/1.0/",
    "beds": {},
    "crashes": [],
}
filtered = {}
for season, source in SOURCES.items():
    print("Extracting " + season + " noise tail", flush=True)
    samples = read_tail(source)
    samples = signal.sosfiltfilt(signal.butter(2, 40, "highpass", fs=SR, output="sos"), samples)
    before = harmonic_energy(samples)
    if season == "winter":
        # The recording's harmonic comb is slightly below nominal 60 Hz.
        # Fixed 3 Hz-wide notches also remove its higher audible harmonics.
        for hz in np.arange(59.94, 5000, 59.94):
            b, a = signal.iirnotch(hz, hz / 3, fs=SR)
            samples = signal.filtfilt(b, a, samples)
    after = harmonic_energy(samples)
    filtered[season] = samples
    # Reduce the largest embedded impulses so additional stochastic crashes
    # add variety without simply doubling the original peak-crash density.
    envelope = np.sqrt(np.maximum(ndimage.uniform_filter1d(samples ** 2, int(SR * .020)), 0))
    ceiling = np.median(envelope) * 2.5
    attenuation = np.minimum(1, ceiling / np.maximum(envelope, 1e-12))
    attenuation = ndimage.gaussian_filter1d(attenuation, SR * .010)
    bed = samples * attenuation
    fade = FADE_SECONDS * SR
    loop = bed[fade:].copy()
    angle = np.linspace(0, np.pi / 2, fade, endpoint=True)
    loop[-fade:] = bed[-fade:] * np.cos(angle) + bed[:fade] * np.sin(angle)
    loop *= .12 / max(np.sqrt(np.mean(loop ** 2)), 1e-12)
    loop = np.clip(loop, -.65, .65)
    entry = encode(season + "-bed.mp3", loop)
    # Correct small codec RMS differences at runtime, preserving 0/+1/+2 dB.
    entry["normalizationGain"] = .12 / entry["rms"]
    entry["sourcePage"] = "https://archive.org/details/" + source["identifier"]
    entry["sourceFile"] = source["filename"]
    entry["sourceOffsetSeconds"] = source["offsetSeconds"]
    entry["inputSeconds"] = LOOP_SECONDS + FADE_SECONDS
    entry["crossfadeSeconds"] = FADE_SECONDS
    entry["recordingDateLabel"] = source["recordingDateLabel"]
    entry["frequencyKHz"] = source["frequencyKHz"]
    if season == "winter":
        entry["deBuzz"] = {
            "method": "59.94 Hz harmonic comb through 5 kHz; 3 Hz-wide zero-phase narrow notches",
            "harmonicEnergyFractionBefore": before,
            "harmonicEnergyFractionAfter": after,
            "harmonicSuppressionDb": float(10 * np.log10(max(after, 1e-15) / max(before, 1e-15))),
        }
    manifest["beds"][season] = entry

for season in ["summer", "autumn"]:
    samples = filtered[season]
    envelope = ndimage.uniform_filter1d(samples ** 2, int(SR * .030))
    peaks, _ = signal.find_peaks(envelope, distance=4 * SR)
    peaks = sorted(peaks, key=lambda p: envelope[p], reverse=True)
    peaks = [p for p in peaks if SR < p < len(samples) - SR][:3]
    if len(peaks) < 3:
        raise RuntimeError("Not enough separated crash candidates")
    for index, peak in enumerate(peaks, 1):
        start = peak - int(.12 * SR)
        crash = samples[start: start + int(.9 * SR)].copy()
        crash[:int(.008 * SR)] *= np.linspace(0, 1, int(.008 * SR))
        crash[-int(.15 * SR):] *= np.linspace(1, 0, int(.15 * SR))
        crash *= .65 / max(np.max(np.abs(crash)), 1e-12)
        entry = encode(f"{season}-crash-{index}.mp3", crash)
        entry["sourcePage"] = manifest["beds"][season]["sourcePage"]
        entry["sourceOffsetSeconds"] = SOURCES[season]["offsetSeconds"] + start / SR
        manifest["crashes"].append(entry)

(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({
    "beds": {name: {"seconds": entry["durationSeconds"], "bytes": entry["bytes"]} for name, entry in manifest["beds"].items()},
    "winterDebuzz": manifest["beds"]["winter"]["deBuzz"],
    "crashes": len(manifest["crashes"]),
}, indent=2), flush=True)
