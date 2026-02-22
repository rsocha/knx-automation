import type { VseWidgetInstance, VseTemplate } from "@/types/vse";

interface Props {
  instance: VseWidgetInstance;
  template: VseTemplate;
}

export default function VseTitleCard({ instance }: Props) {
  return (
    <div
      className="w-full rounded-t-[18px] px-3 py-2.5"
      style={{
        background: "rgba(0,0,0,0.18)",
        border: "1px solid rgba(255,255,255,0.06)",
        backdropFilter: "blur(10px)",
      }}
    >
      <div className="text-sm font-semibold text-foreground">{instance.label}</div>
      {instance.variableValues?.subtitle && (
        <div className="text-[10px] text-muted-foreground mt-0.5">
          {instance.variableValues.subtitle}
        </div>
      )}
    </div>
  );
}
