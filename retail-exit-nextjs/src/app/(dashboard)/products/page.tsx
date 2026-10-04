"use client";

import { safeFetch } from "@/lib/api-client";
﻿import React, { useState, useEffect } from "react";
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

export default function ProductsPage() {
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState<ProductItem | null>(null);

  const [formData, setFormData] = useState({
    skuCode: "",
    name: "",
    category: "BEVERAGES",
    packSize: 24,
    unitPrice: 1.5,
    casePrice: 32.0,
    reorderThreshold: 50,
  });

  const fetchProducts = async () => {
    try {
      setLoading(true);
      const url = search
        ? `/api/products?query=${encodeURIComponent(search)}`
        : "/api/products";
      const res = await safeFetch(url);
      if (res.ok) {
        const data = await res.json();
        setProducts(data);
      }
    } catch (e) {
      console.warn("Failed to fetch products:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts();
  }, [search]);

  const handleSaveProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingProduct) {
        const res = await safeFetch(`/api/products/${editingProduct.productId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(formData),
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
          body: JSON.stringify(formData),
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
        category: "BEVERAGES",
        packSize: 24,
        unitPrice: 1.5,
        casePrice: 32.0,
        reorderThreshold: 50,
      });
      fetchProducts();
    } catch (err: any) {
      alert(err.message || "Request failed");
    }
  };

  const handleDeleteProduct = async (id: string, name: string) => {
    if (!confirm(`Are you sure you want to delete product '${name}'?`)) return;
    try {
      const res = await safeFetch(`/api/products/${id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        fetchProducts();
      } else {
        const err = await res.json();
        alert(err.detail || "Delete failed");
      }
    } catch (e: any) {
      alert(e.message || "Delete error");
    }
  };

  const filtered = products.filter(
    (p) => categoryFilter === "ALL" || p.category.toUpperCase() === categoryFilter.toUpperCase()
  );

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-[var(--bg-panel)] p-6 rounded-xl border border-[var(--border-hairline)]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--text-primary)] flex items-center gap-3">
            <Box className="text-[#E8A33D]" /> Product & Pack-Math Master Catalogue
          </h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">
            Dynamic case-to-unit multiplication multipliers (<code className="text-[#B8E3D6]">pack_size</code>), SKU
            mappings, and inventory reorder levels.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchProducts}
            className="px-3.5 py-2 bg-[var(--bg-panel-raised)] hover:bg-[var(--bg-panel-hover)] text-[var(--text-primary)] border border-[var(--border-hairline)] rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
          >
            <RefreshCw size={15} /> Refresh
          </button>
          <button
            onClick={() => {
              setEditingProduct(null);
              setFormData({
                skuCode: "",
                name: "",
                category: "BEVERAGES",
                packSize: 24,
                unitPrice: 1.5,
                casePrice: 32.0,
                reorderThreshold: 50,
              });
              setShowAddModal(true);
            }}
            className="px-4 py-2 bg-[#2563EB] hover:bg-[#1D4ED8] text-white rounded-lg text-sm font-semibold flex items-center gap-2 shadow-lg shadow-blue-900/30 transition-all"
          >
            <Plus size={16} /> Add Product
          </button>
        </div>
      </div>

      {/* Filter / Search Bar */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between bg-[var(--bg-panel)] p-4 rounded-xl border border-[var(--border-hairline)]">
        <div className="relative flex-1 max-w-md">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by SKU code, product name, or category..."
            className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg pl-10 pr-4 py-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none focus:border-[#38BDF8]"
          />
        </div>
        <div className="flex items-center gap-2">
          {["ALL", "BEVERAGES", "SNACKS", "HOUSEHOLD", "INDUSTRIAL"].map((cat) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors ${
                categoryFilter === cat
                  ? "bg-[#2563EB] text-white"
                  : "bg-[var(--bg-canvas)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-hairline)]"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Products Table */}
      <div className="bg-[var(--bg-panel)] border border-[var(--border-hairline)] rounded-xl overflow-hidden shadow-xl">
        {filtered.length === 0 && !loading ? (
          <div className="p-12 text-center text-[var(--text-secondary)]">
            <Package size={40} className="mx-auto mb-3 text-[#2C323D]" />
            <h4 className="text-base font-bold text-[var(--text-primary)]">No products registered</h4>
            <p className="text-xs text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
              Add your first SKU with its pack-size multiplier to enable automated exit verification.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--bg-canvas)] text-[var(--text-secondary)] text-xs font-mono border-b border-[var(--border-hairline)]">
                <tr>
                  <th className="p-4">SKU CODE</th>
                  <th className="p-4">PRODUCT NAME</th>
                  <th className="p-4">CATEGORY</th>
                  <th className="p-4">PACK SIZE (UNITS/CASE)</th>
                  <th className="p-4">UNIT PRICE</th>
                  <th className="p-4">CASE PRICE</th>
                  <th className="p-4">REORDER LEVEL</th>
                  <th className="p-4 text-right">ACTIONS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-hairline)] text-[var(--text-primary)]">
                {filtered.map((item) => (
                  <tr key={item.productId} className="hover:bg-[var(--bg-panel-raised)] transition-colors">
                    <td className="p-4 font-mono font-bold text-[#38BDF8]">{item.skuCode}</td>
                    <td className="p-4 font-semibold text-[var(--text-primary)]">{item.name}</td>
                    <td className="p-4">
                      <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-[var(--bg-canvas)] text-[#B8E3D6] border border-[var(--border-hairline)]">
                        {item.category}
                      </span>
                    </td>
                    <td className="p-4 font-mono font-bold text-[#E8A33D]">
                      {item.packSize} <span className="text-xs font-normal text-[var(--text-secondary)]">units/case</span>
                    </td>
                    <td className="p-4 font-mono text-[var(--text-primary)]">${Number(item.unitPrice).toFixed(2)}</td>
                    <td className="p-4 font-mono text-[#4FD1B3]">${Number(item.casePrice).toFixed(2)}</td>
                    <td className="p-4 font-mono text-[var(--text-secondary)]">{item.reorderThreshold} cases</td>
                    <td className="p-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => {
                            setEditingProduct(item);
                            setFormData({
                              skuCode: item.skuCode,
                              name: item.name,
                              category: item.category,
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
                ))}
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
              <button onClick={() => setShowAddModal(false)} className="text-[var(--text-secondary)] hover:text-white">
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveProduct} className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">SKU CODE *</label>
                  <input
                    type="text"
                    required
                    value={formData.skuCode}
                    onChange={(e) => setFormData({ ...formData, skuCode: e.target.value })}
                    placeholder="e.g. BEV-WAT-500ML"
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none focus:border-[#38BDF8]"
                  />
                </div>
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">CATEGORY</label>
                  <select
                    value={formData.category}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none"
                  >
                    <option value="BEVERAGES">Beverages</option>
                    <option value="SNACKS">Snacks & Dry Goods</option>
                    <option value="HOUSEHOLD">Household Goods</option>
                    <option value="ELECTRONICS">Electronics</option>
                    <option value="INDUSTRIAL">Industrial Materials</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">PRODUCT NAME *</label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. Natural Spring Water 500ml"
                  className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">PACK SIZE (UNITS) *</label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={formData.packSize}
                    onChange={(e) => setFormData({ ...formData, packSize: parseInt(e.target.value) || 1 })}
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[#E8A33D] font-mono font-bold outline-none"
                  />
                  <span className="text-[10px] text-[var(--text-secondary)]">Units per sealed case</span>
                </div>
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">UNIT PRICE ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={formData.unitPrice}
                    onChange={(e) => setFormData({ ...formData, unitPrice: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[var(--text-primary)] font-mono outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">CASE PRICE ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    required
                    value={formData.casePrice}
                    onChange={(e) => setFormData({ ...formData, casePrice: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-[var(--bg-canvas)] border border-[var(--border-hairline)] rounded-lg p-2.5 text-[#4FD1B3] font-mono outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono text-[var(--text-secondary)] mb-1">REORDER THRESHOLD (CASES)</label>
                <input
                  type="number"
                  value={formData.reorderThreshold}
                  onChange={(e) => setFormData({ ...formData, reorderThreshold: parseInt(e.target.value) || 0 })}
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
    </div>
  );
}
