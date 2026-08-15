import { ref } from 'vue';
import type { PetAction } from '../api/pet';

export function usePetController() {
  const menuOpen = ref(false);
  const bubbleText = ref('');
  const forcedAction = ref<PetAction | null>(null);
  let bubbleTimer = 0;

  function showBubble(text: string, ms = 2400) {
    bubbleText.value = text;
    window.clearTimeout(bubbleTimer);
    bubbleTimer = window.setTimeout(() => {
      bubbleText.value = '';
    }, ms);
  }

  function triggerAction(action: PetAction) {
    forcedAction.value = { ...action };
    window.setTimeout(() => {
      forcedAction.value = null;
    }, 1200);
  }

  return { menuOpen, bubbleText, forcedAction, showBubble, triggerAction };
}
