import { FOUR_DIM_LINE_OUTLINE } from "./fourDimOutlineData";
import { circledIndex, LineNumberedDoc, type LineDocRow } from "./lineNumberedDoc";

interface FourDimLineOutlineProps {
  onSelectLine?: (text: string) => void;
}

/** Empty-state outline matching Lazyweb Line Numbers mockup copy/layout. */
export function FourDimLineOutline({ onSelectLine }: FourDimLineOutlineProps) {
  const rows: LineDocRow[] = [];
  FOUR_DIM_LINE_OUTLINE.forEach((section, index) => {
    if (index > 0) rows.push({ kind: "spacer" });
    rows.push({
      kind: "section",
      text: `${circledIndex(index)} ${section.title}`,
    });
    for (const line of section.lines) {
      rows.push({
        kind: "text",
        text: line,
        onClick: onSelectLine ? () => onSelectLine(line) : undefined,
      });
    }
  });

  return <LineNumberedDoc className="four-dim-line-outline" rows={rows} />;
}
