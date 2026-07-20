"use client";

import { useState } from "react";
import DashboardTab from "@/components/DashboardTab";
import { Power } from "lucide-react";

export default function JobPulseDashboard() {
  const [activeTab, setActiveTab] = useState<string>("CV-Library");
  const platforms = ["Universal", "CV-Library", "Indeed", "LinkedIn"];

  const shutdownEngine = async () => {
    if (confirm("Are you sure you want to turn off the background JobPulse Engine? You will need to reopen the .exe file to use the app again.")) {
      try {
        const API_BASE = "http://127.0.0.1:8000";
        await fetch(`${API_BASE}/api/shutdown`, { method: "POST" });
        alert("Engine shut down successfully. You can safely close this browser tab.");
      } catch (e) {
        alert("Engine is already offline or couldn't be reached.");
      }
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-50 p-8 font-sans selection:bg-indigo-500/30">
      <div className="max-w-7xl mx-auto space-y-8">

        {/* Header */}
        <div className="flex justify-between items-center">
          <div className="space-y-1">
            <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">JobPulse AI</h1>
            <p className="text-neutral-400">Enterprise Recruitment Intelligence Platform</p>
          </div>
          <button 
            onClick={shutdownEngine}
            className="flex items-center gap-2 px-4 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 rounded-md transition-colors text-sm font-medium"
          >
            <Power className="w-4 h-4" /> Turn Off Engine
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex space-x-2 border-b border-neutral-800 pb-px">
          {platforms.map(platform => (
            <button
              key={platform}
              onClick={() => setActiveTab(platform)}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
                activeTab === platform
                  ? "bg-indigo-600/10 text-indigo-400 border-b-2 border-indigo-500"
                  : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900"
              }`}
            >
              {platform} Search
            </button>
          ))}
        </div>

        {/* Render all tabs, but hide inactive ones using CSS to preserve their internal state! */}
        {platforms.map(platform => (
          <div key={platform} style={{ display: activeTab === platform ? 'block' : 'none' }}>
            <DashboardTab platformName={platform} />
          </div>
        ))}

      </div>
    </div>
  );
}
