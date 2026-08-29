import { Card, CardContent } from "@/components/ui/card";

type Props = {
  label: string;

  value: string | number;

  valueClassName?: string;
};

export function MetricCard({ label, value, valueClassName = "" }: Props) {
  return (
    <Card>
      <CardContent className="p-4">
        <div
          className="
            text-xs
            text-slate-400
            mb-1
          "
        >
          {label}
        </div>

        <div
          className={`
            text-2xl
            font-semibold
            ${valueClassName}
          `}
        >
          {value}
        </div>
      </CardContent>
    </Card>
  );
}
