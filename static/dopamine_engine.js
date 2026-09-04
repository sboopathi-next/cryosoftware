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
   * Synthesizes rich, highly satisfying sound chimes via Web Audio API.
   * Handles audio context resume asynchronously to bypass browser autoplay blocks.
   * @param {string} type - 'completion' | 'milestone' | 'levelup' | 'sync' | 'error'
   */
  function playDopamineSound(type = 'completion') {
    try {
      const ctx = getAudioContext();
      if (!ctx) return;

      const playOscillators = () => {
        const now = ctx.currentTime;

        // Layer 1: Satisfying Tactile Sub-Bass Pop (Thump)
        const popOsc = ctx.createOscillator();
        const popGain = ctx.createGain();
        popOsc.type = 'sine';
        popOsc.frequency.setValueAtTime(160, now);
        popOsc.frequency.exponentialRampToValueAtTime(40, now + 0.06);

        popGain.gain.setValueAtTime(0.4, now);
        popGain.gain.exponentialRampToValueAtTime(0.001, now + 0.06);

        popOsc.connect(popGain);
        popGain.connect(ctx.destination);
        popOsc.start(now);
        popOsc.stop(now + 0.06);

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
          // Standard Super Satisfying Task Completion Chime: E5 (659Hz) -> A5 (880Hz) -> E6 (1318Hz)
          const notes = [659.25, 880.00, 1318.51];
          notes.forEach((freq, i) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();

            osc.type = i === 2 ? 'triangle' : 'sine';
            osc.frequency.setValueAtTime(freq, now + i * 0.06);

            gain.gain.setValueAtTime(0.01, now + i * 0.06);
            gain.gain.linearRampToValueAtTime(0.35, now + i * 0.06 + 0.015);
            gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.06 + 0.3);

            osc.connect(gain);
            gain.connect(ctx.destination);

            osc.start(now + i * 0.06);
            osc.stop(now + i * 0.06 + 0.32);
          });
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

  // Auto-attach eager pointerdown/click listeners to pre-unlock AudioContext & trigger haptics on task cards
  document.addEventListener('DOMContentLoaded', () => {
    const attachEagerSound = () => {
      const taskCards = document.querySelectorAll('.chk-item, [id^="chk-"], .routine-card, [data-haptic]');
      taskCards.forEach(card => {
        if (card.dataset.hapticBound) return;
        card.dataset.hapticBound = 'true';

        const trigger = () => {
          unlockAudio();
          triggerDopamineSurge('completion');
        };

        card.addEventListener('pointerdown', trigger, { passive: true });
        card.addEventListener('click', trigger, { passive: true });
      });
    };
    attachEagerSound();
    setTimeout(attachEagerSound, 1000);
    setTimeout(attachEagerSound, 3000);
  });

  const unlockAudio = () => {
    const ctx = getAudioContext();
    if (ctx && ctx.state === 'suspended') {
      ctx.resume();
    }
  };
  document.addEventListener('click', unlockAudio, { passive: true });
  document.addEventListener('touchstart', unlockAudio, { passive: true });

})();
