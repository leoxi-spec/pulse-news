// Five listening profiles. Browser speech engines expose different voices on
// macOS, Windows and Android, so each profile prefers known natural voices and
// falls back to the best English voice the device offers.
import { prefs, savePrefs } from './store.js';
import { html, raw, icons, modal, toast } from './ui.js';

export const VOICES = [
  {
    id: 'nova',
    label: 'Nova',
    tone: 'Warm and clear',
    blurb: 'A friendly newsroom read for long features.',
    rate: 1.0,
    pitch: 1.04,
    prefer: ['Samantha', 'Google US English', 'Microsoft Aria', 'Karen', 'Moira', 'Zira'],
  },
  {
    id: 'atlas',
    label: 'Atlas',
    tone: 'Deep newsreader',
    blurb: 'Lower, slower and built for headlines.',
    rate: 0.93,
    pitch: 0.84,
    prefer: ['Daniel', 'Google UK English Male', 'Microsoft Guy', 'Alex', 'Fred'],
  },
  {
    id: 'luna',
    label: 'Luna',
    tone: 'Bright and quick',
    blurb: 'A lighter voice for short briefs and quizzes.',
    rate: 1.09,
    pitch: 1.13,
    prefer: ['Google US English', 'Microsoft Zira', 'Samantha', 'Victoria'],
  },
  {
    id: 'sage',
    label: 'Sage',
    tone: 'Calm and measured',
    blurb: 'Steady pacing for study sessions.',
    rate: 0.9,
    pitch: 0.96,
    prefer: ['Google UK English Female', 'Microsoft Hazel', 'Moira', 'Tessa'],
  },
  {
    id: 'orion',
    label: 'Orion',
    tone: 'Documentary',
    blurb: 'A cinematic read for long reads and explainers.',
    rate: 0.97,
    pitch: 0.76,
    prefer: ['Google UK English Male', 'Microsoft George', 'Daniel', 'Alex'],
  },
];

const SAMPLE = 'Here is how this Pulse voice sounds reading the day’s news.';

export function currentVoiceId() {
  const stored = prefs().listen_voice;
  return VOICES.some((voice) => voice.id === stored) ? stored : 'nova';
}

export function voiceProfile(id = currentVoiceId()) {
  return VOICES.find((voice) => voice.id === id) || VOICES[0];
}

function englishVoices() {
  if (!window.speechSynthesis) return [];
  return window.speechSynthesis.getVoices().filter((voice) => (voice.lang || '').toLowerCase().startsWith('en'));
}

function pickVoice(profile, voices) {
  if (!voices.length) return null;
  for (const name of profile.prefer) {
    const match = voices.find((voice) => voice.name.toLowerCase().includes(name.toLowerCase()));
    if (match) return match;
  }
  const index = VOICES.findIndex((voice) => voice.id === profile.id);
  return voices[Math.max(0, index) % voices.length];
}

export function applyVoice(utterance, id = currentVoiceId()) {
  const profile = voiceProfile(id);
  const voice = pickVoice(profile, englishVoices());
  if (voice) {
    utterance.voice = voice;
    utterance.lang = voice.lang || 'en-US';
  } else {
    utterance.lang = 'en-US';
  }
  utterance.rate = Math.min(1.35, Math.max(0.72, profile.rate * (Number(prefs().listen_rate) || 1)));
  utterance.pitch = profile.pitch;
  utterance.volume = 1;
  return utterance;
}

export function speakSample(id) {
  if (!window.speechSynthesis || typeof SpeechSynthesisUtterance === 'undefined') return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(SAMPLE);
  applyVoice(utterance, id);
  window.speechSynthesis.speak(utterance);
}

export function openVoicePicker({ onSelect = null } = {}) {
  if (!window.speechSynthesis || typeof SpeechSynthesisUtterance === 'undefined') {
    toast('This browser cannot read stories aloud.', { type: 'bad' });
    return;
  }
  let selected = currentVoiceId();
  const body = document.createElement('div');
  const paint = () => {
    body.innerHTML = html`
      <p class="small muted" style="margin-bottom:.8rem">Five listening profiles. Pulse picks the most natural English voice installed on this device; no audio leaves your browser.</p>
      <div class="voice-grid">
        ${VOICES.map((voice) => html`
          <article class="voice-card ${voice.id === selected ? 'is-on' : ''}" data-voice="${voice.id}">
            <div class="voice-card__top">
              <div><b>${voice.label}</b><span>${voice.tone}</span></div>
              <span class="voice-card__mark" aria-hidden="true">${voice.id === selected ? 'Selected' : ''}</span>
            </div>
            <p>${voice.blurb}</p>
            <button class="btn btn--sm btn--ghost" type="button" data-sample="${voice.id}">${raw(icons.sound)} Sample</button>
          </article>`)}
      </div>
      <p class="tiny faint" style="margin-top:.7rem">Tip: install more system voices in your operating system settings for even more choice.</p>`;
    body.querySelectorAll('[data-voice]').forEach((card) => {
      card.addEventListener('click', (event) => {
        if (event.target.closest('[data-sample]')) return;
        selected = card.dataset.voice;
        paint();
      });
    });
    body.querySelectorAll('[data-sample]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.stopPropagation();
        speakSample(button.dataset.sample);
      });
    });
  };
  paint();
  modal({
    title: 'Choose a listening voice',
    wide: true,
    body,
    actions: [
      {
        label: 'Use this voice',
        class: 'btn--primary',
        onClick: async () => {
          try {
            await savePrefs({ listen_voice: selected });
            toast(`Listening voice: ${voiceProfile(selected).label}`);
            onSelect?.(selected);
          } catch (err) {
            toast(err.message, { type: 'bad' });
          }
        },
      },
    ],
  });
}
