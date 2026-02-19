import { createSignal, onMount, onCleanup } from 'solid-js';

export function useViewport() {
  const [height, setHeight] = createSignal(window.innerHeight);
  const [isKeyboardOpen, setIsKeyboardOpen] = createSignal(false);

  const handleResize = () => {
    const visualHeight = window.visualViewport?.height || window.innerHeight;
    document.documentElement.style.setProperty('--app-height', `${visualHeight}px`);
    setHeight(visualHeight);

    const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
    setIsKeyboardOpen(isMobile && visualHeight < window.screen.height * 0.75);
  };

  onMount(() => {
    handleResize();
    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', handleResize);
      window.visualViewport.addEventListener('scroll', handleResize);
    } else {
      window.addEventListener('resize', handleResize);
    }
  });

  onCleanup(() => {
    if (window.visualViewport) {
      window.visualViewport.removeEventListener('resize', handleResize);
      window.visualViewport.removeEventListener('scroll', handleResize);
    } else {
      window.removeEventListener('resize', handleResize);
    }
  });

  return { height, isKeyboardOpen };
}
