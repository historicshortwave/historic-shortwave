'use strict';
(function (root) {
  const seasons = ['winter', 'spring', 'summer', 'autumn'];
  const levelsDb = { winter: 0, spring: 1, summer: 2, autumn: 1 };
  const rates = { winter: 1, spring: 10, summer: 20, autumn: 10 };
  const beds = { winter: 'winter', spring: 'autumn', summer: 'summer', autumn: 'autumn' };
  const mix = { between: .24, loading: .08 };
  function outputGain(desired, season, ready) {
    if (!ready || !desired.power || !desired.enabled) return 0;
    const base = !desired.selected ? mix.between
      : ['loading', 'buffering'].includes(desired.mediaState) ? mix.loading : 0;
    return base * desired.gain * 10 ** (levelsDb[season] / 20);
  }
  function conditions(date = new Date()) {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit'
    }).formatToParts(date);
    const value = type => parts.find(part => part.type === type).value;
    const month = Number(value('month'));
    const actual = month === 12 || month <= 2 ? 'winter' : month <= 5 ? 'spring' : month <= 8 ? 'summer' : 'autumn';
    const season = actual;
    return { season, actual, easternDate: `${value('year')}-${value('month')}-${value('day')}`,
      bed: beds[season], db: levelsDb[season], rate: rates[season] };
  }
  class SeasonalNoise {
    constructor(onChange = () => {}) {
      this.onChange = onChange;
      this.condition = conditions(new Date());
      this.cache = new Map();
      this.crashes = [];
      this.activeCrashes = new Set();
      this.status = 'idle';
      this.desired = { power: false, enabled: true, gain: .45, selected: false, mediaState: 'idle' };
      this.generation = 0;
      this.onChange(this);
      this.refreshTimer = setInterval(() => this.refresh(), 60000);
      root.document?.addEventListener('visibilitychange', () => this.refresh());
    }
    refresh() {
      const next = conditions(new Date());
      const changed = next.season !== this.condition.season;
      this.condition = next;
      if (changed && this.ctx) this.loadSeason();
      this.onChange(this);
    }
    async start() {
      try {
        if (!this.ctx) {
          this.ctx = new (root.AudioContext || root.webkitAudioContext)();
          this.master = this.ctx.createGain();
          this.master.gain.value = 0;
          this.master.connect(this.ctx.destination);
          this.ctx.onstatechange = () => this.onChange(this);
        }
        // Do not let blocked Web Audio hold up archive playback indefinitely.
        let activationTimer;
        try {
          await Promise.race([
            this.ctx.resume(),
            new Promise((_, reject) => {
              activationTimer = setTimeout(() => reject(new Error('Audio activation blocked')), 2000);
            })
          ]);
        } finally { clearTimeout(activationTimer); }
        if (this.ctx.state !== 'running') throw new Error('Audio activation blocked');
      } catch (error) {
        this.status = 'error';
        this.error = 'Static audio could not start. Switch the receiver off/on to retry; check that this tab is not muted.';
        this.update(this.desired);
        this.onChange(this);
        throw error;
      }
      // Only context resumption is awaited. Archive playback never waits for downloads.
      if (this.status === 'idle' || this.status === 'error') this.loadSeason();
      this.update(this.desired);
    }
    async buffer(file) {
      if (!/^[a-z0-9-]+\.mp3$/.test(file)) throw new Error('Invalid static asset');
      if (!this.cache.has(file)) {
        const pending = (async () => {
          const response = await fetch(`./audio/seasonal/${file}`);
          if (!response.ok) throw new Error('Static asset unavailable');
          return this.ctx.decodeAudioData(await response.arrayBuffer());
        })();
        this.cache.set(file, pending);
        pending.catch(() => this.cache.delete(file));
      }
      return this.cache.get(file);
    }
    async loadSeason() {
      const generation = ++this.generation;
      this.status = 'loading';
      this.update(this.desired);
      this.onChange(this);
      try {
        if (!this.manifest) {
          if (!this.manifestPromise) this.manifestPromise = fetch('./audio/seasonal/manifest.json')
            .then(response => { if (!response.ok) throw new Error('Static manifest unavailable'); return response.json(); })
            .catch(error => { this.manifestPromise = null; throw error; });
          this.manifest = await this.manifestPromise;
        }
        const entry = this.manifest.beds[this.condition.bed];
        const bed = await this.buffer(entry.file);
        if (generation !== this.generation) return;
        this.source?.stop();
        this.source?.disconnect();
        this.bedGain?.disconnect();
        this.source = this.ctx.createBufferSource();
        this.source.buffer = bed;
        this.source.loop = true;
        this.source.loopEnd = Math.min(75, bed.duration);
        this.bedGain = this.ctx.createGain();
        this.bedGain.gain.value = entry.normalizationGain || 1;
        this.source.connect(this.bedGain).connect(this.master);
        this.source.start(0, Math.random() * this.source.loopEnd);
        this.status = 'ready';
        this.update(this.desired);
        this.onChange(this);
        // Crash assets are small and optional; a failed overlay must not silence the bed.
        if (!this.crashPromise) this.crashPromise = Promise.allSettled(
          this.manifest.crashes.map(async entry => ({ entry, buffer: await this.buffer(entry.file) }))
        ).then(results => {
          this.crashes = results.filter(result => result.status === 'fulfilled').map(result => result.value);
          this.scheduleCrash();
        });
        await this.crashPromise;
      } catch (error) {
        if (generation !== this.generation) return;
        this.status = 'error';
        this.error = 'Seasonal static unavailable; station playback is unaffected. Toggle static off/on to retry.';
        this.update(this.desired);
        this.onChange(this);
      }
    }
    update(desired) {
      this.desired = { ...desired };
      this.targetGain = outputGain(desired, this.condition.season, this.status === 'ready');
      if (this.master) {
        this.master.gain.cancelScheduledValues(this.ctx.currentTime);
        this.master.gain.setTargetAtTime(this.targetGain, this.ctx.currentTime, .06);
      }
      if (!this.targetGain) {
        clearTimeout(this.crashTimer);
        this.crashTimer = null;
        for (const source of this.activeCrashes) { try { source.stop(); } catch (_) {} }
        this.activeCrashes.clear();
      } else this.scheduleCrash();
    }
    scheduleCrash() {
      if (this.crashTimer || !this.targetGain || !this.crashes.length) return;
      const delay = Math.max(1100, -Math.log(1 - Math.random()) * 60000 / this.condition.rate);
      this.crashTimer = setTimeout(() => {
        this.crashTimer = null;
        if (!this.targetGain) return;
        const profile = this.condition.season === 'summer' ? 'summer' : 'autumn';
        const pool = this.crashes.filter(crash => crash.entry.file.startsWith(profile));
        if (pool.length) {
          const crash = pool[Math.floor(Math.random() * pool.length)];
          const source = this.ctx.createBufferSource(), gain = this.ctx.createGain();
          source.buffer = crash.buffer;
          source.playbackRate.value = .92 + Math.random() * .16;
          gain.gain.value = .32 + Math.random() * .28;
          source.connect(gain).connect(this.master);
          this.activeCrashes.add(source);
          source.onended = () => { this.activeCrashes.delete(source); source.disconnect(); gain.disconnect(); };
          source.start();
        }
        this.scheduleCrash();
      }, delay);
    }
  }
  root.SeasonalNoise = SeasonalNoise;
  if (typeof module !== 'undefined' && module.exports) module.exports = { conditions, levelsDb, rates, beds, mix, outputGain };
})(typeof window === 'undefined' ? globalThis : window);
