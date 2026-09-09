// Industrial Sound Synthesizer using Web Audio API

let audioCtx: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (AudioContextClass) {
      audioCtx = new AudioContextClass();
    }
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

export function playAlarmSound(volume = 0.75, type: 'HIGH' | 'MEDIUM' | 'ACK' = 'HIGH') {
  try {
    const ctx = getAudioContext();
    if (!ctx) return;

    const now = ctx.currentTime;
    const gainNode = ctx.createGain();
    gainNode.connect(ctx.destination);
    gainNode.gain.setValueAtTime(volume * 0.3, now);

    if (type === 'HIGH') {
      // Urgent dual-tone siren chirp
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();

      osc1.type = 'sawtooth';
      osc2.type = 'sine';

      // 880Hz to 440Hz rapid dual beep
      osc1.frequency.setValueAtTime(880, now);
      osc1.frequency.exponentialRampToValueAtTime(440, now + 0.15);
      osc1.frequency.setValueAtTime(880, now + 0.2);
      osc1.frequency.exponentialRampToValueAtTime(440, now + 0.35);

      osc2.frequency.setValueAtTime(1200, now);
      osc2.frequency.linearRampToValueAtTime(600, now + 0.35);

      osc1.connect(gainNode);
      osc2.connect(gainNode);

      osc1.start(now);
      osc2.start(now);

      gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
      osc1.stop(now + 0.4);
      osc2.stop(now + 0.4);
    } else if (type === 'MEDIUM') {
      // Soft single attention ping (587Hz -> D5)
      const osc = ctx.createOscillator();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(587.33, now);
      osc.connect(gainNode);

      osc.start(now);
      gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.25);
      osc.stop(now + 0.25);
    } else {
      // Subtle click/ack tone
      const osc = ctx.createOscillator();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(440, now);
      osc.connect(gainNode);

      osc.start(now);
      gainNode.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
      osc.stop(now + 0.08);
    }
  } catch (err) {
    console.warn('Audio playback not permitted or unavailable:', err);
  }
}

