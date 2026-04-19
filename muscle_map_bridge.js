/**
 * muscle_map_bridge.js (Elite Version)
 * Uses native Gradio JS parameters for 100% stable data transmission
 * bypassing fragile DOM text manipulation.
 */
(function () {
  let isProcessing = false;

  function findElementDeep(selector, root = document) {
      let found = root.querySelector(selector);
      if (found) return found;
      const allElements = root.querySelectorAll('*');
      for (let el of allElements) {
          if (el.shadowRoot) {
              found = findElementDeep(selector, el.shadowRoot);
              if (found) return found;
          }
      }
      return null;
  }

  window.addEventListener("message", function (ev) {
      const d = ev.data;
      if (!d || d.type !== "mm-muscle" || !d.muscle) return;

      if (isProcessing) return;
      isProcessing = true;
      setTimeout(() => { isProcessing = false; }, 1000);

      // 1. Securely store the exact clicked muscle
      window._mm_target_muscle = String(d.muscle);
      console.log("Muscle targeted:", window._mm_target_muscle);

      // 2. Safely trigger the hidden bridge button
      function tryClick(attemptsLeft) {
          const btnHost = document.querySelector("#hidden_trigger_btn");
          if (!btnHost) {
              if (attemptsLeft > 0) setTimeout(() => tryClick(attemptsLeft - 1), 150);
              return;
          }

          const btn = findElementDeep("button", btnHost) || btnHost;
          if (btn) {
              btn.click();
          } else if (attemptsLeft > 0) {
              setTimeout(() => tryClick(attemptsLeft - 1), 150);
          }
      }
      tryClick(5);
  });
})();