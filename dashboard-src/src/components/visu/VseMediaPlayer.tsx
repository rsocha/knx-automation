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
  
  // Status: 1=Play, 2=Stop, 3=Pause
  const statusValue = Number(getKoValue("ko5") || 0);
  const isPlaying = statusValue === 1;
  const isStopped = statusValue === 2;
  const isPaused = statusValue === 3 || statusValue === 0;
  
  const volume = Number(getKoValue("ko6") || 50);
  const position = Number(getKoValue("ko7") || 0);
  const duration = Number(getKoValue("ko8") || 0);
  const isMuted = getKoValue("ko19") === "1" || getKoValue("ko19") === 1;

  const displayAlbum = radioStation || album;

  const textColor = lightText ? "rgba(255,255,255,0.95)" : "rgba(0,0,0,0.9)";
  const subTextColor = lightText ? "rgba(255,255,255,0.6)" : "rgba(0,0,0,0.6)";

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const handlePlayPause = () => {
    if (isPlaying) {
      // Currently playing -> send Pause
      const pauseAddr = instance.koBindings["ko14"];
      if (pauseAddr) sendCommand({ address: pauseAddr, value: 1 });
    } else {
      // Currently paused/stopped -> send Play
      const playAddr = instance.koBindings["ko9"];
      if (playAddr) sendCommand({ address: playAddr, value: 1 });
    }
  };

  const handleStop = () => {
    const addr = instance.koBindings["ko15"];
    if (addr) sendCommand({ address: addr, value: 1 });
  };

  const handlePrev = () => {
    const addr = instance.koBindings["ko11"];
    if (addr) sendCommand({ address: addr, value: 1 });
  };

  const handleNext = () => {
    const addr = instance.koBindings["ko10"];
    if (addr) sendCommand({ address: addr, value: 1 });
  };

  const handleRewind = () => {
    const addr = instance.koBindings["ko17"];
    if (addr) sendCommand({ address: addr, value: 1 });
  };

  const handleForward = () => {
    const addr = instance.koBindings["ko16"];
    if (addr) sendCommand({ address: addr, value: 1 });
  };

  const handleMute = () => {
    const addr = instance.koBindings["ko18"];
    if (addr) sendCommand({ address: addr, value: isMuted ? 0 : 1 });
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
        padding: 16,
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
          marginBottom: 12,
          background: `linear-gradient(135deg, rgba(${accentColor},0.3) 0%, rgba(${accentColor},0.1) 100%)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {coverUrl ? (
          <img src={coverUrl} alt="Cover" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <MdiIcon name="music" size={60} color={`rgba(${accentColor},0.5)`} />
        )}
      </div>

      {/* Title & Artist */}
      <div style={{ textAlign: "center", marginBottom: 8 }}>
        <div style={{ color: textColor, fontSize: 16, fontWeight: 600, lineHeight: 1.3, marginBottom: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {title}
        </div>
        <div style={{ color: subTextColor, fontSize: 13, lineHeight: 1.3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {artist}
        </div>
        {displayAlbum && (
          <div style={{ color: `rgba(${accentColor},0.8)`, fontSize: 11, marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {displayAlbum}
          </div>
        )}
      </div>

      {/* Progress */}
      {duration > 0 && (
        <div style={{ marginBottom: 10 }}>
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
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}>
            <span style={{ color: subTextColor, fontSize: 9 }}>{formatTime(position)}</span>
            <span style={{ color: subTextColor, fontSize: 9 }}>{formatTime(duration)}</span>
          </div>
        </div>
      )}

      {/* Main Controls */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, marginBottom: 8 }}>
        {/* Rewind */}
        <button onClick={handleRewind} style={{ background: "none", border: "none", cursor: "pointer", padding: 4 }}>
          <MdiIcon name="rewind-30" size={20} color={subTextColor} />
        </button>
        
        {/* Previous */}
        <button onClick={handlePrev} style={{ background: "none", border: "none", cursor: "pointer", padding: 4 }}>
          <MdiIcon name="skip-previous" size={24} color={textColor} />
        </button>
        
        {/* Play/Pause */}
        <button
          onClick={handlePlayPause}
          style={{
            background: `rgba(${accentColor},0.9)`,
            border: "none",
            borderRadius: "50%",
            width: 48,
            height: 48,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <MdiIcon name={isPlaying ? "pause" : "play"} size={28} color="#fff" />
        </button>
        
        {/* Next */}
        <button onClick={handleNext} style={{ background: "none", border: "none", cursor: "pointer", padding: 4 }}>
          <MdiIcon name="skip-next" size={24} color={textColor} />
        </button>
        
        {/* Forward */}
        <button onClick={handleForward} style={{ background: "none", border: "none", cursor: "pointer", padding: 4 }}>
          <MdiIcon name="fast-forward-30" size={20} color={subTextColor} />
        </button>
      </div>

      {/* Volume Row */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {/* Mute Button */}
        <button 
          onClick={handleMute} 
          style={{ background: "none", border: "none", cursor: "pointer", padding: 4 }}
        >
          <MdiIcon name={isMuted ? "volume-off" : "volume-low"} size={18} color={isMuted ? `rgb(${accentColor})` : subTextColor} />
        </button>
        
        {/* Volume Slider */}
        <Slider
          value={[isMuted ? 0 : volume]}
          min={0}
          max={100}
          step={1}
          onValueChange={handleVolumeChange}
          className="flex-1"
        />
        
        <MdiIcon name="volume-high" size={18} color={subTextColor} />
        <span style={{ color: subTextColor, fontSize: 11, width: 28, textAlign: "right" }}>{volume}%</span>
      </div>
    </div>
  );
}
