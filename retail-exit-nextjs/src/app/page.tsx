"use client";
import { useState, useEffect } from "react";
import { Activity, Camera, Box, FileText, AlertTriangle, Settings, ShieldAlert, LogOut, CheckCircle } from "lucide-react";

export default function Dashboard() {
  const [activeView, setActiveView] = useState("Dashboard");
  const [currentTime, setCurrentTime] = useState("");

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(timer);
  }, []);

  const renderContent = () => {
    if (activeView === "Dashboard") {
      return (
        <div className="space-y-6 animate-in fade-in zoom-in duration-300">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[
              { label: "Active Cameras", value: "4 / 4", icon: Camera, color: "text-blue-400" },
              { label: "Today's Alerts", value: "12", icon: AlertTriangle, color: "text-yellow-400" },
              { label: "Items Scanned", value: "1,204", icon: Box, color: "text-green-400" },
              { label: "Tracking Accuracy", value: "98.7%", icon: Activity, color: "text-purple-400" },
            ].map((kpi, idx) => (
              <div key={idx} className="p-6 bg-gray-900 border border-gray-800 rounded-xl hover:border-gray-700 transition-colors">
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

          <div>
            <h3 className="text-xl font-bold mb-4">Live Exit Feeds</h3>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {[1, 2, 3, 4].map((cam) => (
                <div key={cam} className="aspect-video bg-gray-900 border border-gray-800 rounded-xl relative overflow-hidden group">
                  <div className="absolute top-4 left-4 z-10 flex gap-2">
                    <span className="px-2 py-1 bg-black/60 backdrop-blur rounded text-xs border border-gray-700 font-mono">CAM-0{cam}</span>
                    <span className="px-2 py-1 bg-red-500/20 text-red-400 backdrop-blur rounded text-xs border border-red-900 flex items-center gap-1 font-bold">
                      <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div> REC
                    </span>
                  </div>
                  <div className="w-full h-full bg-gray-800 flex items-center justify-center group-hover:bg-gray-750 transition-colors">
                     <Camera size={48} className="text-gray-700" />
                     <p className="absolute bottom-4 text-gray-500 text-sm">Connecting to RTSP Stream...</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      );
    }

    if (activeView === "Cameras") {
      return (
        <div className="p-6 bg-gray-900 border border-gray-800 rounded-xl animate-in slide-in-from-right-4 duration-300">
          <h2 className="text-2xl font-bold mb-4">Camera Management</h2>
          <p className="text-gray-400 mb-6">Manage RTSP feeds, Edge AI nodes, and ByteTrack configurations.</p>
          <div className="space-y-4">
             {[1, 2, 3, 4].map((cam) => (
               <div key={cam} className="p-4 border border-gray-800 rounded-lg flex justify-between items-center bg-gray-950">
                 <div className="flex items-center gap-4">
                   <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                   <div>
                     <h4 className="font-bold">Exit Lane {cam} Camera</h4>
                     <p className="text-sm text-gray-500 font-mono">rtsp://192.168.1.10{cam}/stream</p>
                   </div>
                 </div>
                 <button className="px-4 py-2 bg-blue-900/30 text-blue-400 border border-blue-900 rounded hover:bg-blue-900/50 transition-colors">Configure</button>
               </div>
             ))}
          </div>
        </div>
      );
    }

    if (activeView === "Alerts") {
      return (
        <div className="p-6 bg-gray-900 border border-gray-800 rounded-xl animate-in slide-in-from-right-4 duration-300">
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-yellow-400"><AlertTriangle /> Security Alerts</h2>
          <p className="text-gray-400 mb-6">Real-time discrepancy and occlusion alarms.</p>
          <div className="p-4 border border-red-900/50 bg-red-900/10 rounded-lg mb-4">
            <h4 className="font-bold text-red-400">HIGH PRIORITY: Quantity Mismatch</h4>
            <p className="text-sm text-gray-300">Exit Lane 2: Invoice declared 24 units, ByteTrack counted 25 units.</p>
            <p className="text-xs text-gray-500 mt-2 font-mono">10 mins ago</p>
          </div>
          <div className="p-4 border border-yellow-900/50 bg-yellow-900/10 rounded-lg">
            <h4 className="font-bold text-yellow-400">WARNING: Occlusion Detected</h4>
            <p className="text-sm text-gray-300">Exit Lane 1: Subject temporarily occluded tracking path. Track ID 104 restored.</p>
            <p className="text-xs text-gray-500 mt-2 font-mono">1 hour ago</p>
          </div>
        </div>
      );
    }

    return (
      <div className="p-12 text-center animate-in fade-in duration-300">
        <Activity size={48} className="mx-auto text-gray-600 mb-4 animate-bounce" />
        <h2 className="text-2xl font-bold text-gray-400">Module Initialization</h2>
        <p className="text-gray-500 mt-2">The {activeView} module is securely connecting to the PostgreSQL backend.</p>
      </div>
    );
  };

  return (
    <div className="flex h-screen overflow-hidden bg-gray-950 text-gray-100 selection:bg-blue-900">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col z-20 shadow-xl">
        <div className="p-6 border-b border-gray-800">
          <h1 className="text-xl font-bold flex items-center gap-3 text-blue-400 tracking-tight">
            <ShieldAlert className="text-blue-500" /> SEC-OPS V8
          </h1>
        </div>
        <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
          {[
            { id: "Dashboard", icon: Activity },
            { id: "Cameras", icon: Camera },
            { id: "Alerts", icon: AlertTriangle },
            { id: "Inventory", icon: Box },
            { id: "Invoices", icon: FileText },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveView(item.id)}
              className={w-full flex items-center gap-3 p-3 rounded-lg transition-all duration-200 }
            >
              <item.icon size={20} /> {item.id}
            </button>
          ))}
        </nav>
        <div className="p-4 border-t border-gray-800 space-y-2">
          <button 
            onClick={() => setActiveView("Settings")}
            className={w-full flex items-center gap-3 p-3 rounded-lg transition-colors }
          >
            <Settings size={20} /> Settings
          </button>
          <button className="w-full flex items-center gap-3 p-3 text-red-400 hover:bg-red-950 hover:text-red-300 rounded-lg transition-colors">
            <LogOut size={20} /> Logout
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        {/* Header */}
        <header className="p-6 border-b border-gray-800 flex justify-between items-center bg-gray-900/80 backdrop-blur-md z-10 sticky top-0">
          <h2 className="text-2xl font-bold tracking-tight">{activeView}</h2>
          <div className="flex items-center gap-6">
            <div className="text-sm font-mono text-gray-400 bg-gray-950 px-3 py-1 rounded-md border border-gray-800">
              {currentTime}
            </div>
            <div className="flex items-center gap-2 px-3 py-1 bg-green-950 text-green-400 rounded-full text-sm border border-green-900 font-medium">
              <CheckCircle size={16} /> API Online
            </div>
          </div>
        </header>

        {/* Scrollable View Area */}
        <div className="p-6 overflow-y-auto flex-1">
          {renderContent()}
        </div>
      </main>
    </div>
  );
}
