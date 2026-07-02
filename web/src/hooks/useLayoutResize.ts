import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import {
  loadLayoutSettings,
  saveLayoutSettings,
  type LayoutSettings,
} from "../layoutSettings";

export type LayoutResizeAxis = "copilot-x" | "lists" | "y";

export interface LayoutResizeState {
  layoutSettings: LayoutSettings;
  setLayoutSettings: Dispatch<SetStateAction<LayoutSettings>>;
  startCopilotResize: (axis: "x" | "y") => void;
  startListsResize: () => void;
}

export function useLayoutResize(): LayoutResizeState {
  const [layoutSettings, setLayoutSettings] = useState<LayoutSettings>(() => loadLayoutSettings());
  const resizingRef = useRef(false);
  const resizingAxisRef = useRef<LayoutResizeAxis>("copilot-x");

  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!resizingRef.current) return;
      setLayoutSettings((prev) => {
        if (resizingAxisRef.current === "y") {
          const minH = 200;
          const maxH = window.innerHeight - 120;
          const next = window.innerHeight - e.clientY;
          return { ...prev, copilotHeight: Math.max(minH, Math.min(maxH, next)) };
        }
        if (resizingAxisRef.current === "lists") {
          const minW = 280;
          const maxW = Math.min(880, window.innerWidth - 480);
          const listsWidth = Math.max(minW, Math.min(maxW, e.clientX));
          return { ...prev, listsWidth };
        }
        const minW = 320;
        const maxW = Math.min(720, window.innerWidth - 400);
        const next = window.innerWidth - e.clientX;
        const copilotWidth = Math.max(minW, Math.min(maxW, next));
        return { ...prev, copilotWidth };
      });
    }

    function onUp() {
      if (!resizingRef.current) return;
      resizingRef.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      setLayoutSettings((prev) => {
        saveLayoutSettings(prev);
        return prev;
      });
    }

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  function startCopilotResize(axis: "x" | "y") {
    resizingRef.current = true;
    resizingAxisRef.current = axis === "y" ? "y" : "copilot-x";
    document.body.style.cursor = axis === "y" ? "row-resize" : "col-resize";
    document.body.style.userSelect = "none";
  }

  function startListsResize() {
    resizingRef.current = true;
    resizingAxisRef.current = "lists";
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }

  return {
    layoutSettings,
    setLayoutSettings,
    startCopilotResize,
    startListsResize,
  };
}
