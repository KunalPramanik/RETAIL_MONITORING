"use client";
import { useState, useEffect } from "react";
import { Activity, Camera, Box, FileText, AlertTriangle, Settings, ShieldAlert, LogOut } from "lucide-react";

export default function Dashboard() {
  const [stats, setStats] = useState({ cameras: 0, alerts: 0, products: 0 });

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="p-4 border-b border-gray-800">
          <h1 className="text-xl font-bold flex items-center gap-2 text-blue-400">
            <ShieldAlert /> SEC-OPS V8
          </h1>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <a href="#" className="flex items-center gap-3 p-3 bg-blue-900/30 text-blue-400 rounded-lg">
            <Activity size={20} /> Dashboard
          </a>
          <a href="#" className="flex items-center gap-3 p-3 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors">
            <Camera size={20} /> Cameras
          </a>
          <a href="#" className="flex items-center gap-3 p-3 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors">
            <AlertTriangle size={20} /> Alerts
          </a>
          <a href="#" className="flex items-center gap-3 p-3 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors">
            <Box size={20} /> Inventory
          </a>
          <a href="#" className="flex items-center gap-3 p-3 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors">
            <FileText size={20} /> Invoices
          </a>
        </nav>
        <div className="p-4 border-t border-gray-800">
          <a href="#" className="flex items-center gap-3 p-3 text-gray-400 hover:text-white rounded-lg transition-colors">
            <Settings size={20} /> Settings
          </a>
          <a href="#" className="flex items-center gap-3 p-3 text-red-400 hover:bg-red-900/20 rounded-lg transition-colors mt-2">
            <LogOut size={20} /> Logout
          </a>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 bg-gray-950 overflow-y-auto">
        <header className="p-6 border-b border-gray-800 flex justify-between items-center bg-gray-900/50">
          <h2 className="text-2xl font-bold">Command Center</h2>
          <div className="flex gap-4">
            <span className="px-3 py-1 bg-green-900/30 text-green-400 rounded-full text-sm border border-green-800">System Online</span>
          </div>
        </header>

        <div className="p-6 space-y-6">
          {/* KPI Grid */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              { label: "Active Cameras", value: "4 / 4", icon: Camera, color: "text-blue-400" },
              { label: "Today's Alerts", value: "12", icon: AlertTriangle, color: "text-yellow-400" },
              { label: "Items Scanned", value: "1,204", icon: Box, color: "text-green-400" },
              { label: "Tracking Accuracy", value: "98.7%", icon: Activity, color: "text-purple-400" },
            ].map((kpi, idx) => (
              <div key={idx} className="p-6 bg-gray-900 border border-gray-800 rounded-xl">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="text-gray-400 text-sm mb-1">{kpi.label}</p>
                    <h3 className="text-3xl font-bold">{kpi.value}</h3>
                  </div>
                  <kpi.icon className={kpi.color} size={24} />
                </div>
              </div>
            ))}
          </div>

          {/* Camera Grid */}
          <div>
            <h3 className="text-xl font-bold mb-4">Live Feeds</h3>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {[1, 2, 3, 4].map((cam) => (
                <div key={cam} className="aspect-video bg-gray-900 border border-gray-800 rounded-xl relative overflow-hidden group">
                  <div className="absolute top-4 left-4 z-10 flex gap-2">
                    <span className="px-2 py-1 bg-black/60 backdrop-blur rounded text-xs border border-gray-700">CAM-0{cam}</span>
                    <span className="px-2 py-1 bg-red-500/20 text-red-400 backdrop-blur rounded text-xs border border-red-900 flex items-center gap-1">
                      <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div> REC
                    </span>
                  </div>
                  {/* Mock Video Placeholder */}
                  <div className="w-full h-full bg-gray-800 flex items-center justify-center">
                     <Camera size={48} className="text-gray-700" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
