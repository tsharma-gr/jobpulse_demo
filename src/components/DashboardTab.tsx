"use client";

import { useState, KeyboardEvent, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Search, Loader2, X, Briefcase, MapPin, Building2, CheckCircle2, ExternalLink, Calendar, Tag, Layers } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface DiscoveredJob {
  job_title: string;
  company_name: string;
  location: string;
  job_site: string;
  job_url: string;
  date_posted?: string;
  job_type?: string;
  industry_match?: string;
  reason_for_match?: string;
  match_score?: number;
}

export default function DashboardTab({ platformName }: { platformName: string }) {
  const [jobTitles, setJobTitles] = useState<string[]>([]);
  const [titleInput, setTitleInput] = useState("");
  const [industries, setIndustries] = useState<string[]>([]);
  const [industryInput, setIndustryInput] = useState("");
  const [location, setLocation] = useState("United Kingdom");
  const [radius, setRadius] = useState("50");
  const [postedDate, setPostedDate] = useState(
    platformName === "Indeed" ? "All Dates" : 
    platformName === "LinkedIn" ? "Any time" : "Last 28 days"
  );
  const [postedDates, setPostedDates] = useState({
    "CV-Library": "Last 28 days",
    "Indeed": "All Dates",
    "LinkedIn": "Any time"
  });
  const [isSearching, setIsSearching] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState("");
  const [logs, setLogs] = useState<{time: string, text: string}[]>([]);
  const [jobsFound, setJobsFound] = useState(0);
  const [discoveredJobs, setDiscoveredJobs] = useState<DiscoveredJob[]>([]);
  const [expandedJob, setExpandedJob] = useState<number | null>(null);

  const addTags = (rawText: string, type: 'title' | 'industry') => {
    const newTags = rawText.split(/[,|]/).map(t => t.trim()).filter(t => t.length > 0);
    if (newTags.length === 0) return;
    if (type === 'title') {
      setJobTitles(prev => Array.from(new Set([...prev, ...newTags])));
      setTitleInput("");
    } else {
      setIndustries(prev => Array.from(new Set([...prev, ...newTags])));
      setIndustryInput("");
    }
  };

  const handleAddChip = (e: KeyboardEvent<HTMLInputElement>, type: 'title' | 'industry') => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addTags(type === 'title' ? titleInput : industryInput, type);
    }
  };

  const handleInputChange = (val: string, type: 'title' | 'industry') => {
    if (val.includes(',')) { addTags(val, type); return; }
    if (type === 'title') setTitleInput(val); else setIndustryInput(val);
  };

  const removeChip = (index: number, type: 'title' | 'industry') => {
    if (type === 'title') setJobTitles(p => p.filter((_, i) => i !== index));
    else setIndustries(p => p.filter((_, i) => i !== index));
  };

  const startSearch = async () => {
    let currentTitles = [...jobTitles];
    if (titleInput.trim()) {
      currentTitles = Array.from(new Set([...currentTitles, ...titleInput.split(/[,|]/).map(t => t.trim()).filter(t => t)]));
      setJobTitles(currentTitles); setTitleInput("");
    }
    let currentInds = [...industries];
    if (industryInput.trim()) {
      currentInds = Array.from(new Set([...currentInds, ...industryInput.split(/[,|]/).map(t => t.trim()).filter(t => t)]));
      setIndustries(currentInds); setIndustryInput("");
    }
    if (currentTitles.length === 0 || !location) return;

    setIsSearching(true); setProgress(5); setStatusText(`Initializing ${platformName} Search...`);
    setLogs([]); setJobsFound(0); setDiscoveredJobs([]); setExpandedJob(null);

    try {
      const RAW_API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const API_BASE = RAW_API.replace(/\/$/, "");
      const res = await fetch(`${API_BASE}/api/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          job_titles: currentTitles, 
          industries: currentInds, 
          location, 
          radius: parseInt(radius), 
          posted_date: postedDate,
          posted_dates: platformName === "Universal" ? postedDates : {},
          platforms: platformName === "Universal" ? ["CV-Library", "Indeed", "LinkedIn"] : [platformName]
        })
      });
      const data = await res.json();
      setSessionId(data.session_id);
    } catch (e) {
      console.error(e);
      setStatusText("Failed to connect to backend API");
      setIsSearching(false);
    }
  };

  useEffect(() => {
    if (!sessionId) return;
    const RAW_API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const API_BASE = RAW_API.replace(/\/$/, "");
    
    let isMounted = true;
    const abortController = new AbortController();

    const fetchStream = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/events/${sessionId}`, {
          method: 'GET',
          headers: {
            'Accept': 'text/event-stream',
            'ngrok-skip-browser-warning': 'true',
            'bypass-tunnel-reminder': 'true'
          },
          signal: abortController.signal
        });

        if (!response.body) return;
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (isMounted) {
          const { value, done } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataStr = line.replace('data: ', '').trim();
              if (!dataStr) continue;
              
              try {
                const parsed = JSON.parse(dataStr);
                const eventType = parsed.event;
                const data = parsed.data || {};
                const addLog = (text: string) => setLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), text }]);

                if (eventType === "SEARCH_STARTED") {
                  setStatusText("Search Started"); setProgress(10); addLog("Search pipeline initialized");
                } else if (eventType === "DISCOVERY_STARTED") {
                  setStatusText("Discovering Candidates..."); setProgress(30); addLog(`Searching ${(data.sources as string[])?.join(", ")}`);
                } else if (eventType === "DISCOVERY_COMPLETED") {
                  setStatusText("Discovery Completed"); setProgress(50); addLog(`Found ${data.urls_found} candidate URLs`);
                } else if (eventType === "EXTRACTION_STARTED") {
                  setStatusText("Extracting Job Descriptions..."); setProgress(60); addLog("Running Crawl4AI extractors");
                } else if (eventType === "AI_STARTED") {
                  setStatusText("AI Analysis in Progress..."); setProgress(75); addLog("Analyzing with DeepSeek API");
                } else if (eventType === "AI_COMPLETED") {
                  setStatusText("AI Analysis Completed"); setProgress(85); addLog("Match scoring applied");
                } else if (eventType === "VERIFICATION_COMPLETED") {
                  setStatusText("Verification Completed"); setProgress(95); setJobsFound((data.verified_jobs as number) || 0); addLog(`Verified ${data.verified_jobs} active roles`);
                } else if (eventType === "RANKING_COMPLETED") {
                  setStatusText("Ranking & Deduplication"); addLog("Applied deterministic ranking");
                } else if (eventType === "JOB_VERIFIED") {
                  const newJob = data as unknown as DiscoveredJob;
                  setDiscoveredJobs(prev => [...prev, newJob]);
                  setJobsFound(prev => prev + 1);
                  addLog(`AI verified match: ${newJob.job_title} at ${newJob.company_name}`);
                } else if (eventType === "FINISHED") {
                  setStatusText("Search Completed ✓"); setProgress(100);
                  if (data.jobs && Array.isArray(data.jobs)) {
                      setDiscoveredJobs(data.jobs as DiscoveredJob[]); // Final sync if provided
                      setJobsFound(data.jobs.length);
                  }
                  addLog(`Search finished. ${data.jobs_ready || 0} jobs ready for review.`);
                  setIsSearching(false);
                } else if (eventType === "ERROR") {
                  setStatusText("Error Occurred"); addLog(`Error: ${data.detail}`); setIsSearching(false);
                }
              } catch (e) {
                // Ignore parse errors for incomplete chunks
              }
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name !== 'AbortError') {
          console.error("Stream error:", err);
          setStatusText("Connection to server lost");
        }
      } finally {
        setIsSearching(false);
      }
    };

    fetchStream();

    return () => {
      isMounted = false;
      abortController.abort();
    };
  }, [sessionId]);

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Search Controls */}
        <Card className="lg:col-span-1 bg-neutral-900 border-neutral-800 text-neutral-50 shadow-2xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Search className="w-5 h-5 text-indigo-400" />{platformName} Search</CardTitle>
            <CardDescription className="text-neutral-400">Configure parameters specific to {platformName}.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Job Titles */}
            <div className="space-y-3">
              <label className="text-sm font-medium flex items-center gap-2 text-neutral-300"><Briefcase className="w-4 h-4 text-cyan-400" /> Job Titles</label>
              <div className="flex flex-wrap gap-1.5 mb-2 w-full">
                <AnimatePresence>
                  {jobTitles.map((title, idx) => (
                    <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.8 }} key={idx} className="max-w-full">
                      <Badge variant="secondary" className="bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 px-2.5 py-1 text-xs font-medium h-auto whitespace-normal break-words text-left max-w-full overflow-hidden inline-flex items-center gap-1.5">
                        <span>{title}</span>
                        <button onClick={() => removeChip(idx, 'title')} className="hover:text-white shrink-0 mt-0.5"><X className="w-3 h-3" /></button>
                      </Badge>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
              <Input placeholder="e.g. Estimator, QS (Press Enter)" value={titleInput} onChange={e => handleInputChange(e.target.value, 'title')} onKeyDown={e => handleAddChip(e, 'title')} className="bg-neutral-950 border-neutral-800 text-neutral-100 focus-visible:ring-indigo-500 h-9 text-sm" />
            </div>

            {/* Industries */}
            <div className="space-y-3">
              <label className="text-sm font-medium flex items-center gap-2 text-neutral-300"><Building2 className="w-4 h-4 text-emerald-400" /> Industry / Sector</label>
              <div className="flex flex-wrap gap-1.5 mb-2 w-full">
                <AnimatePresence>
                  {industries.map((ind, idx) => (
                    <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.8 }} key={idx} className="max-w-full">
                      <Badge variant="secondary" className="bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 px-2.5 py-1 text-xs font-medium h-auto whitespace-normal break-words text-left max-w-full overflow-hidden inline-flex items-center gap-1.5">
                        <span>{ind}</span>
                        <button onClick={() => removeChip(idx, 'industry')} className="hover:text-white shrink-0 mt-0.5"><X className="w-3 h-3" /></button>
                      </Badge>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
              <Input placeholder="e.g. Joinery, Construction" value={industryInput} onChange={e => handleInputChange(e.target.value, 'industry')} onKeyDown={e => handleAddChip(e, 'industry')} className="bg-neutral-950 border-neutral-800 text-neutral-100 focus-visible:ring-emerald-500 h-9 text-sm" />
            </div>

            {/* Location, Radius, Posted Date */}
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-2">
                <label className="text-xs font-medium flex items-center gap-1.5 text-neutral-300"><MapPin className="w-3.5 h-3.5 text-rose-400" /> Location</label>
                <Input placeholder="e.g. London" value={location} onChange={e => setLocation(e.target.value)} className="bg-neutral-950 border-neutral-800 text-neutral-100 focus-visible:ring-rose-500 h-9 text-sm" />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium text-neutral-300">Radius</label>
                <select value={radius} onChange={e => setRadius(e.target.value)} className="flex h-9 w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-1 text-sm text-neutral-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500">
                  <option value="10">10 Miles</option>
                  <option value="25">25 Miles</option>
                  <option value="50">50 Miles</option>
                  <option value="75">75 Miles</option>
                  <option value="100">100 Miles</option>
                </select>
              </div>
              {platformName === "Universal" ? (
                <div className="col-span-3 grid grid-cols-3 gap-3">
                  <div className="space-y-2">
                    <label className="text-xs font-medium text-neutral-300">CV-Library Date</label>
                    <select value={postedDates["CV-Library"]} onChange={e => setPostedDates(p => ({...p, "CV-Library": e.target.value}))} className="flex h-9 w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-1 text-sm text-neutral-100 focus-visible:ring-2 focus-visible:ring-indigo-500">
                      <option value="Last 24 hours">Last 24 hours</option>
                      <option value="Last 2 days">Last 2 days</option>
                      <option value="Last 3 days">Last 3 days</option>
                      <option value="Last 7 days">Last 7 days</option>
                      <option value="Last 14 days">Last 14 days</option>
                      <option value="Last 28 days">Last 28 days</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-medium text-neutral-300">Indeed Date</label>
                    <select value={postedDates["Indeed"]} onChange={e => setPostedDates(p => ({...p, "Indeed": e.target.value}))} className="flex h-9 w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-1 text-sm text-neutral-100 focus-visible:ring-2 focus-visible:ring-indigo-500">
                      <option value="Last 24 hours">Last 24 hours</option>
                      <option value="Last 3 days">Last 3 days</option>
                      <option value="Last 7 days">Last 7 days</option>
                      <option value="Last 14 days">Last 14 days</option>
                      <option value="All Dates">All Dates</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-medium text-neutral-300">LinkedIn Date</label>
                    <select value={postedDates["LinkedIn"]} onChange={e => setPostedDates(p => ({...p, "LinkedIn": e.target.value}))} className="flex h-9 w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-1 text-sm text-neutral-100 focus-visible:ring-2 focus-visible:ring-indigo-500">
                      <option value="Last 24 hours">Last 24 hours</option>
                      <option value="Past week">Past week</option>
                      <option value="Past month">Past month</option>
                      <option value="Any time">Any time</option>
                    </select>
                  </div>
                </div>
              ) : (
              <div className="space-y-2">
                <label className="text-xs font-medium text-neutral-300">Posted Date</label>
                <select value={postedDate} onChange={e => setPostedDate(e.target.value)} className="flex h-9 w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-1 text-sm text-neutral-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500">
                  {platformName === "Indeed" ? (
                    <>
                      <option value="Last 24 hours">Last 24 hours</option>
                      <option value="Last 3 days">Last 3 days</option>
                      <option value="Last 7 days">Last 7 days</option>
                      <option value="Last 14 days">Last 14 days</option>
                      <option value="All Dates">All Dates</option>
                    </>
                  ) : platformName === "LinkedIn" ? (
                    <>
                      <option value="Last 24 hours">Last 24 hours</option>
                      <option value="Past week">Past week</option>
                      <option value="Past month">Past month</option>
                      <option value="Any time">Any time</option>
                    </>
                  ) : (
                    <>
                      <option value="Last 24 hours">Last 24 hours</option>
                      <option value="Last 2 days">Last 2 days</option>
                      <option value="Last 3 days">Last 3 days</option>
                      <option value="Last 7 days">Last 7 days</option>
                      <option value="Last 14 days">Last 14 days</option>
                      <option value="Last 28 days">Last 28 days</option>
                    </>
                  )}
                </select>
              </div>
              )}
            </div>

            <Button onClick={startSearch} disabled={isSearching || (!titleInput.trim() && jobTitles.length === 0) || !location} className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-medium shadow-lg shadow-indigo-900/20 h-11">
              {isSearching ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Running {platformName}...</> : `Start ${platformName} AI`}
            </Button>
          </CardContent>
        </Card>

        {/* Right Panel */}
        <div className="lg:col-span-2 space-y-5">
          {/* Live Progress Card */}
          <Card className="bg-neutral-900 border-neutral-800 text-neutral-50 shadow-2xl relative overflow-hidden">
            {isSearching && (
              <div className="absolute top-0 left-0 w-full h-1 bg-neutral-800">
                <motion.div className="h-full bg-gradient-to-r from-indigo-500 via-cyan-400 to-emerald-400" initial={{ width: 0 }} animate={{ width: `${progress}%` }} transition={{ ease: "easeInOut", duration: 0.5 }} />
              </div>
            )}
            <CardHeader className="pb-3">
              <CardTitle className="text-lg font-semibold flex items-center justify-between">
                <span>{platformName} Operations</span>
                {statusText && <Badge variant="outline" className="bg-indigo-500/10 border-indigo-500/30 text-indigo-300 text-xs">{statusText}</Badge>}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="bg-neutral-950 rounded-lg p-3 font-mono text-xs h-44 overflow-y-auto border border-neutral-800/50">
                {logs.length === 0 && !isSearching && <div className="text-neutral-500 flex items-center justify-center h-full">Waiting for {platformName} execution...</div>}
                {logs.map((log, idx) => (
                  <motion.div key={idx} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} className="py-0.5 text-neutral-300">
                    <span className="text-neutral-500 mr-3">[{log.time}]</span>{log.text}
                  </motion.div>
                ))}
                {isSearching && <div className="py-1 text-indigo-400 animate-pulse mt-1 flex items-center"><span className="w-1.5 h-1.5 rounded-full bg-indigo-500 inline-block mr-2" />Processing {platformName}...</div>}
              </div>
            </CardContent>
          </Card>

          {/* Metrics */}
          <div className="grid grid-cols-3 gap-4">
            <Card className="bg-neutral-900 border-neutral-800"><CardContent className="pt-5">
              <div className="text-xs font-medium text-neutral-400 mb-1">URLs Discovered</div>
              <div className="text-2xl font-bold font-mono text-cyan-400">{progress > 40 ? discoveredJobs.length || "..." : "0"}</div>
            </CardContent></Card>
            <Card className="bg-neutral-900 border-neutral-800"><CardContent className="pt-5">
              <div className="text-xs font-medium text-neutral-400 mb-1">AI Match Processing</div>
              <div className="text-2xl font-bold font-mono text-indigo-400">{progress > 80 ? "100%" : progress > 60 ? "In Progress" : "Waiting"}</div>
            </CardContent></Card>
            <Card className="bg-neutral-900 border-neutral-800"><CardContent className="pt-5">
              <div className="text-xs font-medium text-neutral-400 mb-1">Verified Fits</div>
              <div className="text-2xl font-bold font-mono text-emerald-400 flex items-center gap-2">
                {jobsFound}{jobsFound > 0 && <CheckCircle2 className="w-5 h-5 text-emerald-400" />}
              </div>
            </CardContent></Card>
          </div>
        </div>
      </div>

      {/* Results Table */}
      <AnimatePresence>
        {discoveredJobs.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
            <Card className="bg-neutral-900 border-neutral-800 text-neutral-50 shadow-2xl">
              <CardHeader>
                <CardTitle className="text-xl font-semibold flex items-center gap-2 text-white">
                  <Briefcase className="w-5 h-5 text-indigo-400" />
                  {platformName} Vacancies
                  <Badge className="bg-indigo-600/20 text-indigo-300 border border-indigo-500/20 ml-2">{discoveredJobs.length} jobs</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                {/* Table Header */}
                <div className="grid grid-cols-12 gap-2 px-5 py-3 text-xs font-bold text-indigo-300 uppercase tracking-wider border-b border-neutral-800 bg-neutral-950/80">
                  <div className="col-span-3">Job Title / Company</div>
                  <div className="col-span-2">Location</div>
                  <div className="col-span-1">Site</div>
                  <div className="col-span-2">Date Posted</div>
                  <div className="col-span-2">Industry Match</div>
                  <div className="col-span-2">Actions</div>
                </div>

                {/* Table Rows */}
                <div className="divide-y divide-neutral-800">
                  {discoveredJobs.map((job, idx) => (
                    <div key={idx}>
                      <motion.div
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.05 }}
                        className="grid grid-cols-12 gap-2 px-5 py-4 hover:bg-neutral-800/30 transition-colors cursor-pointer"
                        onClick={() => setExpandedJob(expandedJob === idx ? null : idx)}
                      >
                        {/* Job Title & Company */}
                        <div className="col-span-3 pr-2">
                          <div className="font-semibold text-neutral-100 text-sm leading-tight truncate" title={job.job_title}>{job.job_title}</div>
                          <div className="text-neutral-400 text-xs mt-0.5 flex items-center gap-1 truncate" title={job.company_name}>
                            <Building2 className="w-3 h-3 shrink-0" />{job.company_name}
                          </div>
                        </div>

                        {/* Location */}
                        <div className="col-span-2 flex items-center pr-2 overflow-hidden">
                          <div className="text-neutral-300 text-xs flex items-center gap-1 truncate" title={job.location}>
                            <MapPin className="w-3 h-3 text-rose-400 shrink-0" />
                            <span className="truncate">{job.location}</span>
                          </div>
                        </div>

                        {/* Job Site */}
                        <div className="col-span-1 flex items-center">
                          <Badge variant="outline" className="text-xs border-blue-500/30 text-blue-400 bg-blue-500/10">{job.job_site}</Badge>
                        </div>

                        {/* Date Posted */}
                        <div className="col-span-2 flex items-center pr-2 overflow-hidden">
                          <div className="text-neutral-400 text-xs flex items-center gap-1 truncate" title={job.date_posted}>
                            <Calendar className="w-3 h-3 text-cyan-400 shrink-0" />
                            <span className="truncate">
                              {job.date_posted ? (job.date_posted.includes('T') ? job.date_posted.split('T')[0] : job.date_posted) : "Recently"}
                            </span>
                          </div>
                        </div>

                        {/* Industry Match */}
                        <div className="col-span-2 flex items-center pr-2 overflow-hidden">
                          <Badge variant="outline" className="text-xs border-emerald-500/30 text-emerald-400 bg-emerald-500/10 truncate max-w-full" title={job.industry_match || "General"}>
                            <Layers className="w-2.5 h-2.5 mr-1 shrink-0" />
                            <span className="truncate">{job.industry_match || "General"}</span>
                          </Badge>
                        </div>

                        {/* Actions */}
                        <div className="col-span-2 flex items-center gap-2">
                          <a
                            href={job.job_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={e => e.stopPropagation()}
                            className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 border border-indigo-500/30 bg-indigo-500/10 hover:bg-indigo-500/20 px-2 py-1 rounded-md transition-all"
                          >
                            <ExternalLink className="w-3 h-3" /> Apply
                          </a>
                          <span className="text-xs text-neutral-500">{expandedJob === idx ? "▲" : "▼"}</span>
                        </div>
                      </motion.div>

                      {/* Expandable Reason Row */}
                      <AnimatePresence>
                        {expandedJob === idx && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            className="px-5 pb-4 bg-indigo-950/20 border-t border-indigo-500/10"
                          >
                            <div className="flex items-start gap-2 mt-3">
                              <Tag className="w-3.5 h-3.5 text-indigo-400 mt-0.5 shrink-0" />
                              <div>
                                <div className="text-xs font-semibold text-indigo-300 mb-1">Why this matches your search</div>
                                <div className="text-xs text-neutral-300 leading-relaxed">{job.reason_for_match || "Relevant to your search criteria."}</div>
                              </div>
                            </div>
                            {job.job_type && (
                              <div className="flex items-center gap-2 mt-2">
                                <Briefcase className="w-3.5 h-3.5 text-neutral-500" />
                                <span className="text-xs text-neutral-400">Job Type: <span className="text-neutral-200">{job.job_type}</span></span>
                              </div>
                            )}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
