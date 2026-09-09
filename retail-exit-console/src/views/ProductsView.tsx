import React, { useState } from 'react';
import { useAppData } from '../context/AppDataContext';
import type { Product } from '../types';
import { Modal } from '../components/common/Modal';
import { Boxes, Plus, Edit2, Trash2, Search, PackageCheck, AlertCircle } from 'lucide-react';

export const ProductsView: React.FC = () => {
  const { products, addProduct, updateProduct, deleteProduct } = useAppData();
  const [searchQuery, setSearchQuery] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);

  // Form State
  const [formData, setFormData] = useState<Omit<Product, 'productId'>>({
    skuCode: '',
    name: '',
    category: 'Beverages',
    packSize: 24,
    unitPrice: 1.5,
    casePrice: 32.0,
    reorderThreshold: 50,
  });

  const openAddModal = () => {
    setEditingProduct(null);
    setFormData({
      skuCode: `SKU-${Math.floor(100 + Math.random() * 900)}`,
      name: '',
      category: 'Beverages',
      packSize: 24,
      unitPrice: 1.5,
      casePrice: 30.0,
      reorderThreshold: 50,
    });
    setIsModalOpen(true);
  };

  const openEditModal = (p: Product) => {
    setEditingProduct(p);
    setFormData({
      skuCode: p.skuCode,
      name: p.name,
      category: p.category,
      packSize: p.packSize,
      unitPrice: p.unitPrice,
      casePrice: p.casePrice,
      reorderThreshold: p.reorderThreshold,
    });
    setIsModalOpen(true);
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.skuCode.trim()) return;

    if (editingProduct) {
      updateProduct({
        ...formData,
        productId: editingProduct.productId,
      });
    } else {
      addProduct(formData);
    }
    setIsModalOpen(false);
  };

  // Filter products by search
  const filteredProducts = products.filter((p: Product) => {
    const q = searchQuery.toLowerCase();
    return (
      p.name.toLowerCase().includes(q) ||
      p.skuCode.toLowerCase().includes(q) ||
      p.category.toLowerCase().includes(q)
    );
  });

  return (
    <div className="p-4 space-y-4">
      {/* Header and Add Action */}
      <div className="p-4 bg-panel border border-hairline rounded-sm space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h1 className="text-base-tech font-semibold text-text-pri flex items-center gap-2">
              <Boxes className="w-5 h-5 text-amber" />
              Product Master & Packaging Specification Matrix
            </h1>
            <p className="text-xs-tech text-text-sec mt-0.5">
              Defines the core case-to-unit pack size conversion formulas used by edge camera object detectors.
            </p>
          </div>

          <button
            onClick={openAddModal}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs-tech font-semibold rounded-sm bg-amber/20 hover:bg-amber/30 text-amber border border-amber/40 transition-colors self-start sm:self-auto"
          >
            <Plus className="w-3.5 h-3.5" />
            Add SKU Pack Profile
          </button>
        </div>

        {/* Search */}
        <div className="relative pt-2 border-t border-hairline max-w-md">
          <Search className="w-3.5 h-3.5 text-text-sec absolute left-3 top-4.5" />
          <input
            type="text"
            placeholder="Search SKU code, product name, category..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri placeholder:text-text-sec/60 focus-visible:outline-2 focus-visible:outline-amber"
          />
        </div>
      </div>

      {/* Products Table */}
      <div className="bg-panel border border-hairline rounded-sm overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-hairline bg-panel-raised text-xs-tech">
          <span className="font-semibold text-text-pri">
            Active Product Catalog ({filteredProducts.length} entries)
          </span>
          <span className="font-mono text-text-sec text-[11px]">
            Pack multipliers verified
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-hairline bg-canvas/60 text-xs-tech text-text-sec font-normal">
                <th className="py-2 px-3 font-normal">SKU Code</th>
                <th className="py-2 px-3 font-normal">Product Description</th>
                <th className="py-2 px-3 font-normal">Category</th>
                <th className="py-2 px-3 font-normal text-right">
                  <span className="text-amber font-semibold">Pack Size (Case Multiplier)</span>
                </th>
                <th className="py-2 px-3 font-normal text-right">Single Unit Price</th>
                <th className="py-2 px-3 font-normal text-right">Full Case Price</th>
                <th className="py-2 px-3 font-normal text-right">Reorder Threshold</th>
                <th className="py-2 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredProducts.length > 0 ? (
                filteredProducts.map((prod: Product) => (
                  <tr
                    key={prod.productId}
                    className="border-b border-hairline/60 hover:bg-panel-raised/50 transition-colors text-xs-tech"
                  >
                    {/* SKU */}
                    <td className="py-2.5 px-3 font-mono font-semibold text-text-pri whitespace-nowrap">
                      {prod.skuCode}
                    </td>

                    {/* Name */}
                    <td className="py-2.5 px-3 text-text-pri font-medium">
                      {prod.name}
                    </td>

                    {/* Category */}
                    <td className="py-2.5 px-3 text-text-sec">
                      <span className="px-2 py-0.5 rounded-sm bg-panel-raised border border-hairline text-[11px]">
                        {prod.category}
                      </span>
                    </td>

                    {/* Pack Size - Visually Prominent */}
                    <td className="py-2.5 px-3 text-right whitespace-nowrap">
                      <div className="inline-flex flex-col items-end">
                        <span className="font-mono text-sm-tech font-bold text-mono-val px-2 py-0.5 bg-canvas border border-amber/30 rounded-sm">
                          {prod.packSize} <span className="text-[10px] text-amber">units/case</span>
                        </span>
                        <span className="text-[10px] text-text-sec mt-0.5">
                          1 case = {prod.packSize} eaches
                        </span>
                      </div>
                    </td>

                    {/* Unit Price */}
                    <td className="py-2.5 px-3 font-mono text-right text-text-sec whitespace-nowrap">
                      ₹{prod.unitPrice.toFixed(2)}
                    </td>

                    {/* Case Price */}
                    <td className="py-2.5 px-3 font-mono text-right text-text-pri font-semibold whitespace-nowrap">
                      ₹{prod.casePrice.toFixed(2)}
                    </td>

                    {/* Reorder Threshold */}
                    <td className="py-2.5 px-3 font-mono text-right text-text-sec whitespace-nowrap">
                      {prod.reorderThreshold} cs
                    </td>

                    {/* Actions */}
                    <td className="py-2.5 px-3 text-right whitespace-nowrap">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => openEditModal(prod)}
                          className="p-1 rounded-sm text-text-sec hover:text-text-pri hover:bg-hairline/40 transition-colors"
                          title="Edit product pack configuration"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => {
                            if (confirm(`Delete SKU ${prod.skuCode} (${prod.name})?`)) {
                              deleteProduct(prod.productId);
                            }
                          }}
                          className="p-1 rounded-sm text-text-sec hover:text-status-high hover:bg-red-950/20 transition-colors"
                          title="Delete product"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : products.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-16 text-center text-xs-tech text-text-sec">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Boxes className="w-7 h-7 text-hairline" />
                      <span className="text-text-pri font-medium">No products registered in master catalog</span>
                      <span className="text-[11px] max-w-sm">
                        Register SKU pack profiles so edge computer vision models can resolve detected cases into unit counts.
                      </span>
                      <button
                        onClick={openAddModal}
                        className="mt-2 inline-flex items-center gap-1.5 px-3 py-1.5 bg-amber/20 hover:bg-amber/30 text-amber border border-amber/40 rounded-sm font-semibold transition-colors"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        Add First Product
                      </button>
                    </div>
                  </td>
                </tr>
              ) : (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-xs-tech text-text-sec">
                    No products matched search query "{searchQuery}".
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add / Edit Product Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingProduct ? `Edit SKU: ${editingProduct.skuCode}` : 'Register New Product & Case Pack'}
        subtitle="Edge computer vision uses these exact pack sizes to resolve bounding boxes into unit inventories."
        maxWidth="lg"
      >
        <form onSubmit={handleSave} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {/* SKU Code */}
            <div>
              <label className="block text-xs-tech font-medium text-text-sec mb-1">
                SKU Identifier Code
              </label>
              <input
                type="text"
                value={formData.skuCode}
                onChange={(e) => setFormData({ ...formData, skuCode: e.target.value })}
                className="w-full px-3 py-2 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
                required
              />
            </div>

            {/* Category */}
            <div>
              <label className="block text-xs-tech font-medium text-text-sec mb-1">
                Product Category
              </label>
              <select
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                className="w-full px-3 py-2 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
              >
                <option value="Beverages">Beverages</option>
                <option value="Pantry">Pantry</option>
                <option value="Household">Household</option>
                <option value="Snacks">Snacks</option>
                <option value="Hardware">Hardware</option>
                <option value="Electronics">Electronics</option>
              </select>
            </div>
          </div>

          {/* Product Name */}
          <div>
            <label className="block text-xs-tech font-medium text-text-sec mb-1">
              Full Product Name / Description
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g. Glacier Pure Spring Water 500ml"
              className="w-full px-3 py-2 bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
              required
            />
          </div>

          {/* Pack Size - Highlighted */}
          <div className="p-3.5 bg-panel border-2 border-amber/40 rounded-sm space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs-tech font-bold text-amber flex items-center gap-1.5">
                <PackageCheck className="w-4 h-4" />
                Case Pack Multiplier (Pack Size) *
              </label>
              <span className="font-mono text-xs-tech font-bold text-mono-val">
                {formData.packSize} units/case
              </span>
            </div>

            <input
              type="number"
              min={1}
              max={240}
              value={formData.packSize}
              onChange={(e) => setFormData({ ...formData, packSize: parseInt(e.target.value) || 1 })}
              className="w-full px-3 py-2 font-mono text-base-tech font-semibold bg-canvas border border-hairline rounded-sm text-mono-val focus-visible:outline-2 focus-visible:outline-amber"
              required
            />

            <div className="flex items-center gap-1 text-[11px] text-text-sec">
              <AlertCircle className="w-3.5 h-3.5 text-amber flex-shrink-0" />
              <span>
                <strong>Helper Guide:</strong> Exact units contained inside 1 sealed master corrugated box. When vision camera tags 1 case, inventory subtracts {formData.packSize} units.
              </span>
            </div>
          </div>

          {/* Pricing Grid */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs-tech font-medium text-text-sec mb-1">
                Single Unit (₹)
              </label>
              <input
                type="number"
                step="0.01"
                min={0}
                value={formData.unitPrice}
                onChange={(e) => setFormData({ ...formData, unitPrice: parseFloat(e.target.value) || 0 })}
                className="w-full px-3 py-1.5 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
              />
            </div>

            <div>
              <label className="block text-xs-tech font-medium text-text-sec mb-1">
                Case Price (₹)
              </label>
              <input
                type="number"
                step="0.01"
                min={0}
                value={formData.casePrice}
                onChange={(e) => setFormData({ ...formData, casePrice: parseFloat(e.target.value) || 0 })}
                className="w-full px-3 py-1.5 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
              />
            </div>

            <div>
              <label className="block text-xs-tech font-medium text-text-sec mb-1">
                Reorder Threshold
              </label>
              <input
                type="number"
                min={0}
                value={formData.reorderThreshold}
                onChange={(e) => setFormData({ ...formData, reorderThreshold: parseInt(e.target.value) || 0 })}
                className="w-full px-3 py-1.5 font-mono bg-canvas border border-hairline rounded-sm text-xs-tech text-text-pri focus-visible:outline-2 focus-visible:outline-amber"
              />
            </div>
          </div>

          {/* Form Actions */}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-hairline">
            <button
              type="button"
              onClick={() => setIsModalOpen(false)}
              className="px-3 py-1.5 text-xs-tech rounded-sm border border-hairline hover:bg-hairline/30 text-text-sec transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-1.5 text-xs-tech font-semibold rounded-sm bg-amber hover:bg-amber/90 text-black transition-colors"
            >
              {editingProduct ? 'Update Product Profile' : 'Save Product Master'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

