import type { VseWidgetInstance, VseTemplate } from "@/types/vse";
import VseSwitchCard from "./VseSwitchCard";
import VseTitleCard from "./VseTitleCard";
import VseStrompreisChart from "./VseStrompreisChart";
import VseGaugeBarometer from "./VseGaugeBarometer";
import VseSensorCard from "./VseSensorCard";
import VseMarkdownCard from "./VseMarkdownCard";
import VseDynamicWidget from "./VseDynamicWidget";
import VseCompassSpeedometer from "./VseCompassSpeedometer";

interface Props {
  instance: VseWidgetInstance;
  template: VseTemplate;
}

// Registry: maps render type -> component
// Für custom Widgets wird automatisch VseDynamicWidget verwendet
const RENDERERS: Record<string, React.ComponentType<Props>> = {
  switchCard: VseSwitchCard,
  titleCard: VseTitleCard,
  strompreisChart: VseStrompreisChart,
  gaugeBarometer: VseGaugeBarometer,
  sensorCard: VseSensorCard,
  markdownCard: VseMarkdownCard,
  compassSpeedometer: VseCompassSpeedometer,
  // Generic/dynamic renderer for custom widgets
  dynamic: VseDynamicWidget,
  generic: VseDynamicWidget,
  custom: VseDynamicWidget,
};

export default function VseRenderer({ instance, template }: Props) {
  // Try to find specific renderer, otherwise use dynamic renderer
  const Comp = RENDERERS[template.render] || VseDynamicWidget;
  
  // Apply size overrides
  const effectiveTemplate = (instance.widthOverride || instance.heightOverride)
    ? {
        ...template,
        width: instance.widthOverride ?? template.width,
        height: instance.heightOverride ?? template.height,
      }
    : template;

  return <Comp instance={instance} template={effectiveTemplate} />;
}
