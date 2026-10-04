"use client";

import React, { useRef, useEffect, useState } from "react";

export default function RoiCanvas({
  width,
  height,
  isDrawingMode,
  onPolygonComplete,
}: {
  width: number;
  height: number;
  isDrawingMode: boolean;
  onPolygonComplete: (points: { x: number; y: number }[]) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [points, setPoints] = useState<{ x: number; y: number }[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);

    if (points.length > 0) {
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i].x, points[i].y);
      }
      
      if (points.length > 2 && !isDrawingMode) {
        ctx.closePath();
        ctx.fillStyle = "rgba(239, 68, 68, 0.2)"; // Red tint
        ctx.fill();
        ctx.strokeStyle = "rgb(239, 68, 68)"; // Red border
      } else {
        ctx.strokeStyle = "rgb(59, 130, 246)"; // Blue while drawing
      }
      
      ctx.lineWidth = 2;
      ctx.stroke();

      // Draw points
      points.forEach((p) => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = "white";
        ctx.fill();
        ctx.stroke();
      });
    }
  }, [points, width, height, isDrawingMode]);

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawingMode) return;
    
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;

    const newPoints = [...points, { x, y }];
    setPoints(newPoints);

    // Auto-close polygon on 4th point for standard exit lanes
    if (newPoints.length === 4) {
      onPolygonComplete(newPoints);
    }
  };

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    if (isDrawingMode && points.length > 2) {
      onPolygonComplete(points);
    }
  };

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      onClick={handleCanvasClick}
      onContextMenu={handleContextMenu}
      className={`absolute top-0 left-0 w-full h-full z-20 ${isDrawingMode ? 'cursor-crosshair' : 'cursor-default'}`}
    />
  );
}
