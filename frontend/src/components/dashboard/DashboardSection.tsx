import type { ReactNode } from "react";

type Props = {
  title: string;

  children: ReactNode;
};

export function DashboardSection({ title, children }: Props) {
  return (
    <div className="mb-6">
      <div
        className="
          text-sm
          font-semibold
          text-slate-300
          mb-3
        "
      >
        {title}
      </div>

      {children}
    </div>
  );
}
