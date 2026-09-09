import React, { useEffect, useState } from 'react';
import QRCode from 'qrcode';

interface QrCodeSvgProps {
  value: string;
  size?: number;
  className?: string;
  darkColor?: string;
  lightColor?: string;
}

export const QrCodeSvg: React.FC<QrCodeSvgProps> = ({
  value,
  size = 200,
  className = '',
  darkColor = '#000000',
  lightColor = '#ffffff',
}) => {
  const [svgContent, setSvgContent] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!value) {
      setSvgContent('');
      return;
    }

    QRCode.toString(value, {
      type: 'svg',
      margin: 1,
      width: size,
      color: {
        dark: darkColor,
        light: lightColor,
      },
    })
      .then((svg) => {
        setSvgContent(svg);
        setError(null);
      })
      .catch((err) => {
        console.error('Error generating QR code:', err);
        setError('Failed to generate QR code');
      });
  }, [value, size, darkColor, lightColor]);

  if (error) {
    return (
      <div
        style={{ width: size, height: size }}
        className={`flex items-center justify-center bg-panel-raised border border-status-alarm/40 text-status-alarm text-xs-tech font-mono p-2 text-center rounded ${className}`}
      >
        {error}
      </div>
    );
  }

  if (!svgContent) {
    return (
      <div
        style={{ width: size, height: size }}
        className={`flex items-center justify-center bg-panel-raised border border-hairline text-text-sec text-xs-tech font-mono rounded ${className}`}
      >
        Generating QR...
      </div>
    );
  }

  return (
    <div
      className={`inline-block overflow-hidden rounded ${className}`}
      style={{ width: size, height: size }}
      dangerouslySetInnerHTML={{ __html: svgContent }}
    />
  );
};

