"use client";

import { useState } from "react";
import DashboardTab from "@/components/DashboardTab";

export default function JobPulseDashboard() {
  const [activeTab, setActiveTab] = useState<string>("CV-Library");
  
  const platforms = ["CV-Library", "Indeed", "LinkedIn"];

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-50 p-8 font-sans selection:bg-indigo-500/30">
      <div className="max-w-7xl mx-auto space-y-8">

        {/* Header */}
        <div className="space-y-1">
          <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">JobPulse AI</h1>
          <p className="text-neutral-400">Enterprise Recruitment Intelligence Platform</p>
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
