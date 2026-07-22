// src/components/ToolCallChip.tsx
// Tool çağrısını göstergesi — küçük renkli pill badge

import type { ToolCall } from "../types";
import { CATEGORY_COLORS, CATEGORY_ICONS } from "../types";

interface Props {
  toolCall: ToolCall;
}

export function ToolCallChip({ toolCall }: Props) {
  const color = CATEGORY_COLORS[toolCall.category] ?? "var(--text-dim)";
  const icon  = CATEGORY_ICONS[toolCall.category] ?? "🔧";

  return (
    <div
      className="tool-chip"
      style={{
        color,
        borderColor: `${color}40`,
        background: `${color}12`,
      }}
      title={`Kategori: ${toolCall.category}${toolCall.duration_ms != null ? ` • ${toolCall.duration_ms}ms` : ""}`}
    >
      <span>{icon}</span>
      <span>{toolCall.tool_name}</span>
      {toolCall.duration_ms != null && (
        <span style={{ opacity: 0.6, fontSize: 10 }}>{toolCall.duration_ms}ms</span>
      )}
    </div>
  );
}
