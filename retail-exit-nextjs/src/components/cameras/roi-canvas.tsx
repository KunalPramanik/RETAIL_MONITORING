"use client";

import React, { useRef, useEffect, useState, useCallback } from "react";

export interface NormalizedPoint {
  x: number;
  y: number;
}

export interface RoiCanvasProps {
  width?: number;
  height?: number;
  isDrawing?: boolean;
  isDrawingMode?: boolean;
  existingPolygon?: NormalizedPoint[] | null;
  onSave?: (points: NormalizedPoint[]) => void | Promise<void>;
  onPolygonComplete?: (points: NormalizedPoint[]) => void | Promise<void>;
  onCancel?: () => void;
}

export default function RoiCanvas({
  width,
  height,
  isDrawing,
  isDrawingMode,
  existingPolygon = null,
  onSave,
  onPolygonComplete,
  onCancel,
}: RoiCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [points, setPoints] = useState<NormalizedPoint[]>([]);
  const [dim, setDim] = useState({ w: width || 640, h: height || 360 });

  const activeMode = isDrawing !== undefined ? isDrawing : (isDrawingMode ?? false);
  const handleComplete = onSave || onPolygonComplete || (() => {});

  useEffect(() => {
    if (width && height) {
      setDim({ w: width, h: height });
    } else {
      const updateSize = () => {
        if (canvasRef.current) {
          setDim({
            w: canvasRef.current.clientWidth || 640,
            h: canvasRef.current.clientHeight || 360,
          });
        }
      };
      updateSize();
      window.addEventListener("resize", updateSize);
      return () => window.removeEventListener("resize", updateSize);
    }
  }, [width, height]);

  useEffect(() => {
    if (existingPolygon && existingPolygon.length > 0) {
      setPoints(existingPolygon);
    } else {
      setPoints([]);
    }
  }, [existingPolygon]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, dim.w, dim.h);

    if (points.length === 0) return;

    ctx.beginPath();
    const startX = points[0].x * dim.w;
    const startY = points[0].y * dim.h;
    ctx.moveTo(startX, startY);

    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i].x * dim.w, points[i].y * dim.h);
    }

    if (points.length >= 3 && !activeMode) {
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
      const px = p.x * dim.w;
      const py = p.y * dim.h;
      ctx.beginPath();
      ctx.arc(px, py, idx === 0 ? 6 : 4, 0, Math.PI * 2);
      ctx.fillStyle = idx === 0 ? "#10B981" : "#F59E0B";
      ctx.fill();
      ctx.strokeStyle = "#FFFFFF";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      if (activeMode) {
        ctx.fillStyle = "#FFFFFF";
        ctx.font = "10px monospace";
        ctx.fillText(`P${idx + 1}`, px + 8, py - 4);
      }
    });
  }, [points, dim.w, dim.h, activeMode]);

  useEffect(() => {
    draw();
  }, [draw]);

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!activeMode) return;
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
    if (activeMode && points.length >= 3) {
      handleComplete(points);
    }
  };

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    if (activeMode) {
      if (points.length >= 3) {
        handleComplete(points);
      } else if (onCancel) {
        onCancel();
      }
    }
  };

  return (
    <canvas
      ref={canvasRef}
      width={dim.w}
      height={dim.h}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      onContextMenu={handleContextMenu}
      className={`absolute inset-0 w-full h-full z-20 ${
        activeMode ? "cursor-crosshair pointer-events-auto" : "pointer-events-none"
      }`}
    />
  );
}

function roundCoord(num: number): number {
  return Math.round(num * 10000) / 10000;
}
