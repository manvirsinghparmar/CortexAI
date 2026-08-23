import { useCallback, useEffect, useRef } from "react";
import { createCortexAnalysis } from "../api/cortexAnalysis";
import { useChatStore } from "../store/chatStore";

const FAILURE_MESSAGE =
  "Cortex couldn't combine these answers. Your model responses are safe above.";

export function useCortexAnalysis() {
  const activeController = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      activeController.current?.abort();
      activeController.current = null;
    },
    [],
  );

  const run = useCallback(async (turnId: string) => {
    const state = useChatStore.getState();
    const turn = state.turns.find((item) => item.id === turnId);
    if (!turn?.requestGroupId || turn.analysisStatus === "processing") return;

    activeController.current?.abort();
    const controller = new AbortController();
    activeController.current = controller;
    state.setTurnAnalysisStatus(turnId, "processing");

    try {
      const analysis = await createCortexAnalysis(turn.requestGroupId, controller.signal);
      if (controller.signal.aborted) return;
      useChatStore.getState().addTurnAnalysisRun(turnId, analysis);
    } catch (error) {
      if (controller.signal.aborted) return;
      console.warn("Cortex Analysis failed", error);
      useChatStore.getState().setTurnAnalysisStatus(turnId, "failed", FAILURE_MESSAGE);
    } finally {
      if (activeController.current === controller) {
        activeController.current = null;
      }
    }
  }, []);

  return { run };
}
