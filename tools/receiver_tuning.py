"""Test helper: tune the receiver using only its fixed controls.

The receiver has no typed frequency box. Tests reach a frequency the way a
listener can: the Band list (under Alternative controls) selects the band if
needed, then the full-band tuning slider moves to the frequency.
"""

BANDS = {"90m": (3150, 3500), "60m": (4700, 5085), "49m": (5850, 6350)}


def band_for(khz):
    khz = float(khz)
    for band, (lo, hi) in BANDS.items():
        if lo <= khz <= hi:
            return band
    raise ValueError(f"{khz} kHz is outside every receiver band")


def tune_to(page, khz, wait_ms=0):
    khz = float(khz)
    band = band_for(khz)
    lo, hi = BANDS[band]
    if page.evaluate("document.getElementById('band-select').value") != band:
        page.evaluate("""b => { const s = document.getElementById('band-select');
            s.value = b; s.dispatchEvent(new Event('change', {bubbles: true})); }""", band)
    page.wait_for_function("""([lo, hi]) => { const s = document.getElementById('band-slider');
        return Number(s.min) === lo && Number(s.max) === hi; }""", arg=[lo, hi], timeout=10000)
    page.evaluate("""k => { const s = document.getElementById('band-slider');
        s.value = String(k); s.dispatchEvent(new Event('input', {bubbles: true})); }""", khz)
    if wait_ms:
        page.wait_for_timeout(wait_ms)
