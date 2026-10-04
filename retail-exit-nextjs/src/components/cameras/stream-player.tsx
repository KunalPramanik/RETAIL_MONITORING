"use client";

import React, { useState } from "react";
import RoiCanvas from "./roi-canvas";
import { Maximize2, PenTool, Trash2, Crosshair } from "lucide-react";

export default function StreamPlayer({ cameraId, streamUrl }: { cameraId: string, streamUrl: string }) {
  const [isDrawingMode, setIsDrawingMode] = useState(false);
  const [polygon, setPolygon] = useState<{ x: number; y: number }[] | null>(null);

  // Mock detections for HUD demonstration
  const mockDetections = [
    { id: 104, label: "Person (Shopper)", conf: 92, x: 120, y: 150, w: 100, h: 250, color: "border-blue-500", bg: "bg-blue-500" },
    { id: 105, label: "Backpack / Bag", conf: 88, x: 130, y: 220, w: 60, h: 80, color: "border-yellow-500", bg: "bg-yellow-500" },
    { id: 106, label: "Display / Screen (2D)", conf: 96, x: 400, y: 100, w: 150, h: 100, color: "border-red-500", bg: "bg-red-500" }
  ];

  return (
    <div className="flex flex-col bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-xl">
      {/* Stream Header */}
      <div className="px-4 py-3 border-b border-gray-800 flex justify-between items-center bg-gray-950">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse"></div>
          <h3 className="font-bold text-gray-100 font-mono">{cameraId}</h3>
          <span className="text-xs px-2 py-0.5 bg-gray-800 text-gray-400 rounded">H.265 / 30fps</span>
        </div>
        <div className="flex gap-2">
          {polygon ? (
             <button 
                onClick={() => { setPolygon(null); setIsDrawingMode(false); }}
                className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-gray-800 rounded transition-colors"
                title="Clear Tripwire"
             >
               <Trash2 size={16} />
             </button>
          ) : (
            <button 
              onClick={() => setIsDrawingMode(!isDrawingMode)}
              className={`p-1.5 rounded transition-colors flex items-center gap-2 text-xs font-bold ${isDrawingMode ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-blue-400 hover:bg-gray-800'}`}
            >
              <PenTool size={16} /> {isDrawingMode ? "Drawing..." : "Draw Tripwire"}
            </button>
          )}
          <button className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded transition-colors">
            <Maximize2 size={16} />
          </button>
        </div>
      </div>

      {/* Stream Container */}
      <div className="relative aspect-video bg-black w-full overflow-hidden">
        {/* Fallback pattern / stream feed */}
        <div className="absolute inset-0 opacity-20" 
             style={{ backgroundImage: 'radial-gradient(circle at center, #333 1px, transparent 1px)', backgroundSize: '20px 20px' }}>
        </div>
        
        <div className="absolute inset-0 flex items-center justify-center text-gray-600 font-mono text-sm">
          Awaiting WebRTC / HLS Stream Data...
        </div>

        {/* HUD Detections Overlay */}
        {!isDrawingMode && mockDetections.map((det) => (
          <div 
            key={det.id}
            className={`absolute border-2 ${det.color} bg-transparent z-10 transition-all duration-300`}
            style={{ left: `${det.x}px`, top: `${det.y}px`, width: `${det.w}px`, height: `${det.h}px` }}
          >
            <div className={`absolute -top-6 left-[-2px] ${det.bg} text-white text-[10px] font-bold px-1.5 py-0.5 whitespace-nowrap rounded-t-sm flex gap-2`}>
              <span>{det.label}</span>
              <span>{det.conf}%</span>
              <span>#{det.id}</span>
            </div>
            {/* Center crosshair for tracking */}
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-white/50">
               <Crosshair size={12} />
            </div>
          </div>
        ))}

        {/* Interactive Tripwire Canvas */}
        <RoiCanvas 
          width={800} 
          height={450} 
          isDrawingMode={isDrawingMode} 
          onPolygonComplete={(pts) => {
            setPolygon(pts);
            setIsDrawingMode(false);
          }} 
        />
      </div>
    </div>
  );
}
