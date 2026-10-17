import React from 'react';
import { MetricPoint } from '../types';
import { getNextExpectedReadingPkt } from '../utils/time';

interface MetricChartProps {
  data: MetricPoint[];
  metricKey: 'cpu_pct' | 'ram_pct' | 'disk_pct';
  label: string;
  colorHex?: string;
  unit?: string;
  lastReadingTime?: string | null;
}

export const MetricChart: React.FC<MetricChartProps> = ({
  data,
  metricKey,
  label,
  colorHex = '#06b6d4',
  unit = '%',
  lastReadingTime
}) => {
  const nextReadingTime = getNextExpectedReadingPkt(lastReadingTime);

  if (!data || data.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between h-52">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{label}</span>
          <span className="text-[10px] text-slate-500 font-mono">15m interval</span>
        </div>
        <div className="flex flex-col items-center justify-center text-center space-y-1 py-6">
          <div className="text-sm font-bold text-slate-300">No data yet</div>
          <div className="text-xs text-slate-500">
            Next expected reading at <strong className="text-cyan-400 font-mono">{nextReadingTime}</strong>
          </div>
        </div>
        <div className="text-[10px] text-slate-600 font-mono">
          Telemetry sampled every 15 min
        </div>
      </div>
    );
  }

  const values = data.map(d => (d[metricKey] != null ? Number(d[metricKey]) : 0));
  const maxVal = Math.max(100, ...values);
  const minVal = 0;

  const width = 600;
  const height = 160;
  const padding = 28;

  const points = data.map((d, i) => {
    const x = padding + (i / Math.max(1, data.length - 1)) * (width - padding * 2);
    const val = d[metricKey] != null ? Number(d[metricKey]) : 0;
    const y = height - padding - ((val - minVal) / (maxVal - minVal)) * (height - padding * 2);
    return `${x},${y}`;
  });

  const pathD = points.length > 0 ? `M ${points.join(' L ')}` : '';
  const areaD = points.length > 0
    ? `M ${points[0]} L ${points.join(' L ')} L ${width - padding},${height - padding} L ${padding},${height - padding} Z`
    : '';

  const latestVal = values[values.length - 1] ?? 0;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{label}</span>
          <div className="flex items-baseline gap-1.5 mt-0.5">
            <span className="text-xl font-black text-white">{latestVal}</span>
            <span className="text-xs text-slate-400 font-medium">{unit} current</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-[11px] text-slate-400 bg-slate-950 px-2 py-1 rounded border border-slate-800">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: colorHex }}></span>
          {data.length} reading point{data.length > 1 ? 's' : ''} (15m apart)
        </div>
      </div>

      <div className="relative w-full overflow-hidden">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-36 overflow-visible select-none"
        >
          <defs>
            <linearGradient id={`grad-${metricKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={colorHex} stopOpacity="0.35" />
              <stop offset="100%" stopColor={colorHex} stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line x1={padding} y1={padding} x2={width - padding} y2={padding} stroke="#334155" strokeDasharray="3 3" opacity="0.6" />
          <line x1={padding} y1={height / 2} x2={width - padding} y2={height / 2} stroke="#334155" strokeDasharray="3 3" opacity="0.6" />
          <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#475569" opacity="0.8" />

          {/* Value markers */}
          <text x={padding - 6} y={padding + 4} fill="#64748b" fontSize="9" textAnchor="end">100{unit}</text>
          <text x={padding - 6} y={height / 2 + 3} fill="#64748b" fontSize="9" textAnchor="end">50{unit}</text>
          <text x={padding - 6} y={height - padding + 3} fill="#64748b" fontSize="9" textAnchor="end">0{unit}</text>

          {/* Filled Area */}
          {areaD && <path d={areaD} fill={`url(#grad-${metricKey})`} />}

          {/* Stroke Line */}
          {pathD && (
            <path
              d={pathD}
              fill="none"
              stroke={colorHex}
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Data Dots with reading points */}
          {data.map((d, i) => {
            const val = d[metricKey] != null ? Number(d[metricKey]) : 0;
            const x = padding + (i / Math.max(1, data.length - 1)) * (width - padding * 2);
            const y = height - padding - ((val - minVal) / (maxVal - minVal)) * (height - padding * 2);
            return (
              <circle
                key={i}
                cx={x}
                cy={y}
                r={i === data.length - 1 ? 4.5 : 3}
                fill={i === data.length - 1 ? '#ffffff' : colorHex}
                stroke={colorHex}
                strokeWidth={i === data.length - 1 ? 2.5 : 1}
              >
                <title>{`${d.time_label || d.ts}: ${val}${unit}`}</title>
              </circle>
            );
          })}
        </svg>
      </div>

      <div className="flex items-center justify-between text-[10px] text-slate-500 font-mono px-1">
        <span>{data[0]?.time_label || 'Start'}</span>
        <span>Next expected: {nextReadingTime}</span>
        <span>{data[data.length - 1]?.time_label || 'Now'}</span>
      </div>
    </div>
  );
};
