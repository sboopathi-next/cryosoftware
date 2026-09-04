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
    if (audioCtx && audioCtx.state === 'suspended') {
      audioCtx.resume();
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
        // Standard satisfying dopamine tap
        navigator.vibrate([35, 45, 55]);
      }
    } catch (e) {
      console.log('[Haptic Warning]', e);
    }
  }

  /**
   * Synthesizes rich 8-bit / sci-fi level-up chime sound effects via Web Audio API.
   * @param {string} type - 'completion' | 'milestone' | 'levelup' | 'sync' | 'error'
   */
  function playDopamineSound(type = 'completion') {
    try {
      const ctx = getAudioContext();
      if (!ctx) return;

      const now = ctx.currentTime;

      if (type === 'milestone' || type === 'levelup') {
        // Major Arpeggio Level Up Surge: C5 (523.25Hz) -> E5 (659.25Hz) -> G5 (783.99Hz) -> C6 (1046.50Hz) -> E6 (1318.51Hz)
        const notes = [523.25, 659.25, 783.99, 1046.50, 1318.51];
        notes.forEach((freq, i) => {
          const osc = ctx.createOscillator();
          const gain = ctx.createGain();

          osc.type = 'triangle';
          osc.frequency.setValueAtTime(freq, now + i * 0.065);

          gain.gain.setValueAtTime(0.01, now + i * 0.065);
          gain.gain.exponentialRampToValueAtTime(0.25, now + i * 0.065 + 0.02);
          gain.gain.exponentialRampToValueAtTime(0.001, now + i * 0.065 + 0.35);

          osc.connect(gain);
          gain.connect(ctx.destination);

          osc.start(now + i * 0.065);
          osc.stop(now + i * 0.065 + 0.38);
        });
      } else if (type === 'sync' || type === 'leetcode') {
        // Digital Sci-Fi Chime Sweep: 440Hz -> 880Hz -> 1760Hz
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.exponentialRampToValueAtTime(880, now + 0.08);
        osc.frequency.exponentialRampToValueAtTime(1760, now + 0.18);

        gain.gain.setValueAtTime(0.2, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.32);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start(now);
        osc.stop(now + 0.32);
      } else {
        // Standard Satisfying Task Completion Chime: D5 (587.33Hz) -> A5 (880.00Hz) -> D6 (1174.66Hz)
        const osc1 = ctx.createOscillator();
        const osc2 = ctx.createOscillator();
        const gain = ctx.createGain();

        osc1.type = 'sine';
        osc2.type = 'triangle';

        osc1.frequency.setValueAtTime(587.33, now);
        osc1.frequency.exponentialRampToValueAtTime(880.00, now + 0.07);

        osc2.frequency.setValueAtTime(1174.66, now + 0.07);

        gain.gain.setValueAtTime(0.01, now);
        gain.gain.linearRampToValueAtTime(0.22, now + 0.03);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.28);

        osc1.connect(gain);
        osc2.connect(gain);
        gain.connect(ctx.destination);

        osc1.start(now);
        osc2.start(now + 0.07);
        osc1.stop(now + 0.28);
        osc2.stop(now + 0.28);
      }
    } catch (e) {
      console.warn('[Dopamine Sound Warning]', e);
    }
  }

  /**
   * Combined Master Dopamine Trigger (Audio Chime + Tactile Mobile Vibration Shake).
   * @param {string} type - 'completion' | 'milestone' | 'levelup' | 'sync' | 'error'
   */
  function triggerDopamineSurge(type = 'completion') {
    playDopamineSound(type);
    triggerHapticShake(type);
  }

  // Export functions to global window context
  window.playDopamineSound = playDopamineSound;
  window.triggerHapticShake = triggerHapticShake;
  window.triggerDopamineSurge = triggerDopamineSurge;

  // Global listener to unlock Web Audio context on user gesture
  const unlockAudio = () => {
    getAudioContext();
    document.removeEventListener('click', unlockAudio);
    document.removeEventListener('touchstart', unlockAudio);
  };
  document.addEventListener('click', unlockAudio, { once: true });
  document.addEventListener('touchstart', unlockAudio, { once: true });

})();
