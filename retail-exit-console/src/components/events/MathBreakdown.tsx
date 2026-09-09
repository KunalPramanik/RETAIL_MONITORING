import React from 'react';
import type { ExitEvent } from '../../types';
import { useAppData } from '../../context/AppDataContext';
import { Calculator } from 'lucide-react';

interface MathBreakdownProps {
  event: ExitEvent;
}

export const MathBreakdown: React.FC<MathBreakdownProps> = ({ event }) => {
  const { products } = useAppData();

  return (
    <div className="p-3.5 bg-panel border border-hairline rounded-sm space-y-3">
      <div className="flex items-center justify-between border-b border-hairline pb-2">
        <div className="flex items-center gap-2">
          <Calculator className="w-4 h-4 text-amber" />
          <span className="text-xs-tech font-semibold text-text-pri">
            Case-to-Unit Pack Resolution Arithmetic
          </span>
        </div>
        <span className="font-mono text-xs-tech text-text-sec">
          Resolved: {event.unitsDetected} units total
        </span>
      </div>

      <div className="space-y-2 font-mono text-xs-tech">
        {event.lineItems.map((item, idx) => {
          const product = products.find((p) => p.productId === item.productId);
          const packSize = product ? product.packSize : 1;
          const isCase = item.casesQty > 0;

          if (isCase) {
            const caseUnits = item.casesQty * packSize;
            return (
              <div key={idx} className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 p-2 bg-panel-raised rounded-sm border border-hairline/60">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="px-1.5 py-0.5 rounded bg-amber/20 text-amber font-semibold">
                    {item.casesQty} × FULL_CASE
                  </span>
                  <span className="text-text-pri">"{product?.name || 'Unknown SKU'}"</span>
                  <span className="text-text-sec">(pack_size {packSize})</span>
                </div>
                <div className="text-mono-val font-semibold">= {caseUnits} units</div>
              </div>
            );
          } else {
            return (
              <div key={idx} className="flex flex-col sm:flex-row sm:items-center justify-between gap-1 p-2 bg-panel-raised rounded-sm border border-hairline/60">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="px-1.5 py-0.5 rounded bg-hairline/60 text-text-sec font-medium">
                    + {item.unitsQty} × SINGLE_UNIT
                  </span>
                  <span className="text-text-pri">"{product?.name || 'Loose Items'}"</span>
                </div>
                <div className="text-mono-val font-semibold">= {item.unitsQty} units</div>
              </div>
            );
          }
        })}

        {/* Total Summary Row */}
        <div className="flex items-center justify-between pt-2 border-t border-hairline font-semibold">
          <span className="text-text-sec">Total Detected Sum</span>
          <span className="text-mono-val text-sm-tech font-bold">
            {event.consensusUnits} units
          </span>
        </div>

        {/* Declared vs Detected Comparison */}
        {event.declaredUnits !== undefined && (
          <div className="flex items-center justify-between p-2 rounded-sm bg-canvas border border-hairline">
            <span className="text-text-sec">
              Invoice Declared ({event.declaredUnits} units) vs Detected ({event.consensusUnits} units)
            </span>
            <span
              className={`font-mono font-bold ${
                (event.deltaUnits || 0) === 0
                  ? 'text-status-ok'
                  : (event.deltaUnits || 0) > 4
                  ? 'text-status-high'
                  : 'text-status-low'
              }`}
            >
              Δ {(event.deltaUnits || 0) > 0 ? `+${event.deltaUnits}` : event.deltaUnits || 0} units
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

