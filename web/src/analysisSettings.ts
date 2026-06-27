/** @deprecated Use modeSettings.ts — kept for import compatibility. */
export {
  BUILTIN_MASTER_IDS,
  chatBodyField,
  loadModeSettings as loadAnalysisSettings,
  saveModeSettings as saveAnalysisSettings,
  type CustomMaster,
  type ModeSettings as AnalysisUserSettings,
  type ReadingMode,
} from "./modeSettings";

import { chatBodyField } from "./modeSettings";

/** @deprecated alias */
export const analysisBodyField = chatBodyField;
