import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef } from "react";

import { usePromptInputController } from "@/components/ai-elements/prompt-input";
import { useI18n } from "@/core/i18n/hooks";

/**
 * Hook to determine if the chat is in a specific mode based on URL parameters, and to set an initial prompt input value accordingly.
 */
export function useSpecificChatMode() {
  const { t } = useI18n();
  const { thread_id: threadIdFromPath } = useParams<{ thread_id: string }>();
  const searchParams = useSearchParams();
  const promptInputController = usePromptInputController();
  const inputInitialValue = useMemo(() => {
    if (threadIdFromPath !== "new") {
      return undefined;
    }
    if (searchParams.get("mode") === "skill") {
      return t.inputBox.createSkillPrompt;
    }
    // skill mode takes precedence over ?prompt= (designed so skill selectors
    // never lose the synthetic prompt text from a stray URL param).
    return searchParams.get("prompt") ?? undefined;
  }, [threadIdFromPath, searchParams, t.inputBox.createSkillPrompt]);
  const lastInitialValueRef = useRef<string | undefined>(undefined);
  const setInputRef = useRef(promptInputController.textInput.setInput);
  setInputRef.current = promptInputController.textInput.setInput;
  useEffect(() => {
    if (
      inputInitialValue &&
      inputInitialValue !== lastInitialValueRef.current
    ) {
      lastInitialValueRef.current = inputInitialValue;
      setTimeout(() => {
        setInputRef.current(inputInitialValue);
        const textarea = document.querySelector("textarea");
        if (textarea) {
          textarea.focus();
          textarea.selectionStart = textarea.value.length;
          textarea.selectionEnd = textarea.value.length;
        }
      }, 100);
    } else if (!inputInitialValue) {
      // Allow a later navigation to the same URL (e.g. back/forward within
      // the same route, where the component does not remount) to prefill
      // again instead of being swallowed by the dedup ref above.
      lastInitialValueRef.current = undefined;
    }
  }, [inputInitialValue]);
}
