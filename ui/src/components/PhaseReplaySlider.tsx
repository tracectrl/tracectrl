import { formatDuration } from '../api/sessions'

interface PhaseReplaySliderProps {
  traceStartNs: number
  traceDurationNs: number
  currentNs: number
  onChange: (ns: number) => void
  onClear: () => void
}

export default function PhaseReplaySlider({ traceStartNs, traceDurationNs, currentNs, onChange, onClear }: PhaseReplaySliderProps) {
  if (traceDurationNs <= 0) return null

  const sliderValue = Math.round(((currentNs - traceStartNs) / traceDurationNs) * 1000)

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(e.target.value, 10)
    const ns = traceStartNs + (value / 1000) * traceDurationNs
    onChange(ns)
  }

  return (
    <div className="replay-slider-bar">
      <span className="replay-slider-label">Replay</span>
      <input
        type="range"
        className="replay-slider-input"
        min={0}
        max={1000}
        value={sliderValue}
        onChange={handleChange}
        aria-label="Replay timeline position"
      />
      <span className="replay-slider-time">{formatDuration(currentNs - traceStartNs)}</span>
      <button className="btn btn-ghost btn-sm" onClick={onClear}>Reset</button>
    </div>
  )
}
