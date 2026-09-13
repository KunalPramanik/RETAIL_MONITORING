import React, { useState } from 'react';
import type { StaticImageRecord } from '../../types';
import {
  RefreshCw,
  Image as ImageIcon,
  CheckCircle2,
  Filter,
} from 'lucide-react';

interface StaticImageLogTableProps {
  records: StaticImageRecord[];
  onRefresh?: () => void;
  isLoading?: boolean;
}

export const StaticImageLogTable: React.FC<StaticImageLogTableProps> = ({
  records,
  onRefresh,
  isLoading = false,
}) => {
  const [filterClass, setFilterClass] = useState<string>('ALL');

  const filtered = records.filter((r) => {
    if (filterClass === 'ALL') return true;
    return r.classification === filterClass;
  });

  const getClassificationBadge = (classification: string) => {
    switch (classification) {
      case 'RELIGIOUS_IMAGE':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber/20 text-amber border border-amber/40">
            RELIGIOUS IMAGE
          </span>
        );
      case 'PERSON_PHOTO':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-600">
            PERSON PHOTO
          </span>
        );
      case 'POSTER_OR_SIGNAGE':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-950/40 text-blue-400 border border-blue-600/40">
            POSTER / SIGNAGE
          </span>
        );
      case 'SCREEN_DISPLAY':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-950/40 text-purple-400 border border-purple-600/40">
            SCREEN DISPLAY
          </span>
        );
      case 'UNCLASSIFIED_STATIC':
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-zinc-800 text-zinc-400 border border-zinc-700">
            UNCLASSIFIED STATIC
          </span>
        );
    }
  };

  return (
    <div className="space-y-3">
      {/* Table Subheader / Filter bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs-tech">
        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-text-sec" />
          <span className="text-text-sec font-mono text-[11px]">FILTER CLASSIFICATION:</span>
          <select
            value={filterClass}
            onChange={(e) => setFilterClass(e.target.value)}
            className="px-2 py-1 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
          >
            <option value="ALL">All Static Classifications ({records.length})</option>
            <option value="RELIGIOUS_IMAGE">Religious Images</option>
            <option value="PERSON_PHOTO">Person Photos / Portraits</option>
            <option value="POSTER_OR_SIGNAGE">Posters / Signage</option>
            <option value="SCREEN_DISPLAY">Screen Displays</option>
            <option value="UNCLASSIFIED_STATIC">Unclassified</option>
          </select>
        </div>

        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-panel hover:bg-panel-raised border border-hairline text-text-sec hover:text-text-pri transition-colors font-mono text-[11px]"
          >
            <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin text-amber' : ''}`} />
            Refresh Audit Log
          </button>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-sm border border-hairline bg-canvas">
        <table className="w-full text-left font-mono text-xs-tech border-collapse">
          <thead>
            <tr className="border-b border-hairline bg-panel-raised text-text-sec text-[11px]">
              <th className="p-2.5 font-normal">Timestamp (UTC)</th>
              <th className="p-2.5 font-normal">Camera / Portal</th>
              <th className="p-2.5 font-normal">Classification</th>
              <th className="p-2.5 font-normal text-right">Confidence</th>
              <th className="p-2.5 font-normal text-right">Liveness Score</th>
              <th className="p-2.5 font-normal">Bounding Box [x, y, w, h]</th>
              <th className="p-2.5 font-normal text-right">False Alarm Prevention</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length > 0 ? (
              filtered.map((row) => (
                <tr
                  key={row.detectionId}
                  className="border-b border-hairline/60 hover:bg-panel/40 transition-colors"
                >
                  <td className="p-2.5 text-text-sec whitespace-nowrap">
                    {new Date(row.frameTs).toLocaleTimeString()} ·{' '}
                    <span className="text-[10px] text-text-sec/80">
                      {new Date(row.frameTs).toLocaleDateString()}
                    </span>
                  </td>
                  <td className="p-2.5 font-sans font-medium text-text-pri whitespace-nowrap">
                    {row.cameraLabel}
                  </td>
                  <td className="p-2.5 whitespace-nowrap font-sans">
                    {getClassificationBadge(row.classification)}
                  </td>
                  <td className="p-2.5 text-right font-bold text-mono-val whitespace-nowrap">
                    {(row.classificationConfidence * 100).toFixed(1)}%
                  </td>
                  <td className="p-2.5 text-right font-bold text-text-sec whitespace-nowrap">
                    {row.livenessScore.toFixed(3)}
                  </td>
                  <td className="p-2.5 text-text-sec font-mono text-[11px] whitespace-nowrap">
                    [{row.bbox.join(', ')}]
                  </td>
                  <td className="p-2.5 text-right whitespace-nowrap font-sans">
                    {row.suppressedAlert ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-status-ok bg-teal-950/20 px-2 py-0.5 rounded border border-status-ok/30">
                        <CheckCircle2 className="w-3 h-3 text-status-ok" />
                        Alert Prevented
                      </span>
                    ) : (
                      <span className="text-text-sec text-[11px]">—</span>
                    )}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={7} className="py-10 text-center text-text-sec font-sans">
                  <div className="flex flex-col items-center justify-center space-y-1">
                    <ImageIcon className="w-7 h-7 text-text-sec/40 mb-1" />
                    <p className="font-semibold text-text-pri text-xs-tech">
                      No static images logged yet
                    </p>
                    <p className="text-[11px] text-text-sec max-w-sm">
                      When wall portraits, religious images, posters, or digital displays enter camera
                      view, the liveness engine classifies and logs them here.
                    </p>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

