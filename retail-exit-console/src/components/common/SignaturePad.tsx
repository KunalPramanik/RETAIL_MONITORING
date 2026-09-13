import React, { useRef, useState, useEffect } from 'react';
import { PenTool, Type, RotateCcw, CheckCircle2, Edit3 } from 'lucide-react';

export interface SignatureData {
  name: string;
  role: string;
  badgeId?: string;
  signedAt: string | null;
  signatureImage: string | null; // Data URL for canvas draw
  typedSignature: string;
  mode: 'draw' | 'type';
}

interface SignaturePadProps {
  title: string;
  defaultName: string;
  defaultRole: string;
  data: SignatureData;
  onChange: (data: SignatureData) => void;
}

export const SignaturePad: React.FC<SignaturePadProps> = ({
  title,
  defaultName,
  defaultRole,
  data,
  onChange,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [hasDrawn, setHasDrawn] = useState(!!data.signatureImage);

  // Initialize canvas if data has image
  useEffect(() => {
    if (data.signatureImage && canvasRef.current) {
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        const img = new Image();
        img.onload = () => {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, 0, 0);
        };
        img.src = data.signatureImage;
      }
    }
  }, [data.signatureImage]);

  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    if (data.signedAt) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const x = 'touches' in e ? e.touches[0].clientX - rect.left : e.clientX - rect.left;
    const y = 'touches' in e ? e.touches[0].clientY - rect.top : e.clientY - rect.top;

    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    const computedAmber = typeof window !== 'undefined'
      ? getComputedStyle(document.documentElement).getPropertyValue('--signal-amber').trim() || '#E8A33D'
      : '#E8A33D';
    ctx.strokeStyle = computedAmber;
    setIsDrawing(true);
  };

  const draw = (e: React.MouseEvent<HTMLCanvasElement> | React.TouchEvent<HTMLCanvasElement>) => {
    if (!isDrawing || data.signedAt) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const rect = canvas.getBoundingClientRect();
    const x = 'touches' in e ? e.touches[0].clientX - rect.left : e.clientX - rect.left;
    const y = 'touches' in e ? e.touches[0].clientY - rect.top : e.clientY - rect.top;

    ctx.lineTo(x, y);
    ctx.stroke();
    setHasDrawn(true);
  };

  const stopDrawing = () => {
    if (!isDrawing) return;
    setIsDrawing(false);
    if (canvasRef.current) {
      const dataUrl = canvasRef.current.toDataURL('image/png');
      onChange({
        ...data,
        signatureImage: dataUrl,
      });
    }
  };

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    }
    setHasDrawn(false);
    onChange({
      ...data,
      signatureImage: null,
      signedAt: null,
    });
  };

  const handleSign = () => {
    const timestamp = new Date().toLocaleString();
    let img = data.signatureImage;
    if (data.mode === 'draw' && canvasRef.current && hasDrawn) {
      img = canvasRef.current.toDataURL('image/png');
    }
    onChange({
      ...data,
      signedAt: timestamp,
      signatureImage: img,
    });
  };

  const handleUnlock = () => {
    onChange({
      ...data,
      signedAt: null,
    });
  };

  return (
    <div className="p-4 bg-canvas border border-hairline rounded-sm space-y-3 font-sans">
      <div className="flex items-center justify-between border-b border-hairline pb-2">
        <span className="text-xs-tech font-bold text-text-pri uppercase tracking-wider">
          {title}
        </span>
        {data.signedAt ? (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-teal-950/30 text-status-ok border border-status-ok/30 font-mono text-[10px] font-bold">
            <CheckCircle2 className="w-3 h-3" />
            AUTHORIZED
          </span>
        ) : (
          <div className="flex items-center gap-1 no-print">
            <button
              type="button"
              onClick={() => onChange({ ...data, mode: 'draw' })}
              className={`p-1 rounded text-xs-tech transition-colors ${
                data.mode === 'draw' ? 'bg-amber/20 text-amber' : 'text-text-sec hover:text-text-pri'
              }`}
              title="Draw signature on canvas"
            >
              <PenTool className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => onChange({ ...data, mode: 'type' })}
              className={`p-1 rounded text-xs-tech transition-colors ${
                data.mode === 'type' ? 'bg-amber/20 text-amber' : 'text-text-sec hover:text-text-pri'
              }`}
              title="Type digital signature"
            >
              <Type className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>

      {/* Signatory Details (Editable) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs-tech">
        <div>
          <label className="text-[11px] text-text-sec block mb-0.5">Signatory Full Name</label>
          <input
            type="text"
            disabled={!!data.signedAt}
            value={data.name}
            onChange={(e) => onChange({ ...data, name: e.target.value })}
            placeholder={defaultName}
            className="w-full px-2.5 py-1 bg-panel border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-amber disabled:opacity-75"
          />
        </div>
        <div>
          <label className="text-[11px] text-text-sec block mb-0.5">Title / Authorization Role</label>
          <input
            type="text"
            disabled={!!data.signedAt}
            value={data.role}
            onChange={(e) => onChange({ ...data, role: e.target.value })}
            placeholder={defaultRole}
            className="w-full px-2.5 py-1 bg-panel border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-amber disabled:opacity-75"
          />
        </div>
      </div>

      {/* Signature Area */}
      <div className="pt-1">
        <label className="text-[11px] text-text-sec block mb-1">
          {data.mode === 'draw' ? 'Draw Signature Manually (Mouse / Touch):' : 'Type Signature Preview:'}
        </label>

        {data.mode === 'draw' ? (
          <div className="relative border border-hairline rounded bg-panel overflow-hidden">
            <canvas
              ref={canvasRef}
              width={340}
              height={90}
              onMouseDown={startDrawing}
              onMouseMove={draw}
              onMouseUp={stopDrawing}
              onMouseLeave={stopDrawing}
              onTouchStart={startDrawing}
              onTouchMove={draw}
              onTouchEnd={stopDrawing}
              className={`w-full h-[90px] touch-none ${data.signedAt ? 'cursor-not-allowed opacity-90' : 'cursor-crosshair bg-panel'}`}
            />
            {!hasDrawn && !data.signedAt && (
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none text-text-sec/40 text-[11px] font-mono">
                Sign inside box with mouse or touch
              </div>
            )}
          </div>
        ) : (
          <div className="p-3 border border-hairline rounded bg-panel min-h-[90px] flex items-center justify-center">
            {data.signedAt ? (
              <span className="font-serif italic text-xl text-amber tracking-wide">
                {data.typedSignature || data.name || 'Authorized Signature'}
              </span>
            ) : (
              <input
                type="text"
                value={data.typedSignature}
                onChange={(e) => onChange({ ...data, typedSignature: e.target.value })}
                placeholder="Type your signature here..."
                className="w-full text-center bg-transparent border-b border-amber/40 py-1 text-lg font-serif italic text-amber focus:outline-none placeholder:text-text-sec/40"
              />
            )}
          </div>
        )}
      </div>

      {/* Signature Confirmation or Controls */}
      <div className="flex items-center justify-between pt-1 no-print">
        {data.signedAt ? (
          <div className="flex items-center justify-between w-full">
            <span className="text-[11px] font-mono text-status-ok flex items-center gap-1">
              ✓ Signed on {data.signedAt}
            </span>
            <button
              type="button"
              onClick={handleUnlock}
              className="inline-flex items-center gap-1 text-[11px] text-text-sec hover:text-amber transition-colors px-2 py-0.5 rounded border border-hairline bg-panel hover:bg-hairline/30"
            >
              <Edit3 className="w-3 h-3" />
              Re-sign / Clear
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-between w-full">
            {data.mode === 'draw' ? (
              <button
                type="button"
                onClick={clearCanvas}
                className="inline-flex items-center gap-1 text-[11px] text-text-sec hover:text-status-high transition-colors px-2 py-0.5 rounded border border-hairline bg-panel hover:bg-red-950/20"
              >
                <RotateCcw className="w-3 h-3" />
                Clear
              </button>
            ) : <span />}

            <button
              type="button"
              onClick={handleSign}
              disabled={data.mode === 'draw' ? !hasDrawn : !data.typedSignature && !data.name}
              className="inline-flex items-center gap-1.5 px-3 py-1 bg-amber hover:bg-amber/90 disabled:opacity-40 text-black font-semibold rounded-sm text-xs-tech transition-colors shadow-sm"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              Authorize & Sign
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

