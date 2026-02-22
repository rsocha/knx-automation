import { useGroupAddresses, useSendKnxCommand } from "@/hooks/useKnx";
import type { VseWidgetInstance, VseTemplate } from "@/types/vse";
import MdiIcon from "./MdiIcon";
import { Slider } from "@/components/ui/slider";

interface Props {
  instance: VseWidgetInstance;
  template: VseTemplate;
}

export default function VseMediaPlayer({ instance, template }: Props) {
  const { data: addresses } = useGroupAddresses();
  const { mutate: sendCommand } = useSendKnxCommand();

  const vars: Record<string, any> = {
    ...Object.fromEntries(Object.entries(template.variables).map(([k, v]) => [k, v.default])),
    ...instance.variableValues,
  };

  // Parse variables
  const testTitle = vars.var1 || "Awesome Title";
  const testArtist = vars.var2 || "Famous Artist";
  const testAlbum = vars.var3 || "Well known album";
  const accentColor = vars.var4 || "180,140,100";
  const bgColor = vars.var5 || "30,28,26";
  const bgOpacity = Number(vars.var6) || 95;
  const borderColor = vars.var7 || "255,255,255";
  const borderOpacity = Number(vars.var8) || 8;
  const borderWidth = Number(vars.var12) || 1.5;
  const lightText = vars.var9 === "1" || vars.var9 === true;
  const borderRadius = Number(vars.var10) || 24;
  const coverRadius = Number(vars.var11) || 16;

  // Get KO values
  const getKoValue = (koKey: string) => {
    const addr = instance.koBindings[koKey];
    if (!addr) return null;
    const ga = addresses?.find((a) => a.address === addr);
    return ga?.value;
  };

  const title = getKoValue("ko1") || testTitle;
  const artist = getKoValue("ko2") || testArtist;
  const album = getKoValue("ko3") || testAlbum;
  const radioStation = getKoValue("ko13");
  const coverUrl = getKoValue("ko4") || "";
  const isPlaying = getKoValue("ko5") === "1" || getKoValue("ko5") === 1 || getKoValue("ko5") === true;
  const volume = Number(getKoValue("ko6") || 50);
  const position = Number(getKoValue("ko7") || 0);
  const duration = Number(getKoValue("ko8") || 0);

  const displayAlbum = radioStation || album;

  const textColor = lightText ? "rgba(255,255,255,0.95)" : "rgba(0,0,0,0.9)";
  const subTextColor = lightText ? "rgba(255,255,255,0.6)" : "rgba(0,0,0,0.6)";

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const handlePlayPause = () => {
    const addr = instance.koBindings["ko9"];
    if (addr) sendCommand({ address: addr, value: isPlaying ? 0 : 1 });
  };

  const handlePrev = () => {
    const addr = instance.koBindings["ko11"];
    if (addr) sendCommand({ address: addr, value: 1 });
  };

  const handleNext = () => {
    const addr = instance.koBindings["ko10"];
    if (addr) sendCommand({ address: addr, value: 1 });
  };

  const handleVolumeChange = (val: number[]) => {
    const addr = instance.koBindings["ko12"];
    if (addr) sendCommand({ address: addr, value: val[0] });
  };

  return (
    <div
      style={{
        width: template.width,
        height: template.height,
        borderRadius,
        border: `${borderWidth}px solid rgba(${borderColor}, ${borderOpacity / 100})`,
        background: `rgba(${bgColor}, ${bgOpacity / 100})`,
        display: "flex",
        flexDirection: "column",
        padding: 20,
        boxSizing: "border-box",
        overflow: "hidden",
      }}
    >
      {/* Cover Art */}
      <div
        style={{
          width: "100%",
          aspectRatio: "1",
          borderRadius: coverRadius,
          overflow: "hidden",
          marginBottom: 16,
          background: `linear-gradient(135deg, rgba(${accentColor},0.3) 0%, rgba(${accentColor},0.1) 100%)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {coverUrl ? (
          <img src={coverUrl} alt="Cover" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <MdiIcon name="music" size={80} color={`rgba(${accentColor},0.5)`} />
        )}
      </div>

      {/* Title & Artist */}
      <div style={{ textAlign: "center", marginBottom: 12 }}>
        <div style={{ color: textColor, fontSize: 18, fontWeight: 600, lineHeight: 1.3, marginBottom: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {title}
        </div>
        <div style={{ color: subTextColor, fontSize: 14, lineHeight: 1.3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {artist}
        </div>
        {displayAlbum && (
          <div style={{ color: `rgba(${accentColor},0.8)`, fontSize: 12, marginTop: 4, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {displayAlbum}
          </div>
        )}
      </div>

      {/* Progress */}
      {duration > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ height: 4, borderRadius: 2, background: `rgba(${accentColor},0.2)`, overflow: "hidden" }}>
            <div
              style={{
                height: "100%",
                width: `${(position / duration) * 100}%`,
                background: `rgb(${accentColor})`,
                borderRadius: 2,
              }}
            />
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
            <span style={{ color: subTextColor, fontSize: 10 }}>{formatTime(position)}</span>
            <span style={{ color: subTextColor, fontSize: 10 }}>{formatTime(duration)}</span>
          </div>
        </div>
      )}

      {/* Controls */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 24, marginBottom: 16 }}>
        <button onClick={handlePrev} style={{ background: "none", border: "none", cursor: "pointer", padding: 8 }}>
          <MdiIcon name="skip-previous" size={28} color={textColor} />
        </button>
        <button
          onClick={handlePlayPause}
          style={{
            background: `rgba(${accentColor},0.9)`,
            border: "none",
            borderRadius: "50%",
            width: 56,
            height: 56,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <MdiIcon name={isPlaying ? "pause" : "play"} size={32} color="#fff" />
        </button>
        <button onClick={handleNext} style={{ background: "none", border: "none", cursor: "pointer", padding: 8 }}>
          <MdiIcon name="skip-next" size={28} color={textColor} />
        </button>
      </div>

      {/* Volume */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <MdiIcon name="volume-low" size={18} color={subTextColor} />
        <Slider
          value={[volume]}
          min={0}
          max={100}
          step={1}
          onValueChange={handleVolumeChange}
          className="flex-1"
        />
        <MdiIcon name="volume-high" size={18} color={subTextColor} />
        <span style={{ color: subTextColor, fontSize: 12, width: 32, textAlign: "right" }}>{volume}%</span>
      </div>
    </div>
  );
}
