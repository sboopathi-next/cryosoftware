/**
 * dopamine_engine.js — Antigravity OS Audio & Haptic Dopamine Feedback Engine
 * Provides synthesized Web Audio API sound effects and mobile haptic motor vibrations
 * whenever tasks, routines, workouts, speech evaluations, or syncs complete.
 */

(function () {
  'use strict';

  let audioCtx = null;

  function getAudioContext() {
    if (!audioCtx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        audioCtx = new AudioCtx();
      }
    }
    return audioCtx;
  }

  /**
   * Triggers mobile vibration motor for tactile haptic feedback.
   * @param {string} type - 'completion' | 'milestone' | 'levelup' | 'sync' | 'error'
   */
  function triggerHapticShake(type = 'completion') {
    if (!navigator.vibrate) return;

    try {
      if (type === 'milestone' || type === 'levelup') {
        // High-intensity triple-pulse dopamine surge
        navigator.vibrate([40, 50, 40, 50, 90]);
      } else if (type === 'sync' || type === 'leetcode') {
        // Rapid dual tick
        navigator.vibrate([30, 40, 30]);
      } else if (type === 'error') {
        // Double warning buzz
        navigator.vibrate([70, 40, 70]);
      } else {
        // Standard satisfying dopamine tap (40ms pulse, 30ms pause, 60ms pulse)
        navigator.vibrate([40, 30, 60]);
      }
    } catch (e) {
      console.log('[Haptic Warning]', e);
    }
  }

  /**
   * Synthesizes crisp, satisfying sound effects via Web Audio API.
   * Produces a realistic "Chess Piece Snap / Wood Pop" on task completion.
   * @param {string} type - 'completion' | 'milestone' | 'levelup' | 'sync' | 'error'
   */
  function playDopamineSound(type = 'completion') {
    try {
      const ctx = getAudioContext();
      if (!ctx) return;

      const playOscillators = () => {
        const now = ctx.currentTime;

        if (type === 'milestone' || type === 'levelup') {
          // High Dopamine Major Surge Arpeggio: C5 (523Hz) -> E5 (659Hz) -> G5 (784Hz) -> C6 (1046Hz) -> E6 (1318Hz)
          const notes = [523.25, 659.25, 783.99, 1046.50, 1318.51];
          notes.forEach((freq, i) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();

            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, now + i * 0.055);

            gain.gain.setValueAtTime(0.01, now + i * 0.055);
            gain.gain.linearRampToValueAtTime(0.35, now + i * 0.055 + 0.015);
            gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.055 + 0.35);

            osc.connect(gain);
            gain.connect(ctx.destination);

            osc.start(now + i * 0.055);
            osc.stop(now + i * 0.055 + 0.38);
          });
        } else if (type === 'sync' || type === 'leetcode') {
          // Digital Sci-Fi Chime Sweep: 523Hz -> 1046Hz -> 1568Hz
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();

          osc.type = 'triangle';
          osc.frequency.setValueAtTime(523.25, now);
          osc.frequency.exponentialRampToValueAtTime(1046.50, now + 0.08);
          osc.frequency.exponentialRampToValueAtTime(1567.98, now + 0.16);

          gain.gain.setValueAtTime(0.3, now);
          gain.gain.exponentialRampToValueAtTime(0.001, now + 0.32);

          osc.connect(gain);
          gain.connect(ctx.destination);

          osc.start(now);
          osc.stop(now + 0.32);
        } else {
          // ─── Realistic Chess Piece Snap / Tactile Wood Pop ─────────────────
          // Layer 1: Resonant Low Wood Thud (360Hz -> 80Hz in 28ms)
          const woodOsc = ctx.createOscillator();
          const woodGain = ctx.createGain();
          woodOsc.type = 'sine';
          woodOsc.frequency.setValueAtTime(360, now);
          woodOsc.frequency.exponentialRampToValueAtTime(80, now + 0.028);

          woodGain.gain.setValueAtTime(0.5, now);
          woodGain.gain.exponentialRampToValueAtTime(0.001, now + 0.028);

          woodOsc.connect(woodGain);
          woodGain.connect(ctx.destination);
          woodOsc.start(now);
          woodOsc.stop(now + 0.028);

          // Layer 2: Crisp Mechanical Snap / Click (2400Hz -> 1100Hz in 12ms)
          const snapOsc = ctx.createOscillator();
          const snapGain = ctx.createGain();
          snapOsc.type = 'triangle';
          snapOsc.frequency.setValueAtTime(2400, now);
          snapOsc.frequency.exponentialRampToValueAtTime(1100, now + 0.012);

          snapGain.gain.setValueAtTime(0.35, now);
          snapGain.gain.exponentialRampToValueAtTime(0.001, now + 0.012);

          snapOsc.connect(snapGain);
          snapGain.connect(ctx.destination);
          snapOsc.start(now);
          snapOsc.stop(now + 0.012);
        }
      };

      if (ctx.state === 'suspended') {
        ctx.resume().then(playOscillators).catch(playOscillators);
      } else {
        playOscillators();
      }
    } catch (e) {
      console.warn('[Dopamine Sound Warning]', e);
    }
  }

  /**
   * Combined Master Dopamine Trigger (Audio Chime + Mobile Vibration Shake).
   * @param {string} type - 'completion' | 'milestone' | 'levelup' | 'sync' | 'error'
   */
  let lastSurgeTime = 0;
  function triggerDopamineSurge(type = 'completion') {
    const now = Date.now();
    if (now - lastSurgeTime < 150) return;
    lastSurgeTime = now;

    playDopamineSound(type);
    triggerHapticShake(type);
  }

  // Export functions to global window context
  window.playDopamineSound = playDopamineSound;
  window.triggerHapticShake = triggerHapticShake;
  window.triggerDopamineSurge = triggerDopamineSurge;

  // Global AudioContext unlocker on user interaction
  const unlockAudio = () => {
    const ctx = getAudioContext();
    if (ctx && ctx.state === 'suspended') {
      ctx.resume();
    }
  };
  document.addEventListener('click', unlockAudio, { passive: true });
  document.addEventListener('touchstart', unlockAudio, { passive: true });

})();
