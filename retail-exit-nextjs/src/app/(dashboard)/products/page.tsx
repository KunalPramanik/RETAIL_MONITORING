"use client";

import { safeFetch } from "@/lib/api-client";
import React, { useState, useEffect } from "react";
import {
  Box,
  Plus,
  Search,
  RefreshCw,
  Trash2,
  Edit2,
  DollarSign,
  Layers,
  Package,
  Weight,
  Radio,
  AlertCircle,
  Sliders,
  History,
  Download,
  FileText,
  CheckCircle,
  X,
  TrendingUp,
  TrendingDown,
} from "lucide-react";

interface ProductItem {
  productId: string;
  skuCode: string;
  name: string;
  category: string;
  packSize: number;
  unitPrice: number;
  casePrice: number;
  reorderThreshold: number;
}

interface StockBalance {
  skuCode: string;
  currentStock: number;
  currentCases: number;
  openingStock: number;
  incomingConfirmed: number;
  outgoingConfirmed: number;
  adjustedStock: number;
  status: "IN_STOCK" | "LOW_STOCK" | "OUT_OF_STOCK";
}

interface LedgerRecord {
  ledgerId: string;
  skuCode: string;
  materialName: string;
  transactionType: string;
  direction: string;
  unitQuantity: number;
  packageQuantity: number;
  packagingType: string;
  personName: string;
  personIdentityStatus: string;
  carrierRelation: string;
  cameraId?: string;
  notes?: string;
  discrepancyReason?: string;
  timestamp: string;
}

export default function ProductsPage() {
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [stockMap, setStockMap] = useState<Record<string, StockBalance>>({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState<ProductItem | null>(null);

  // Stock Adjustment Modal State
  const [showAdjustModal, setShowAdjustModal] = useState(false);
  const [adjustTarget, setAdjustTarget] = useState<ProductItem | null>(null);
  const [adjustData, setAdjustData] = useState({
    qtyChange: 10,
    actionType: "ADD" as "ADD" | "DEDUCT",
    reason: "Cycle count receiving",
    operatorId: "SUPERVISOR_DESK",
  });
  const [adjustSubmitting, setAdjustSubmitting] = useState(false);

  // Ledger History Modal State
  const [showLedgerModal, setShowLedgerModal] = useState(false);
  const [selectedLedgerSku, setSelectedLedgerSku] = useState<string | null>(null);
  const [ledgerEntries, setLedgerEntries] = useState<LedgerRecord[]>([]);
  const [ledgerLoading, setLedgerLoading] = useState(false);

  const [formData, setFormData] = useState({
    skuCode: "",
    name: "",
    category: "Building Materials",
    customCategory: "",
    packSize: 1,
    unitPrice: 10.0,
    casePrice: 100.0,
    reorderThreshold: 10,
  });

  // Fetch Products & Real-Time Stock Balances
  const fetchData = async () => {
    try {
      setLoading(true);
      const url = search
        ? `/api/products?query=${encodeURIComponent(search)}`
        : "/api/products";
      const [prodRes, stockRes] = await Promise.all([
        safeFetch(url),
        safeFetch("/api/inventory/stock"),
      ]);

      if (prodRes.ok) {
        const prodData = await prodRes.json();
        setProducts(prodData);
      }

      if (stockRes.ok) {
        const stockData: any[] = await stockRes.json();
        const map: Record<string, StockBalance> = {};
        stockData.forEach((s) => {
          if (s.skuCode) {
            map[s.skuCode.toUpperCase()] = {
              skuCode: s.skuCode,
              currentStock: s.currentStock ?? 0,
              currentCases: s.currentCases ?? 0,
              openingStock: s.openingStock ?? 0,
              incomingConfirmed: s.incomingConfirmed ?? 0,
              outgoingConfirmed: s.outgoingConfirmed ?? 0,
              adjustedStock: s.adjustedStock ?? 0,
              status: s.status || "IN_STOCK",
            };
          }
        });
        setStockMap(map);
      }
    } catch (e) {
      console.warn("Failed to fetch products and stock:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [search]);

  // Dynamic Categories derived directly from registered database products
  const dynamicCategories = [
    "ALL",
    ...Array.from(
      new Set(
        products
          .map((p) => (p.category || "").trim().toUpperCase())
          .filter(Boolean)
      )
    ),
  ];

  // Save / Update Product
  const handleSaveProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    const resolvedCategory =
      formData.customCategory.trim() || formData.category.trim() || "GENERAL";

    const payload = {
      skuCode: formData.skuCode.trim().toUpperCase(),
      name: formData.name.trim(),
      category: resolvedCategory,
      packSize: Number(formData.packSize),
      unitPrice: Number(formData.unitPrice),
      casePrice: Number(formData.casePrice),
      reorderThreshold: Number(formData.reorderThreshold),
    };

    try {
      if (editingProduct) {
        const res = await safeFetch(`/api/products/${editingProduct.productId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const err = await res.json();
          alert(err.detail || "Update failed");
          return;
        }
      } else {
        const res = await safeFetch("/api/products", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const err = await res.json();
          alert(err.detail || "Creation failed");
          return;
        }
      }
      setShowAddModal(false);
      setEditingProduct(null);
      setFormData({
        skuCode: "",
        name: "",
        category: "Building Materials",
        customCategory: "",
        packSize: 1,
        unitPrice: 10.0,
        casePrice: 100.0,
        reorderThreshold: 10,
      });
      fetchData();
    } catch (err: any) {
      alert(err.message || "Request failed");
    }
  };

  // Delete Product
  const handleDeleteProduct = async (id: string, name: string) => {
    if (!confirm(`Are you sure you want to delete product '${name}'?`)) return;
    try {
      const res = await safeFetch(`/api/products/${id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        fetchData();
      } else {
        const err = await res.json();
        alert(err.detail || "Delete failed");
      }
    } catch (e: any) {
      alert(e.message || "Delete error");
    }
  };

  // Submit Manual Stock Adjustment
  const handleAdjustSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!adjustTarget) return;

    const delta =
      adjustData.actionType === "ADD"
        ? Math.abs(adjustData.qtyChange)
        : -Math.abs(adjustData.qtyChange);

    try {
      setAdjustSubmitting(true);
      const res = await safeFetch("/api/inventory/adjust", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sku_code: adjustTarget.skuCode,
          qty_adjustment: delta,
          operator_id: adjustData.operatorId || "SUPERVISOR",
          reason: adjustData.reason || "Manual Stock Correction",
        }),
      });

      if (res.ok) {
        setShowAdjustModal(false);
        setAdjustTarget(null);
        await fetchData();
      } else {
        const err = await res.json();
        alert(err.detail || "Adjustment failed");
      }
    } catch (err: any) {
      alert(err.message || "Error submitting adjustment");
    } finally {
      setAdjustSubmitting(false);
    }
  };

  // Fetch Movement Ledger Entries for Modal
  const openLedgerModal = async (sku?: string) => {
    setSelectedLedgerSku(sku || null);
    setShowLedgerModal(true);
    setLedgerLoading(true);
    try {
      const url = sku
        ? `/api/inventory/ledger?sku_code=${encodeURIComponent(sku)}&limit=50`
        : "/api/inventory/ledger?limit=50";
      const res = await safeFetch(url);
      if (res.ok) {
        const data = await res.json();
        setLedgerEntries(data);
      }
    } catch (err) {
      console.warn("Failed to fetch ledger entries:", err);
    } finally {
      setLedgerLoading(false);
    }
  };

  // Export Data to CSV
  const handleExportCsv = () => {
    const headers = [
      "SKU Code",
      "Product Name",
      "Category",
      "Pack Size (Units/Case)",
      "Unit Price ($)",
      "Case Price ($)",
      "Current Stock (Units)",
      "Current Stock (Cases)",
      "Reorder Threshold (Cases)",
      "Status",
    ];

    const rows = filtered.map((item) => {
      const stock = stockMap[item.skuCode.toUpperCase()];
      return [
        `"${item.skuCode}"`,
        `"${item.name.replace(/"/g, '""')}"`,
        `"${item.category}"`,
        item.packSize,
        item.unitPrice.toFixed(2),
        item.casePrice.toFixed(2),
        stock?.currentStock ?? 0,
        stock?.currentCases ?? 0,
        item.reorderThreshold,
        stock?.status || "IN_STOCK",
      ];
    });

    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `product_catalogue_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Export Data to JSON
  const handleExportJson = () => {
    const exportData = filtered.map((item) => {
      const stock = stockMap[item.skuCode.toUpperCase()];
      return {
        ...item,
        inventory: stock || {
          currentStock: 0,
          currentCases: 0,
          status: "UNKNOWN",
        },
      };
    });

    const dataStr =
      "data:text/json;charset=utf-8," +
      encodeURIComponent(JSON.stringify(exportData, null, 2));
    const link = document.createElement("a");
    link.setAttribute("href", dataStr);
    link.setAttribute("download", `product_catalogue_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const filtered = products.filter(
    (p) =>
      categoryFilter === "ALL" ||
      (p.category || "").toUpperCase() === categoryFilter.toUpperCase()
  );

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[var(--bg-panel)] p-6 rounded-xl border border-[var(--border-hairline)]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-3">
            <Box className="text-[#E8A33D]" /> Product Catalog & Inventory Stock Master
          </h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">
            Dynamic case-to-unit multiplication multipliers (<code className="text-[#B8E3D6]">pack_size</code>),
            live on-hand inventory balances, and immutable material movement ledger.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => openLedgerModal()}
            className="px-3.5 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg text-xs font-mono font-medium flex items-center gap-1.5 transition-colors"
            title="View Full Movement Ledger"
          >
            <History size={14} className="text-[#E8A33D]" /> Movement Ledger
          </button>
          <button
            onClick={handleExportCsv}
            className="px-3 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg text-xs font-mono font-medium flex items-center gap-1.5 transition-colors"
            title="Export CSV"
          >
            <Download size={13} className="text-[#38BDF8]" /> Export CSV
          </button>
          <button
            onClick={handleExportJson}
            className="px-3 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg text-xs font-mono font-medium flex items-center gap-1.5 transition-colors"
            title="Export JSON"
          >
            <FileText size={13} className="text-[#4FD1B3]" /> JSON
          </button>
          <button
            onClick={fetchData}
            disabled={loading}
            className="px-3 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg text-xs font-mono font-medium flex items-center gap-1.5 transition-colors"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} /> Refresh
          </button>
          <button
            onClick={() => {
              setEditingProduct(null);
              setFormData({
                skuCode: "",
                name: "",
                category: "Building Materials",
                customCategory: "",
                packSize: 1,
                unitPrice: 10.0,
                casePrice: 100.0,
                reorderThreshold: 10,
              });
              setShowAddModal(true);
            }}
            className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-xs font-semibold flex items-center gap-2 shadow-lg shadow-blue-900/30 transition-all"
          >
            <Plus size={15} /> Add Product
          </button>
        </div>
      </div>

      {/* Filter / Search Bar with Dynamic Category Pills */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between bg-[var(--bg-panel)] p-4 rounded-xl border border-[var(--border-hairline)]">
        <div className="relative flex-1 max-w-md">
          <Search
            size={16}
            className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by SKU code, name, or category..."
            className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg pl-10 pr-4 py-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none focus:border-[#38BDF8]"
          />
        </div>
        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
          {dynamicCategories.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors whitespace-nowrap ${
                categoryFilter.toUpperCase() === cat.toUpperCase()
                  ? "bg-[#2563EB] text-white"
                  : "bg-[var(--bg-canvas)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-hairline)]"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Products & Inventory Master Table */}
      <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl overflow-hidden shadow-xl">
        {filtered.length === 0 && !loading ? (
          <div className="p-12 text-center text-[var(--text-secondary)]">
            <Package size={40} className="mx-auto mb-3 text-[#2C323D]" />
            <h4 className="text-base font-bold text-[var(--text-primary)]">
              No products found
            </h4>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
              Add your first SKU with its pack-size multiplier to enable automated exit verification and stock tracking.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] text-xs font-mono border-b border-[var(--border-hairline)]">
                <tr>
                  <th className="p-3.5">SKU CODE</th>
                  <th className="p-3.5">PRODUCT NAME</th>
                  <th className="p-3.5">CATEGORY</th>
                  <th className="p-3.5">PACK SIZE</th>
                  <th className="p-3.5">UNIT / CASE PRICE</th>
                  <th className="p-3.5">CURRENT ON-HAND STOCK</th>
                  <th className="p-3.5">STOCK STATUS</th>
                  <th className="p-3.5 text-right">ACTIONS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                {filtered.map((item) => {
                  const stock = stockMap[item.skuCode.toUpperCase()];
                  const currentStock = stock?.currentStock ?? 0;
                  const currentCases = stock?.currentCases ?? Math.floor(currentStock / Math.max(1, item.packSize));
                  const isOutOfStock = currentStock <= 0;
                  const isLowStock = !isOutOfStock && currentCases <= item.reorderThreshold;

                  return (
                    <tr
                      key={item.productId}
                      className="hover:bg-[var(--bg-panel-raised)] transition-colors"
                    >
                      <td className="p-3.5 font-mono font-bold text-[#38BDF8]">
                        {item.skuCode}
                      </td>
                      <td className="p-3.5 font-semibold text-[var(--text-primary)]">
                        {item.name}
                      </td>
                      <td className="p-3.5">
                        <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-[var(--bg-canvas)] text-[#B8E3D6] border border-[var(--border-hairline)]">
                          {item.category}
                        </span>
                      </td>
                      <td className="p-3.5 font-mono font-bold text-[#E8A33D]">
                        {item.packSize}{" "}
                        <span className="text-xs font-normal text-[var(--text-secondary)]">
                          units/case
                        </span>
                      </td>
                      <td className="p-3.5 font-mono">
                        <div className="text-[var(--text-primary)]">
                          ${Number(item.unitPrice).toFixed(2)}/u
                        </div>
                        <div className="text-xs text-[#4FD1B3]">
                          ${Number(item.casePrice).toFixed(2)}/case
                        </div>
                      </td>
                      <td className="p-3.5 font-mono">
                        <div className="font-bold text-sm text-[var(--text-primary)]">
                          {currentStock}{" "}
                          <span className="text-xs font-normal text-[var(--text-secondary)]">
                            units
                          </span>
                        </div>
                        <div className="text-xs text-[var(--text-muted)]">
                          ({currentCases} cases)
                        </div>
                      </td>
                      <td className="p-3.5">
                        {isOutOfStock ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-950/80 text-rose-300 border border-rose-800">
                            OUT OF STOCK
                          </span>
                        ) : isLowStock ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-950/80 text-amber-300 border border-amber-800">
                            LOW STOCK ({currentCases} &le; {item.reorderThreshold})
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950/80 text-emerald-300 border border-emerald-800">
                            IN STOCK
                          </span>
                        )}
                      </td>
                      <td className="p-3.5 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Update Stock Button */}
                          <button
                            onClick={() => {
                              setAdjustTarget(item);
                              setAdjustData({
                                qtyChange: item.packSize * 5,
                                actionType: "ADD",
                                reason: "Cycle count receiving",
                                operatorId: "SUPERVISOR",
                              });
                              setShowAdjustModal(true);
                            }}
                            className="p-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[#38BDF8] rounded border border-[var(--border-hairline)] transition-colors"
                            title="Update / Adjust Stock"
                          >
                            <Sliders size={14} />
                          </button>

                          {/* Movement Ledger Button */}
                          <button
                            onClick={() => openLedgerModal(item.skuCode)}
                            className="p-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[#E8A33D] rounded border border-[var(--border-hairline)] transition-colors"
                            title="View Stock Movement History"
                          >
                            <History size={14} />
                          </button>

                          {/* Edit Button */}
                          <button
                            onClick={() => {
                              setEditingProduct(item);
                              setFormData({
                                skuCode: item.skuCode,
                                name: item.name,
                                category: item.category,
                                customCategory: "",
                                packSize: item.packSize,
                                unitPrice: item.unitPrice,
                                casePrice: item.casePrice,
                                reorderThreshold: item.reorderThreshold,
                              });
                              setShowAddModal(true);
                            }}
                            className="p-1.5 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded border border-[var(--border-hairline)] transition-colors"
                            title="Edit Product"
                          >
                            <Edit2 size={14} />
                          </button>

                          {/* Delete Button */}
                          <button
                            onClick={() => handleDeleteProduct(item.productId, item.name)}
                            className="p-1.5 bg-[var(--bg-panel-raised)] hover:bg-[#451A1A] text-[var(--text-secondary)] hover:text-[#E5484D] rounded border border-[var(--border-hairline)] transition-colors"
                            title="Delete Product"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add / Edit Product Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                <Box size={18} className="text-[#E8A33D]" />
                {editingProduct ? "Edit Product SKU" : "Register New Product SKU"}
              </h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-[var(--text-secondary)] hover:text-white"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSaveProduct} className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">
                    SKU CODE *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.skuCode}
                    onChange={(e) => setFormData({ ...formData, skuCode: e.target.value })}
                    placeholder="e.g. MAT-CEM-50KG"
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none focus:border-[#38BDF8]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">
                    CATEGORY
                  </label>
                  <select
                    value={formData.category}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none"
                  >
                    {dynamicCategories
                      .filter((c) => c !== "ALL")
                      .map((cat) => (
                        <option key={cat} value={cat}>
                          {cat}
                        </option>
                      ))}
                    <option value="CUSTOM">+ Custom Category...</option>
                  </select>
                </div>
              </div>

              {formData.category === "CUSTOM" && (
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">
                    CUSTOM CATEGORY NAME
                  </label>
                  <input
                    type="text"
                    value={formData.customCategory}
                    onChange={(e) => setFormData({ ...formData, customCategory: e.target.value })}
                    placeholder="e.g. Building Materials, Hazardous, Logistics"
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none focus:border-[#38BDF8]"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">
                  PRODUCT NAME *
                </label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. Cement Bag (50kg)"
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">
                    PACK SIZE (UNITS) *
                  </label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={formData.packSize}
                    onChange={(e) =>
                      setFormData({ ...formData, packSize: parseInt(e.target.value) || 1 })
                    }
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[#E8A33D] font-mono font-bold outline-none"
                  />
                  <span className="text-[10px] text-[var(--text-secondary)]">
                    Units per sealed case
                  </span>
                </div>
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">
                    UNIT PRICE ($)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={formData.unitPrice}
                    onChange={(e) =>
                      setFormData({ ...formData, unitPrice: parseFloat(e.target.value) || 0 })
                    }
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">
                    CASE PRICE ($)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={formData.casePrice}
                    onChange={(e) =>
                      setFormData({ ...formData, casePrice: parseFloat(e.target.value) || 0 })
                    }
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[#4FD1B3] font-mono outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">
                  REORDER THRESHOLD (CASES)
                </label>
                <input
                  type="number"
                  value={formData.reorderThreshold}
                  onChange={(e) =>
                    setFormData({ ...formData, reorderThreshold: parseInt(e.target.value) || 0 })
                  }
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-sm font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold shadow-lg shadow-blue-900/30"
                >
                  {editingProduct ? "Save Changes" : "Create Product"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Update Stock / Manual Adjustment Modal */}
      {showAdjustModal && adjustTarget && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                <Sliders size={18} className="text-[#38BDF8]" />
                Update Stock: {adjustTarget.skuCode}
              </h3>
              <button
                onClick={() => setShowAdjustModal(false)}
                className="text-[var(--text-secondary)] hover:text-white"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleAdjustSubmit} className="space-y-4 text-sm">
              <div className="p-3 bg-[var(--bg-canvas)] rounded-lg border border-[var(--border-hairline)] text-xs font-mono space-y-1">
                <div className="text-[var(--text-secondary)]">PRODUCT NAME:</div>
                <div className="font-bold text-[var(--text-primary)]">{adjustTarget.name}</div>
                <div className="text-[var(--text-secondary)] pt-1">
                  CURRENT ON-HAND:{" "}
                  <span className="text-[#4FD1B3] font-bold">
                    {stockMap[adjustTarget.skuCode.toUpperCase()]?.currentStock ?? 0} units
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">
                    ACTION TYPE
                  </label>
                  <select
                    value={adjustData.actionType}
                    onChange={(e) =>
                      setAdjustData({
                        ...adjustData,
                        actionType: e.target.value as "ADD" | "DEDUCT",
                      })
                    }
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none"
                  >
                    <option value="ADD">+ Add Stock (Inbound)</option>
                    <option value="DEDUCT">- Deduct Stock (Outbound / Damage)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">
                    QUANTITY (UNITS) *
                  </label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={adjustData.qtyChange}
                    onChange={(e) =>
                      setAdjustData({
                        ...adjustData,
                        qtyChange: Math.max(1, parseInt(e.target.value) || 1),
                      })
                    }
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono font-bold outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">
                  REASON / AUDIT NOTE *
                </label>
                <select
                  value={adjustData.reason}
                  onChange={(e) => setAdjustData({ ...adjustData, reason: e.target.value })}
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none mb-2"
                >
                  <option value="Cycle count receiving">Cycle count receiving</option>
                  <option value="Physical count discrepancy correction">Physical count discrepancy correction</option>
                  <option value="Damaged or defective stock quarantine">Damaged or defective stock quarantine</option>
                  <option value="Direct supplier inbound receipt">Direct supplier inbound receipt</option>
                  <option value="Internal warehouse stock transfer">Internal warehouse stock transfer</option>
                </select>
                <input
                  type="text"
                  placeholder="Or enter custom reason note..."
                  value={adjustData.reason}
                  onChange={(e) => setAdjustData({ ...adjustData, reason: e.target.value })}
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2 text-xs text-[var(--text-primary)] outline-none"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border-hairline)]">
                <button
                  type="button"
                  onClick={() => setShowAdjustModal(false)}
                  className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-sm font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={adjustSubmitting}
                  className="px-5 py-2 bg-[#10B981] hover:bg-[#059669] text-white rounded-lg text-sm font-semibold shadow-lg shadow-emerald-900/30 flex items-center gap-2"
                >
                  {adjustSubmitting ? (
                    <RefreshCw size={14} className="animate-spin" />
                  ) : (
                    <CheckCircle size={14} />
                  )}
                  Confirm Stock Update
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Movement Ledger Modal */}
      {showLedgerModal && (
        <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-2xl max-w-4xl w-full max-h-[85vh] flex flex-col p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--border-hairline)] pb-3">
              <div className="flex items-center gap-2 font-mono text-base font-bold text-[var(--text-primary)]">
                <History size={20} className="text-[#E8A33D]" />
                <span>
                  Material Movement & Stock Ledger{" "}
                  {selectedLedgerSku ? `— ${selectedLedgerSku}` : "— All Materials"}
                </span>
              </div>
              <button
                onClick={() => setShowLedgerModal(false)}
                className="p-1 text-[var(--text-secondary)] hover:text-white rounded"
              >
                <X size={18} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {ledgerLoading ? (
                <div className="py-12 text-center text-xs font-mono text-[var(--text-secondary)] flex flex-col items-center gap-2">
                  <RefreshCw size={24} className="animate-spin text-[#38BDF8]" />
                  <span>Loading ledger records from database...</span>
                </div>
              ) : ledgerEntries.length === 0 ? (
                <div className="py-12 text-center text-xs font-mono text-[var(--text-secondary)]">
                  No movement ledger entries recorded yet.
                </div>
              ) : (
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] border-b border-[var(--border-hairline)]">
                    <tr>
                      <th className="p-2.5">TIMESTAMP</th>
                      <th className="p-2.5">SKU / ITEM</th>
                      <th className="p-2.5">TX TYPE</th>
                      <th className="p-2.5">DIR</th>
                      <th className="p-2.5">DELTA UNITS</th>
                      <th className="p-2.5">PERSON / ATTRIBUTION</th>
                      <th className="p-2.5">REASON / NOTES</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                    {ledgerEntries.map((l) => (
                      <tr
                        key={l.ledgerId}
                        className="hover:bg-[var(--bg-panel-raised)] transition-colors"
                      >
                        <td className="p-2.5 text-[var(--text-secondary)] whitespace-nowrap">
                          {l.timestamp ? new Date(l.timestamp).toLocaleString() : "-"}
                        </td>
                        <td className="p-2.5">
                          <span className="font-bold text-[#38BDF8]">{l.skuCode}</span>
                          <div className="text-[10px] text-[var(--text-secondary)] truncate max-w-xs">
                            {l.materialName}
                          </div>
                        </td>
                        <td className="p-2.5">
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-[var(--bg-canvas)] border border-[var(--border-hairline)] text-[var(--text-primary)]">
                            {l.transactionType}
                          </span>
                        </td>
                        <td className="p-2.5">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              l.direction === "EXIT" || l.transactionType === "OUT"
                                ? "bg-rose-950 text-rose-300 border border-rose-800"
                                : "bg-emerald-950 text-emerald-300 border border-emerald-800"
                            }`}
                          >
                            {l.direction || l.transactionType}
                          </span>
                        </td>
                        <td className="p-2.5 font-bold">
                          {l.transactionType === "OUT" || l.direction === "EXIT" ? (
                            <span className="text-rose-400">-{l.unitQuantity}</span>
                          ) : (
                            <span className="text-emerald-400">+{l.unitQuantity}</span>
                          )}
                        </td>
                        <td className="p-2.5 text-[var(--text-secondary)]">
                          {l.personName || "SYSTEM"}
                        </td>
                        <td className="p-2.5 text-[var(--text-muted)] truncate max-w-xs">
                          {l.discrepancyReason || l.notes || "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="flex justify-end pt-3 border-t border-[var(--border-hairline)]">
              <button
                onClick={() => setShowLedgerModal(false)}
                className="px-4 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] rounded-lg text-xs font-semibold"
              >
                Close Ledger
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
