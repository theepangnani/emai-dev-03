import type { DemoType } from '../../api/demo';
import { DEFAULT_QUESTIONS } from './demoSamples';
import {
  IconAsk,
  IconStudyGuide,
  IconFlashTutor,
} from './icons';
import type { GatedActionId } from './GatedActionBar';

export type StreamStatus = 'idle' | 'streaming' | 'done' | 'error';

export interface TabState {
  output: string;
  status: StreamStatus;
  question: string;
  error: string;
}

export const TAB_META: Record<DemoType, { label: string; sub: string; Icon: typeof IconAsk }> = {
  ask: { label: 'Ask', sub: 'Get an answer', Icon: IconAsk },
  study_guide: { label: 'Study Guide', sub: 'Key points + Q&A', Icon: IconStudyGuide },
  flash_tutor: { label: 'Flash Tutor', sub: '5 flashcards', Icon: IconFlashTutor },
};

export const GATED_ACTIONS: Record<DemoType, GatedActionId[]> = {
  ask: ['save', 'follow_up'],
  // #3787 — the Study Guide tab now renders its own suggestion chips
  // (`DemoStudyGuideChips`) in place of the generic gated action bar.
  study_guide: [],
  flash_tutor: ['download', 'save', 'more_flashcards'],
};

export const INITIAL_TAB_STATE: Record<DemoType, TabState> = {
  ask: { output: '', status: 'idle', question: DEFAULT_QUESTIONS.ask, error: '' },
  study_guide: { output: '', status: 'idle', question: DEFAULT_QUESTIONS.study_guide, error: '' },
  flash_tutor: { output: '', status: 'idle', question: DEFAULT_QUESTIONS.flash_tutor, error: '' },
};

export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // fall through
  }
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'absolute';
    ta.style.left = '-9999px';
    ta.style.top = '0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}
