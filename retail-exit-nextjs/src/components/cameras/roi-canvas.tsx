"use client";

import React, { useRef, useEffect, useState, useCallback } from "react";

export interface NormalizedPoint {
  x: number;
  y: number;
}

interface RoiCanvasProps {
  width: number;
  height: number;
  isDrawingMode: boolean;
  existingPolygon?: NormalizedPoint[] | null;
  onPolygonComplete: (points: NormalizedPoint[]) => void;
  onCancel?: () => void;
}

export default function RoiCanvas({
  width,
  height,
  isDrawingMode,
  existingPolygon = null,
  onPolygonComplete,
  onCancel,
}: RoiCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [points, setPoints] = useState<NormalizedPoint[]>([]);

  useEffect(() => {
    if (existingPolygon && existingPolygon.length > 0) {
      setPoints(existingPolygon);
    }
  }, [existingPolygon]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);

    if (points.length === 0) return;

    ctx.beginPath();
    const startX = points[0].x * width;
    const startY = points[0].y * height;
    ctx.moveTo(startX, startY);

    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i].x * width, points[i].y * height);
    }

    if (points.length >= 3 && !isDrawingMode) {
      ctx.closePath();
      ctx.fillStyle = "rgba(59, 130, 246, 0.15)";
      ctx.fill();
      ctx.strokeStyle = "rgba(59, 130, 246, 0.9)";
      ctx.lineWidth = 2;
    } else {
      ctx.strokeStyle = "rgba(245, 158, 11, 0.9)";
      ctx.lineWidth = 2;
    }

    ctx.setLineDash([4, 4]);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw vertex handles
    points.forEach((p, idx) => {
      const px = p.x * width;
      const py = p.y * height;
      ctx.beginPath();
      ctx.arc(px, py, idx === 0 ? 6 : 4, 0, Math.PI * 2);
      ctx.fillStyle = idx === 0 ? "#10B981" : "#F59E0B";
      ctx.fill();
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      if (isDrawingMode) {
        ctx.fillStyle = "#FFFFFF";
        ctx.font = "10px monospace";
        ctx.fillText(`P${idx + 1}`, px + 8, py - 4);
      }
    });
  }, [points, width, height, isDrawingMode]);

  useEffect(() => {
    draw();
  }, [draw]);

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawingMode) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;

    const normX = Math.max(0, Math.min(1, clientX / rect.width));
    const normY = Math.max(0, Math.min(1, clientY / rect.height));

    const nextPoints = [...points, { x: roundCoord(normX), y: roundCoord(normY) }];
    setPoints(nextPoints);
  };

  const handleDoubleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    if (isDrawingMode && points.length >= 3) {
      onPolygonComplete(points);
    }
  };

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    if (isDrawingMode) {
      if (points.length >= 3) {
        onPolygonComplete(points);
      } else if (onCancel) {
        onCancel();
      }
    }
  };

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      onContextMenu={handleContextMenu}
      className={`absolute inset-0 w-full h-full z-20 ${
        isDrawingMode ? "cursor-crosshair pointer-events-auto" : "pointer-events-none"
      }`}
    />
  );
}

function roundCoord(num: number): number {
  return Math.round(num * 10000) / 10000;
}
