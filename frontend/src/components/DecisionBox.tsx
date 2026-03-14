type Props = {
  label: string;
  value: any;
};

function formatValue(value: any): string {
  if (value === null || value === undefined) return "—";

  if (typeof value === "boolean") {
    return value ? "TRUE" : "FALSE";
  }

  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toString() : value.toFixed(2);
  }

  if (typeof value === "string") {
    return value.toUpperCase();
  }

  return "";
}

function backgroundForValue(value: any): string {
  if (typeof value === "boolean") {
    return value ? "#14532d" : "#7f1d1d"; // green / red
  }

  if (typeof value === "number") {
    return "#1f2933"; // dark neutral
  }

  return "#374151"; // fallback
}

export function DecisionBox({ label, value }: Props) {
  const displayValue = formatValue(value);
  const bg = backgroundForValue(value);

  return (
    <div
      style={{
        width: 140,
        height: 64,
        padding: "6px 8px",
        borderRadius: 6,
        background: bg,
        color: "#ffffff",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        boxShadow: "0 0 0 1px rgba(255,255,255,0.08)",
      }}
    >
      {/* Label */}
      <div
        style={{
          fontSize: 10,
          opacity: 0.7,
          textTransform: "uppercase",
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
        }}
        title={label}
      >
        {label.replace(/_/g, " ")}
      </div>

      {/* Value */}
      <div
        style={{
          fontSize: 16,
          fontWeight: 700,
          textAlign: "center",
          letterSpacing: 0.5,
        }}
      >
        {displayValue}
      </div>
    </div>
  );
}
