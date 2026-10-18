import React, { useEffect, useRef, useState, useMemo, useCallback } from "react";

const assetPathPrefix = "/assets";
const imgSearchBar = `${assetPathPrefix}/95d81.png`;
const imgMark = `${assetPathPrefix}/09d01.svg`;
const imgIcon = `${assetPathPrefix}/f5c00.svg`;
const imgIcon1 = `${assetPathPrefix}/021a5.svg`;

const BACKEND_URL = "http://127.0.0.1:8000";

interface WordTiming {
  word: string;
  start: number;
  end: number;
}

interface SummaryData {
  title: string;
  url: string;
  summary: string;
  key_points: string[];
  important_facts: string[];
  date?: string;
}

interface LinkedInData {
  candidate_name: string;
  headline: string;
  location?: string;
  url?: string;
  executive_summary: string;
  skills: string[];
  experience_highlights: string[];
  recommended_roles?: string[];
}

interface ResumeRewrite {
  original: string;
  improved: string;
  reason: string;
}

interface ResumeAnalysisData {
  score?: number;
  verdict: string;
  target_role?: string;
  how_is_resume: string;
  strong_points: string[];
  weak_points: string[];
  suggestions: string[];
  rewrites?: ResumeRewrite[];
}

interface SpeechUnit {
  id: number;
  text: string;
  startWordIndex: number;
  wordCount: number;
}

interface CachedAudioUnit {
  audio: HTMLAudioElement;
  words: WordTiming[];
  duration: number;
}

const SPEED_OPTIONS = [0.94, 1.2, 1.5, 2.0];

export default function App() {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Active Navigation Mode: 'summariser' | 'resume' | 'linkedin' | 'history'
  const [navMode, setNavMode] = useState<"summariser" | "resume" | "linkedin" | "history">(() => {
    const params = new URLSearchParams(window.location.search);
    const view = params.get("view");
    if (view === "resume") return "resume";
    if (view === "linkedin") return "linkedin";
    return "summariser";
  });

  // Active Sub-tab inside Summariser: 'summary' | 'keypoints' | 'facts'
  const [activeSubTab, setActiveSubTab] = useState<"summary" | "keypoints" | "facts">("summary");

  // Audio queue references
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const audioCacheRef = useRef<Map<number, CachedAudioUnit>>(new Map());
  const isPlayingRef = useRef(false);
  const activeUnitIdxRef = useRef(0);

  // Data states
  const [summaryData, setSummaryData] = useState<SummaryData | null>(null);
  const [linkedinData, setLinkedinData] = useState<LinkedInData | null>(null);
  const [resumeData, setResumeData] = useState<ResumeAnalysisData | null>(null);
  const [targetRole, setTargetRole] = useState<string>("");
  const [inputText, setInputText] = useState<string>("");
  const [isProcessing, setIsProcessing] = useState<boolean>(false);

  // Playback state
  const [isPlaying, setIsPlaying] = useState(false);
  const [speedIndex, setSpeedIndex] = useState(0); // 0.94 default
  const [activeWordIdx, setActiveWordIdx] = useState<number>(-1);
  const [playbackCurrentTime, setPlaybackCurrentTime] = useState<number>(0);
  const [playbackTotalDuration, setPlaybackTotalDuration] = useState<number>(0);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [isMaximized, setIsMaximized] = useState(false);

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    let isMounted = true;
    (async () => {
      try {
        const { getCurrentWindow } = await import("@tauri-apps/api/window");
        const appWindow = getCurrentWindow();
        if (isMounted) setIsMaximized(await appWindow.isMaximized());
        unlisten = await appWindow.onResized(async () => {
          if (isMounted) setIsMaximized(await appWindow.isMaximized());
        });
      } catch {
        // Fallback in web browser mode
      }
    })();
    return () => {
      isMounted = false;
      if (unlisten) unlisten();
    };
  }, []);

  const lastSyncedBackendViewRef = useRef<string | null>(null);

  const handleNavChange = useCallback((mode: "summariser" | "resume" | "linkedin" | "history") => {
    setNavMode(mode);
    lastSyncedBackendViewRef.current = mode;
    fetch(`${BACKEND_URL}/api/app/active-view`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ view: mode }),
    }).catch(() => {});
  }, []);

  // Synchronize view mode with backend (when triggered from Chrome extension)
  useEffect(() => {
    let isMounted = true;
    const checkActiveView = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/app/active-view`);
        if (res.ok) {
          const data = await res.json();
          const target = data?.active_view;
          if (target && isMounted) {
            if (lastSyncedBackendViewRef.current === null) {
              lastSyncedBackendViewRef.current = target;
              setNavMode(target);
            } else if (lastSyncedBackendViewRef.current !== target) {
              lastSyncedBackendViewRef.current = target;
              setNavMode(target);
              try {
                const { getCurrentWindow } = await import("@tauri-apps/api/window");
                const win = getCurrentWindow();
                await win.show();
                await win.unminimize();
                await win.setFocus();
              } catch {}
            }
          }
        }
      } catch {}
    };

    checkActiveView();
    const interval = setInterval(checkActiveView, 1200);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);


  const currentSpeed = SPEED_OPTIONS[speedIndex];

  // ─── Data Fetching ────────────────────────────────────────────────────────
  const fetchSummary = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/summary`);
      if (res.ok) {
        const data = await res.json();
        if (data && (data.summary || data.title)) {
          setSummaryData((prev) => {
            if (prev?.title === data.title && prev?.summary === data.summary) {
              return prev;
            }
            return {
              title: data.title || "Webpage Summary",
              url: data.url || "",
              summary: data.summary || "",
              key_points: Array.isArray(data.key_points) ? data.key_points : [],
              important_facts: Array.isArray(data.important_facts) ? data.important_facts : [],
              date: new Date().toLocaleString(),
            };
          });
        }
      }
    } catch (err) {
      console.debug("Fetch summary note:", err);
    }
  }, []);

  const fetchLinkedIn = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/linkedin/profile`);
      if (res.ok) {
        const data = await res.json();
        if (data && data.candidate_name && data.candidate_name !== "No profile analyzed yet") {
          setLinkedinData(data);
        }
      }
    } catch (err) {
      console.debug("Fetch LinkedIn note:", err);
    }
  }, []);

  const fetchResumeData = useCallback(async () => {
    try {
      const [resTarget, resAnalysis] = await Promise.all([
        fetch(`${BACKEND_URL}/api/resume/target`),
        fetch(`${BACKEND_URL}/api/resume/latest`),
      ]);

      if (resTarget.ok) {
        const target = await resTarget.json();
        if (target?.title && target.title !== "General Role") {
          setTargetRole(target.title);
        }
      }

      if (resAnalysis.ok) {
        const analysis = await resAnalysis.json();
        if (analysis?.score !== null && analysis?.verdict !== "No resume screened yet") {
          setResumeData(analysis);
        }
      }
    } catch (err) {
      console.debug("Fetch resume note:", err);
    }
  }, []);

  useEffect(() => {
    fetchSummary();
    fetchLinkedIn();
    fetchResumeData();
    const interval = setInterval(() => {
      fetchSummary();
      fetchLinkedIn();
      fetchResumeData();
    }, 4000);
    return () => clearInterval(interval);
  }, [fetchSummary, fetchLinkedIn, fetchResumeData]);

  // ─── Manual Action / Search Bar Trigger ───────────────────────────────────
  const handleMainAction = async () => {
    if (!inputText.trim()) return;
    setIsProcessing(true);

    if (navMode === "resume") {
      setStatusMessage("Screening candidate resume with Qwen3...");
      try {
        const res = await fetch(`${BACKEND_URL}/api/resume/screen`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            resume_text: inputText,
            target_role: targetRole || "General Evaluation",
          }),
        });
        if (res.ok) {
          const data = await res.json();
          setResumeData(data);
          setInputText("");
          setStatusMessage("Resume screening complete!");
        }
      } catch (err) {
        console.error(err);
      } finally {
        setIsProcessing(false);
      }
      return;
    }

    // Default: Summarize URL or text
    setStatusMessage("Generating summary...");
    try {
      const isUrl = /^https?:\/\//i.test(inputText.trim());
      const res = await fetch(`${BACKEND_URL}/summarize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: isUrl ? inputText.trim() : "Custom Input",
          title: isUrl ? inputText.trim() : "Manual Note",
          content: inputText.trim(),
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setSummaryData({
          title: data.title || "Summary",
          url: isUrl ? inputText.trim() : "",
          summary: data.summary,
          key_points: data.key_points || [],
          important_facts: data.important_facts || [],
          date: new Date().toLocaleString(),
        });
        setInputText("");
        setStatusMessage("Summary ready!");
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsProcessing(false);
    }
  };

  // ─── Audio Speech Units ───────────────────────────────────────────────────
  const speechUnits: SpeechUnit[] = useMemo(() => {
    const units: SpeechUnit[] = [];
    let currentGlobalWord = 0;

    const addUnit = (rawText: string) => {
      const text = rawText.trim();
      if (!text) return;
      const words = text.split(/\s+/).filter(Boolean);
      units.push({
        id: units.length,
        text,
        startWordIndex: currentGlobalWord,
        wordCount: words.length,
      });
      currentGlobalWord += words.length;
    };

    if (navMode === "summariser" && summaryData) {
      if (summaryData.title) addUnit(summaryData.title);
      if (summaryData.summary) {
        const rawSentences = summaryData.summary.match(/[^.!?]+[.!?]+(?:\s+|$)|[^.!?]+$/g) || [summaryData.summary];
        for (const s of rawSentences) {
          if (s.trim()) addUnit(s.trim());
        }
      }
      (summaryData.key_points || []).forEach((kp) => addUnit(kp));
      (summaryData.important_facts || []).forEach((f) => addUnit(f));
    } else if (navMode === "linkedin" && linkedinData) {
      if (linkedinData.candidate_name) addUnit(`Candidate Profile: ${linkedinData.candidate_name}`);
      if (linkedinData.headline) addUnit(linkedinData.headline);
      if (linkedinData.executive_summary) {
        const rawSentences = linkedinData.executive_summary.match(/[^.!?]+[.!?]+(?:\s+|$)|[^.!?]+$/g) || [linkedinData.executive_summary];
        for (const s of rawSentences) {
          if (s.trim()) addUnit(s.trim());
        }
      }
      (linkedinData.experience_highlights || []).forEach((e) => addUnit(e));
    } else if (navMode === "resume" && resumeData) {
      if (resumeData.verdict) addUnit(`Resume Verdict: ${resumeData.verdict}. Score: ${resumeData.score || 0} out of 100.`);
      if (resumeData.how_is_resume) {
        const rawSentences = resumeData.how_is_resume.match(/[^.!?]+[.!?]+(?:\s+|$)|[^.!?]+$/g) || [resumeData.how_is_resume];
        for (const s of rawSentences) {
          if (s.trim()) addUnit(s.trim());
        }
      }
      (resumeData.strong_points || []).forEach((sp) => addUnit(`Strength: ${sp}`));
      (resumeData.weak_points || []).forEach((wp) => addUnit(`Area for Improvement: ${wp}`));
      (resumeData.suggestions || []).forEach((sg) => addUnit(`Suggestion: ${sg}`));
    }

    return units;
  }, [navMode, summaryData, linkedinData, resumeData]);

  // Reset audio queue if content changes
  useEffect(() => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    }
    audioCacheRef.current.clear();
    setIsPlaying(false);
    isPlayingRef.current = false;
    activeUnitIdxRef.current = 0;
    setActiveWordIdx(-1);
    setPlaybackCurrentTime(0);
  }, [navMode, summaryData?.title, linkedinData?.candidate_name, resumeData?.score]);

  // Fetch synthesis for a single sentence
  const fetchUnitAudio = async (unit: SpeechUnit, speed: number): Promise<CachedAudioUnit> => {
    const cached = audioCacheRef.current.get(unit.id);
    if (cached) return cached;

    const res = await fetch(`${BACKEND_URL}/api/voice/synthesize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: unit.text,
        speed: speed,
      }),
    });

    if (!res.ok) {
      throw new Error(`Voice synthesis failed (${res.status})`);
    }

    const data = await res.json();
    const audio = new Audio(data.audio_url);
    audio.playbackRate = speed;

    const result: CachedAudioUnit = {
      audio,
      words: data.words || [],
      duration: data.duration || 0,
    };

    audioCacheRef.current.set(unit.id, result);
    return result;
  };

  // Eager background pre-fetch
  useEffect(() => {
    if (speechUnits.length > 0 && !audioCacheRef.current.has(0)) {
      fetchUnitAudio(speechUnits[0], currentSpeed)
        .then((unit0) => {
          setPlaybackTotalDuration(unit0.duration * speechUnits.length);
          if (speechUnits.length > 1 && !audioCacheRef.current.has(1)) {
            fetchUnitAudio(speechUnits[1], currentSpeed).catch(() => {});
          }
        })
        .catch(() => {});
    }
  }, [speechUnits, currentSpeed]);

  const prefetchUpcoming = useCallback((fromIndex: number, speed: number) => {
    for (let i = fromIndex + 1; i <= fromIndex + 3 && i < speechUnits.length; i++) {
      if (!audioCacheRef.current.has(i)) {
        fetchUnitAudio(speechUnits[i], speed).catch(() => {});
      }
    }
  }, [speechUnits]);

  // Play unit
  const playUnit = useCallback(async (unitIdx: number) => {
    if (unitIdx >= speechUnits.length) {
      setIsPlaying(false);
      isPlayingRef.current = false;
      setActiveWordIdx(-1);
      activeUnitIdxRef.current = 0;
      setPlaybackCurrentTime(0);
      setStatusMessage("Playback complete.");
      return;
    }

    const unit = speechUnits[unitIdx];
    activeUnitIdxRef.current = unitIdx;

    try {
      const { audio, words } = await fetchUnitAudio(unit, currentSpeed);
      if (!isPlayingRef.current) return;

      currentAudioRef.current = audio;
      audio.playbackRate = currentSpeed;
      audio.currentTime = 0;

      const onTimeUpdate = () => {
        const time = audio.currentTime;
        setPlaybackCurrentTime(unitIdx * 4 + time);
        if (words.length > 0) {
          const localIdx = words.findIndex((w) => time >= w.start && time <= w.end);
          if (localIdx !== -1) {
            const globalIdx = unit.startWordIndex + localIdx;
            setActiveWordIdx(globalIdx);

            const activeEl = document.getElementById(`word-${globalIdx}`);
            if (activeEl && scrollRef.current) {
              const elRect = activeEl.getBoundingClientRect();
              const contRect = scrollRef.current.getBoundingClientRect();
              if (elRect.top < contRect.top + 40 || elRect.bottom > contRect.bottom - 40) {
                activeEl.scrollIntoView({ behavior: "smooth", block: "center" });
              }
            }
          }
        }
      };

      const onEnded = () => {
        audio.removeEventListener("timeupdate", onTimeUpdate);
        audio.removeEventListener("ended", onEnded);
        if (isPlayingRef.current) {
          playUnit(unitIdx + 1);
        }
      };

      audio.addEventListener("timeupdate", onTimeUpdate);
      audio.addEventListener("ended", onEnded);

      await audio.play();
      setIsPlaying(true);
      setStatusMessage("Kokoro Voice Active (am_fenrir)");

      prefetchUpcoming(unitIdx, currentSpeed);
    } catch (err: any) {
      console.error("Play error:", err);
      setIsPlaying(false);
      isPlayingRef.current = false;
    }
  }, [speechUnits, currentSpeed, prefetchUpcoming]);

  const handlePlayPause = async () => {
    if (isPlaying) {
      isPlayingRef.current = false;
      setIsPlaying(false);
      if (currentAudioRef.current) currentAudioRef.current.pause();
      setStatusMessage("Paused");
      return;
    }

    if (currentAudioRef.current && currentAudioRef.current.paused && currentAudioRef.current.currentTime > 0) {
      currentAudioRef.current.playbackRate = currentSpeed;
      await currentAudioRef.current.play();
      setIsPlaying(true);
      isPlayingRef.current = true;
      setStatusMessage("Kokoro Voice Active (am_fenrir)");
      return;
    }

    isPlayingRef.current = true;
    setIsPlaying(true);
    playUnit(activeUnitIdxRef.current);
  };

  const handleSpeedToggle = () => {
    const nextIdx = (speedIndex + 1) % SPEED_OPTIONS.length;
    setSpeedIndex(nextIdx);
    const newSpeed = SPEED_OPTIONS[nextIdx];
    if (currentAudioRef.current) {
      currentAudioRef.current.playbackRate = newSpeed;
    }
  };

  // Native Tauri Window Controls & Dragging
  const handleStartDrag = async (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    try {
      const { getCurrentWindow } = await import("@tauri-apps/api/window");
      await getCurrentWindow().startDragging();
    } catch {
      // Browser fallback
    }
  };

  const handleWindowMinimize = async () => {
    try {
      const { getCurrentWindow } = await import("@tauri-apps/api/window");
      await getCurrentWindow().minimize();
    } catch {
      // Browser fallback
    }
  };

  const handleWindowMaximize = async () => {
    try {
      const { getCurrentWindow } = await import("@tauri-apps/api/window");
      const appWindow = getCurrentWindow();
      await appWindow.toggleMaximize();
      setIsMaximized(await appWindow.isMaximized());
    } catch {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
        setIsMaximized(true);
      } else {
        document.exitFullscreen().catch(() => {});
        setIsMaximized(false);
      }
    }
  };

  const handleWindowClose = async () => {
    try {
      const { getCurrentWindow } = await import("@tauri-apps/api/window");
      await getCurrentWindow().close();
    } catch {
      window.close();
    }
  };

  // Open in Notepad (download formatted file)
  const handleOpenNotepad = () => {
    let content = "";
    if (navMode === "summariser" && summaryData) {
      content = `TITLE: ${summaryData.title}\nURL: ${summaryData.url}\nDATE: ${summaryData.date}\n\nEXECUTIVE SUMMARY:\n${summaryData.summary}\n\nKEY TAKEAWAYS:\n${(summaryData.key_points || []).map(p => `• ${p}`).join("\n")}\n\nIMPORTANT FACTS:\n${(summaryData.important_facts || []).map(f => `• ${f}`).join("\n")}`;
    } else if (navMode === "linkedin" && linkedinData) {
      content = `CANDIDATE: ${linkedinData.candidate_name}\nHEADLINE: ${linkedinData.headline}\nLOCATION: ${linkedinData.location}\n\nEXECUTIVE SUMMARY:\n${linkedinData.executive_summary}\n\nSKILLS:\n${(linkedinData.skills || []).join(", ")}\n\nEXPERIENCE:\n${(linkedinData.experience_highlights || []).join("\n")}`;
    } else if (navMode === "resume" && resumeData) {
      content = `RESUME EVALUATION\nSCORE: ${resumeData.score}/100 - ${resumeData.verdict}\nTARGET: ${resumeData.target_role}\n\nHOW IS THE RESUME:\n${resumeData.how_is_resume}\n\nSTRONG POINTS:\n${(resumeData.strong_points || []).map(s => `✓ ${s}`).join("\n")}\n\nWEAK POINTS:\n${(resumeData.weak_points || []).map(w => `⚠ ${w}`).join("\n")}\n\nSUGGESTIONS:\n${(resumeData.suggestions || []).map(s => `💡 ${s}`).join("\n")}`;
    }

    if (!content) return;
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `wreciser-${navMode}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Word-level interactive karaoke highlighter
  let globalWordCounter = 0;
  const renderInteractiveText = (text: string) => {
    if (!text) return null;
    const words = text.split(/(\s+)/);

    return words.map((token, i) => {
      if (/^\s+$/.test(token)) {
        return <span key={i}>{token}</span>;
      }

      const wordIdx = globalWordCounter++;
      const isCurrent = wordIdx === activeWordIdx;
      const isPast = activeWordIdx !== -1 && wordIdx < activeWordIdx;

      let wordClass = "transition-all duration-100 rounded px-[2px] ";
      if (isCurrent) {
        wordClass += "text-black font-bold bg-black/15 scale-[1.03] inline-block";
      } else if (isPast) {
        wordClass += "text-[#121212]";
      } else {
        wordClass += "text-[#595959]";
      }

      return (
        <span key={i} id={`word-${wordIdx}`} className={wordClass}>
          {token}
        </span>
      );
    });
  };

  // Format seconds to mm:ss
  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  };

  const progressPercent = playbackTotalDuration > 0
    ? Math.min((playbackCurrentTime / playbackTotalDuration) * 100, 100)
    : 0;

  return (
    // BORDERLESS FULL-BLEED WINDOW CONTAINER (Single window, true borderless from every side)
    <div className="h-screen w-screen overflow-hidden bg-[#f5f5f5] flex select-none font-sans text-[#121212]">
      
      {/* ─── 1. LEFT SIDEBAR (Borderless, sleek, 230px) ───────────────── */}
      <aside className="w-[230px] shrink-0 bg-[#f0f0f0] flex flex-col justify-between p-4">
        <div>
          {/* Logo & Brand (Draggable) */}
          <div
            data-tauri-drag-region
            onMouseDown={handleStartDrag}
            className="flex items-center gap-2.5 px-2 pt-2 pb-6 app-drag-region cursor-move select-none"
          >
            <img alt="Wrecziser" className="h-[22px] w-auto object-contain pointer-events-none select-none" src={imgMark} />
            <span className="font-semibold text-[22px] text-[#121212] tracking-tight leading-none pointer-events-none select-none">
              Wrecziser
            </span>
          </div>


          {/* Navigation Items */}
          <nav className="flex flex-col gap-2">
            <button
              onClick={() => handleNavChange("summariser")}
              className={`flex h-[48px] w-full items-center gap-3 rounded-[11px] px-3.5 transition duration-150 cursor-pointer ${
                navMode === "summariser"
                  ? "bg-[#121212] text-white shadow-xs"
                  : "bg-transparent text-[#121212] hover:bg-black/5"
              }`}
            >
              <img
                alt=""
                className={`size-[22px] ${navMode === "summariser" ? "brightness-0 invert" : ""}`}
                src={imgIcon}
              />
              <span className="font-semibold text-[14px] font-semibold">
                Summariser
              </span>
            </button>

            <button
              onClick={() => handleNavChange("resume")}
              className={`flex h-[48px] w-full items-center gap-3 rounded-[11px] px-3.5 transition duration-150 cursor-pointer ${
                navMode === "resume"
                  ? "bg-[#121212] text-white shadow-xs"
                  : "bg-transparent text-[#121212] hover:bg-black/5"
              }`}
            >
              <img
                alt=""
                className={`size-[22px] ${navMode === "resume" ? "brightness-0 invert" : ""}`}
                src={imgIcon}
              />
              <span className="font-medium text-[14px] font-medium">
                Resume Screener
              </span>
            </button>

            <button
              onClick={() => handleNavChange("linkedin")}
              className={`flex h-[48px] w-full items-center gap-3 rounded-[11px] px-3.5 transition duration-150 cursor-pointer ${
                navMode === "linkedin"
                  ? "bg-[#121212] text-white shadow-xs"
                  : "bg-transparent text-[#121212] hover:bg-black/5"
              }`}
            >
              <img
                alt=""
                className={`size-[22px] ${navMode === "linkedin" ? "brightness-0 invert" : ""}`}
                src={imgIcon1}
              />
              <span className="font-medium text-[14px] font-medium">
                LinkedIn Analyzer
              </span>
            </button>

            {/* Divider */}
            <div className="my-2 h-px w-full bg-[#b8b8b8]/40" />

            <button
              onClick={() => handleNavChange("history")}
              className={`flex h-[48px] w-full items-center gap-3 rounded-[11px] px-3.5 transition duration-150 cursor-pointer ${
                navMode === "history"
                  ? "bg-[#121212] text-white shadow-xs"
                  : "bg-transparent text-[#121212] hover:bg-black/5"
              }`}
            >
              <img
                alt=""
                className={`size-[22px] ${navMode === "history" ? "brightness-0 invert" : ""}`}
                src={imgIcon}
              />
              <span className="font-medium text-[14px] font-medium">
                History
              </span>
            </button>
          </nav>
        </div>

        {/* Footer brand indicator */}
        <div className="px-2 text-[11px] font-medium text-black/40">
          Wreciser Engine v2.0 · Local AI
        </div>
      </aside>

      {/* ─── 2. MAIN WORKSPACE (Center Canvas) ───────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0 p-6 overflow-hidden">
        {/* Workspace Title Header & Borderless Window Controls */}
        <div
          data-tauri-drag-region
          onMouseDown={handleStartDrag}
          className="mb-4 flex items-start justify-between gap-4 app-drag-region cursor-move select-none"
        >
          <div className="app-no-drag cursor-default" onMouseDown={(e) => e.stopPropagation()}>
            <h1 className="text-[28px] font-semibold text-[#121212]">
              {navMode === "summariser" && "Summariser"}
              {navMode === "resume" && "Resume Screener"}
              {navMode === "linkedin" && "LinkedIn Analyzer"}
              {navMode === "history" && "History"}
            </h1>
            <p className="text-[13px] font-normal text-[#595959] mt-0.5">
              {navMode === "summariser" && "Turn any page, article, or transcript into something useful."}
              {navMode === "resume" && "Screen and score candidate resumes across 4 criteria with AI."}
              {navMode === "linkedin" && "Extract and structure professional profiles for deeper evaluation."}
              {navMode === "history" && "View your previous briefings and saved extractions."}
            </p>
          </div>

          {/* Native Borderless Window Controls */}
          <div
            className="flex items-center gap-1.5 app-no-drag shrink-0 bg-white p-1 rounded-[12px] shadow-[0px_0px_5.8px_3px_rgba(0,0,0,0.06)]"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => {
                if (!document.fullscreenElement) {
                  document.documentElement.requestFullscreen().catch(() => {});
                } else {
                  document.exitFullscreen().catch(() => {});
                }
              }}
              title="Toggle Fullscreen"
              className="flex size-[32px] items-center justify-center rounded-[8px] text-[13px] text-[#595959] hover:bg-neutral-100 hover:text-black transition cursor-pointer"
            >
              ⛶
            </button>

            <button
              onClick={handleWindowMinimize}
              title="Minimize Window"
              className="flex size-[32px] items-center justify-center rounded-[8px] text-[14px] font-semibold text-[#595959] hover:bg-neutral-100 hover:text-black transition cursor-pointer"
            >
              —
            </button>

            <button
              onClick={handleWindowMaximize}
              title={isMaximized ? "Restore Window" : "Maximize Window"}
              className="flex size-[32px] items-center justify-center rounded-[8px] text-[14px] text-[#595959] hover:bg-neutral-100 hover:text-black transition cursor-pointer"
            >
              {isMaximized ? "🗗" : "□"}
            </button>

            <button
              onClick={handleWindowClose}
              title="Close Window"
              className="flex size-[32px] items-center justify-center rounded-[8px] text-[13px] font-semibold text-[#595959] hover:bg-red-500 hover:text-white transition cursor-pointer"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Dynamic Search / Input Bar (Borderless soft-shadow card) */}
        <div className="h-[56px] w-full bg-white rounded-[14px] shadow-[0px_0px_5.8px_3px_rgba(0,0,0,0.08)] flex items-center px-4 gap-3 shrink-0 mb-4">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleMainAction()}
            placeholder={
              navMode === "resume"
                ? "Paste candidate resume text or drop files here..."
                : "Type URL, text, or paste article to summarize..."
            }
            className="flex-1 bg-transparent text-[15px] font-normal text-[#121212] placeholder-[#9e9e9e] focus:outline-none"
          />

          <button
            type="button"
            disabled={isProcessing}
            onClick={() => {
              const fileInput = document.createElement("input");
              fileInput.type = "file";
              fileInput.accept = ".pdf,.docx,.doc,.txt,.md,.rtf";
              fileInput.onchange = async (e: any) => {
                const file = e.target.files?.[0];
                if (!file) return;

                setStatusMessage(`Reading ${file.name}...`);
                setIsProcessing(true);

                try {
                  const formData = new FormData();
                  formData.append("file", file);

                  if (navMode === "resume") {
                    // Extract text from PDF / Word and screen it with AI
                    setStatusMessage(`Extracting & screening ${file.name} with AI...`);
                    if (targetRole) {
                      formData.append("target_role", targetRole);
                    }
                    const res = await fetch(`${BACKEND_URL}/api/resume/upload-and-screen`, {
                      method: "POST",
                      body: formData,
                    });
                    if (!res.ok) {
                      const errData = await res.json().catch(() => ({}));
                      throw new Error(errData.detail || `Upload screening failed (${res.status})`);
                    }
                    const data = await res.json();
                    if (data?.extracted_text) {
                      setInputText(data.extracted_text);
                    }
                    if (data?.analysis) {
                      setResumeData(data.analysis);
                    }
                    setStatusMessage(`Screened ${file.name} successfully! (Score: ${data?.analysis?.score || 0}/100)`);
                  } else {
                    // Extract text from PDF / Word and populate input box for summarization
                    setStatusMessage(`Extracting text from ${file.name}...`);
                    const res = await fetch(`${BACKEND_URL}/api/document/extract`, {
                      method: "POST",
                      body: formData,
                    });
                    if (!res.ok) {
                      const errData = await res.json().catch(() => ({}));
                      throw new Error(errData.detail || `Extraction failed (${res.status})`);
                    }
                    const data = await res.json();
                    setInputText(data.text || "");
                    setStatusMessage(`Loaded ${file.name} (${data.length || 0} characters)`);
                  }
                } catch (err: any) {
                  console.error("Add files error:", err);
                  setStatusMessage(err.message || "Failed to process file.");
                } finally {
                  setIsProcessing(false);
                }
              };
              fileInput.click();
            }}
            className="flex h-[40px] items-center gap-2 rounded-[10px] bg-[#121212] px-3.5 cursor-pointer transition hover:bg-[#252525] active:scale-95 disabled:opacity-50"
          >
            <img alt="" className="size-[18px] object-contain brightness-100" src={imgSearchBar} />
            <span className="font-semibold text-[13px] font-semibold text-white whitespace-nowrap">
              {isProcessing ? "Processing..." : "Add files"}
            </span>
          </button>


          <button
            type="button"
            onClick={handleMainAction}
            disabled={isProcessing}
            className="flex h-[40px] items-center justify-center rounded-[10px] bg-[#121212] px-4 cursor-pointer transition hover:bg-[#252525] active:scale-95 disabled:opacity-50"
          >
            <span className="font-semibold text-[13px] font-semibold text-white whitespace-nowrap">
              {isProcessing
                ? "Processing..."
                : navMode === "resume"
                ? "Screen →"
                : "Summarise →"}
            </span>
          </button>
        </div>

        {/* Content Canvas Card (Borderless, modern shadow) */}
        <div className="flex-1 bg-white rounded-[14px] shadow-[0px_0px_5.8px_3px_rgba(0,0,0,0.08)] flex flex-col p-6 min-h-0 overflow-hidden">
          
          {/* ─── TAB VIEW: SUMMARISER ──────────────────────────────────── */}
          {navMode === "summariser" && (
            <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
              {/* Header Info */}
              <div className="pb-3 border-b border-black/5 shrink-0">
                <h2 className="font-semibold text-[20px] font-semibold text-[#121212] leading-snug">
                  {summaryData?.title || "No Summary Loaded"}
                </h2>
                <div className="flex items-center justify-between text-[12px] text-[#595959] mt-1.5">
                  {summaryData?.url ? (
                    <a
                      href={summaryData.url}
                      target="_blank"
                      rel="noreferrer"
                      className="underline truncate max-w-[500px] text-blue-600 hover:text-blue-800"
                    >
                      {summaryData.url}
                    </a>
                  ) : (
                    <span>Ready for input</span>
                  )}
                  <span className="text-[#9e9e9e] shrink-0">
                    {summaryData?.date || new Date().toLocaleDateString()}
                  </span>
                </div>

                {/* Sub-tabs */}
                <div className="flex items-center gap-2 mt-3">
                  <button
                    onClick={() => setActiveSubTab("summary")}
                    className={`h-[34px] px-4 rounded-[9px] text-[11px] font-medium transition cursor-pointer ${
                      activeSubTab === "summary"
                        ? "bg-[#121212] text-white"
                        : "bg-[#f5f5f5] text-[#121212] hover:bg-black/5"
                    }`}
                  >
                    Summary
                  </button>
                  <button
                    onClick={() => setActiveSubTab("keypoints")}
                    className={`h-[34px] px-4 rounded-[9px] text-[11px] font-medium transition cursor-pointer ${
                      activeSubTab === "keypoints"
                        ? "bg-[#121212] text-white"
                        : "bg-[#f5f5f5] text-[#121212] hover:bg-black/5"
                    }`}
                  >
                    Key Takeaways
                  </button>
                  <button
                    onClick={() => setActiveSubTab("facts")}
                    className={`h-[34px] px-4 rounded-[9px] text-[11px] font-medium transition cursor-pointer ${
                      activeSubTab === "facts"
                        ? "bg-[#121212] text-white"
                        : "bg-[#f5f5f5] text-[#121212] hover:bg-black/5"
                    }`}
                  >
                    Highlights & Facts
                  </button>
                </div>
              </div>

              {/* Scrollable Summary Body */}
              <div
                ref={scrollRef}
                className="flex-1 overflow-y-auto report-scroll pt-4 text-[14px] leading-relaxed text-[#595959] whitespace-pre-wrap"
              >
                {!summaryData?.summary ? (
                  <div className="h-[250px] flex flex-col items-center justify-center text-center text-black/40">
                    <p className="text-[16px] font-semibold text-black/70">No Summary Available</p>
                    <p className="text-[12px] max-w-[380px] mt-1">
                      Use the Wreciser extension in Chrome on any webpage or paste a URL above to summarize.
                    </p>
                  </div>
                ) : activeSubTab === "summary" ? (
                  <div>
                    <h3 className="font-semibold text-[15px] font-semibold text-[#121212] mb-2">
                      Executive Summary
                    </h3>
                    <p className="leading-relaxed text-[#4a4a4a]">
                      {renderInteractiveText(summaryData.summary)}
                    </p>

                    {summaryData.key_points && summaryData.key_points.length > 0 && (
                      <div className="mt-6">
                        <h3 className="font-semibold text-[15px] font-semibold text-[#121212] mb-2">
                          Key Takeaways
                        </h3>
                        <ul className="space-y-2.5">
                          {summaryData.key_points.map((kp, idx) => (
                            <li key={idx} className="flex items-start gap-2">
                              <span className="text-black font-bold mt-0.5">•</span>
                              <div>{renderInteractiveText(kp)}</div>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ) : activeSubTab === "keypoints" ? (
                  <div>
                    <h3 className="font-semibold text-[15px] font-semibold text-[#121212] mb-3">
                      Key Takeaways ({summaryData.key_points?.length || 0})
                    </h3>
                    <ul className="space-y-3">
                      {(summaryData.key_points || []).map((kp, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="text-black font-bold mt-0.5">•</span>
                          <div>{renderInteractiveText(kp)}</div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <div>
                    <h3 className="font-semibold text-[15px] font-semibold text-[#121212] mb-3">
                      Important Facts & Entities
                    </h3>
                    <ul className="space-y-2.5">
                      {(summaryData.important_facts || []).map((f, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="text-black font-bold mt-0.5">•</span>
                          <div>{renderInteractiveText(f)}</div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ─── TAB VIEW: RESUME SCREENER (4 CRITERIA) ─────────────────── */}
          {navMode === "resume" && (
            <div
              ref={scrollRef}
              className="flex-1 overflow-y-auto report-scroll text-[14px] leading-relaxed text-[#4a4a4a]"
            >
              {/* Target Role Banner */}
              <div className="flex items-center justify-between pb-4 mb-4 border-b border-black/5">
                <div>
                  <span className="text-[11px] font-bold uppercase tracking-wider text-black/50">
                    Target Role / Job Benchmark:
                  </span>
                  <p className="text-[18px] font-bold text-black">
                    {targetRole || "Senior Distributed Systems Engineer (Default)"}
                  </p>
                </div>
                {resumeData?.score !== undefined && (
                  <div className="flex items-center gap-3 bg-black/5 px-4 py-2 rounded-[12px]">
                    <span className="text-[12px] font-bold text-black/60 uppercase">ATS Score:</span>
                    <span className="text-[28px] font-bold text-black">{resumeData.score}/100</span>
                    <span className="rounded-[12px] bg-black px-3 py-1 text-[12px] font-semibold text-white">
                      {resumeData.verdict}
                    </span>
                  </div>
                )}
              </div>

              {!resumeData || resumeData.score === undefined ? (
                <div className="h-[250px] flex flex-col items-center justify-center text-center text-black/40">
                  <p className="text-[16px] font-semibold text-black/70">No Resume Screened Yet</p>
                  <p className="text-[12px] max-w-[380px] mt-1">
                    Paste resume content into the search bar above and click &quot;Screen →&quot; to evaluate across all 4 criteria.
                  </p>
                </div>
              ) : (
                <div className="space-y-6">
                  {/* 1. HOW IS THE RESUME */}
                  <section>
                    <h3 className="font-semibold text-[15px] font-semibold text-[#121212] mb-1.5 uppercase tracking-wide">
                      1. How is the Resume:
                    </h3>
                    <p className="leading-relaxed text-[#333]">
                      {renderInteractiveText(resumeData.how_is_resume)}
                    </p>
                  </section>

                  {/* 2. STRONG POINTS */}
                  <section>
                    <h3 className="font-semibold text-[15px] font-semibold text-emerald-800 mb-1.5 uppercase tracking-wide">
                      2. Strong Points:
                    </h3>
                    <ul className="space-y-2">
                      {resumeData.strong_points.map((sp, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="text-emerald-700 font-bold mt-0.5">✓</span>
                          <div>{renderInteractiveText(sp)}</div>
                        </li>
                      ))}
                    </ul>
                  </section>

                  {/* 3. WEAK POINTS */}
                  <section>
                    <h3 className="font-semibold text-[15px] font-semibold text-amber-800 mb-1.5 uppercase tracking-wide">
                      3. Weak Points & Gaps:
                    </h3>
                    <ul className="space-y-2">
                      {resumeData.weak_points.map((wp, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="text-amber-600 font-bold mt-0.5">⚠</span>
                          <div>{renderInteractiveText(wp)}</div>
                        </li>
                      ))}
                    </ul>
                  </section>

                  {/* 4. SUGGESTIONS */}
                  <section>
                    <h3 className="font-semibold text-[15px] font-semibold text-blue-900 mb-1.5 uppercase tracking-wide">
                      4. Suggestions:
                    </h3>
                    <ul className="space-y-2 mb-4">
                      {resumeData.suggestions.map((sg, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="text-blue-700 font-bold mt-0.5">💡</span>
                          <div>{renderInteractiveText(sg)}</div>
                        </li>
                      ))}
                    </ul>

                    {resumeData.rewrites && resumeData.rewrites.length > 0 && (
                      <div className="rounded-[12px] bg-blue-50/70 p-4 border border-blue-200">
                        <p className="text-[12px] font-bold text-blue-900 uppercase tracking-wide mb-2">
                          Google XYZ Bullet Rewrites:
                        </p>
                        <div className="space-y-3">
                          {resumeData.rewrites.map((rw, idx) => (
                            <div key={idx} className="bg-white p-3 rounded-[8px] border border-blue-200/60">
                              <p className="text-[12px] text-red-700 line-through">
                                Original: {rw.original}
                              </p>
                              <p className="text-[13px] font-semibold text-emerald-800 mt-1">
                                Improved: {rw.improved}
                              </p>
                              {rw.reason && (
                                <p className="text-[11px] text-black/60 italic mt-0.5">
                                  Why: {rw.reason}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </section>
                </div>
              )}
            </div>
          )}

          {/* ─── TAB VIEW: LINKEDIN ANALYZER ─────────────────────────────── */}
          {navMode === "linkedin" && (
            <div
              ref={scrollRef}
              className="flex-1 overflow-y-auto report-scroll text-[14px] leading-relaxed text-[#4a4a4a]"
            >
              {!linkedinData ? (
                <div className="h-[250px] flex flex-col items-center justify-center text-center text-black/40">
                  <p className="text-[16px] font-semibold text-black/70">No LinkedIn Profile Extracted</p>
                  <p className="text-[12px] max-w-[380px] mt-1">
                    Open any LinkedIn profile in Chrome and click &quot;LinkedIn Analyzer&quot; in the extension popup.
                  </p>
                </div>
              ) : (
                <div>
                  <div className="flex items-start justify-between pb-3 border-b border-black/5">
                    <div>
                      <h2 className="text-[22px] font-bold text-black">
                        {renderInteractiveText(linkedinData.candidate_name)}
                      </h2>
                      <p className="text-[14px] font-medium text-black/80 mt-0.5">
                        {renderInteractiveText(linkedinData.headline)}
                      </p>
                      {linkedinData.location && (
                        <p className="text-[12px] text-black/50 mt-0.5">{linkedinData.location}</p>
                      )}
                    </div>
                    <button
                      onClick={() => {
                        setTargetRole(linkedinData.headline || linkedinData.candidate_name);
                        setNavMode("resume");
                      }}
                      className="rounded-[10px] bg-black px-3.5 py-1.5 text-[12px] font-semibold text-white transition hover:bg-black/80"
                    >
                      Compare with Resume Screener →
                    </button>
                  </div>

                  <div className="mt-4">
                    <h3 className="font-semibold text-[15px] font-semibold text-[#121212] mb-1.5">
                      Executive Summary
                    </h3>
                    <p className="leading-relaxed">
                      {renderInteractiveText(linkedinData.executive_summary)}
                    </p>
                  </div>

                  {linkedinData.skills && linkedinData.skills.length > 0 && (
                    <div className="mt-5">
                      <h3 className="font-semibold text-[15px] font-semibold text-[#121212] mb-2">
                        Core Competencies & Skills
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {linkedinData.skills.map((skill, idx) => (
                          <span
                            key={idx}
                            className="bg-black/5 rounded-[8px] px-2.5 py-1 text-[12px] font-medium text-black"
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {linkedinData.experience_highlights && linkedinData.experience_highlights.length > 0 && (
                    <div className="mt-5">
                      <h3 className="font-semibold text-[15px] font-semibold text-[#121212] mb-2">
                        Experience Highlights
                      </h3>
                      <ul className="space-y-2">
                        {linkedinData.experience_highlights.map((exp, idx) => (
                          <li key={idx} className="flex items-start gap-2">
                            <span className="text-black font-bold mt-0.5">•</span>
                            <div>{renderInteractiveText(exp)}</div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* ─── TAB VIEW: HISTORY ───────────────────────────────────────── */}
          {navMode === "history" && (
            <div className="flex-1 flex flex-col items-center justify-center text-center text-black/40">
              <p className="text-[16px] font-semibold text-black/70">Session History</p>
              <p className="text-[12px] max-w-[340px] mt-1">
                Recent summaries and resume audits will be persisted here for quick re-examination.
              </p>
            </div>
          )}
        </div>
      </main>

      {/* ─── 3. RIGHT ACTION & PLAYBACK RAIL (285px, Borderless) ───────── */}
      <aside className="w-[285px] shrink-0 bg-white rounded-[14px] shadow-[0px_0px_5.8px_3px_rgba(0,0,0,0.08)] m-6 ml-0 p-5 flex flex-col justify-between overflow-y-auto report-scroll">
        <div className="flex flex-col gap-5">
          {/* Actions Section */}
          <div>
            <div data-tauri-drag-region onMouseDown={handleStartDrag} className="app-drag-region cursor-move select-none">
              <h3 className="font-semibold text-[14px] font-semibold text-[#121212] mb-3 pointer-events-none">
                Actions
              </h3>
            </div>
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={handleOpenNotepad}
                className="flex h-[42px] w-full items-center justify-center rounded-[10px] bg-[#f5f5f5] text-[12px] font-medium font-medium text-[#121212] cursor-pointer transition hover:bg-[#ebebeb] active:scale-98"
              >
                Open in Notepad
              </button>

              <button
                type="button"
                onClick={() => {
                  const url = summaryData?.url || linkedinData?.url;
                  if (url) window.open(url, "_blank");
                }}
                className="flex h-[42px] w-full items-center justify-center rounded-[10px] bg-[#121212] text-[12px] font-semibold font-semibold text-white cursor-pointer transition hover:bg-[#252525] active:scale-98"
              >
                Open in Wrecz
              </button>
            </div>
          </div>

          {/* Kokoro Voice Playback Controls */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-[14px] font-semibold text-[#121212]">
                Playback
              </h3>
              <span className="text-[11px] font-medium text-black/50">
                Kokoro (am_fenrir)
              </span>
            </div>

            <div className="flex items-center justify-between">
              {/* Play / Pause button */}
              <button
                type="button"
                onClick={handlePlayPause}
                title={isPlaying ? "Pause audio" : "Play briefing with Kokoro voice"}
                className="size-[42px] rounded-full bg-[#121212] text-white flex items-center justify-center text-[15px] cursor-pointer transition hover:bg-[#252525] active:scale-95 shadow-xs"
              >
                {isPlaying ? "⏸" : "▶"}
              </button>

              {/* Speed Toggle */}
              <button
                type="button"
                onClick={handleSpeedToggle}
                title="Toggle speed"
                className="h-[42px] px-3.5 rounded-[10px] border border-black/30 bg-white text-[12px] font-medium text-[#121212] cursor-pointer transition hover:bg-neutral-50 active:scale-95"
              >
                {currentSpeed}×
              </button>
            </div>

            {/* Progress Bar */}
            <div className="mt-4">
              <div className="h-[5px] w-full rounded-[3px] bg-[#b8b8b8]/40 overflow-hidden">
                <div
                  className="h-full bg-black transition-all duration-200"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
              <div className="flex justify-between items-center text-[11px] text-[#595959] mt-1.5 font-normal">
                <span>{formatTime(playbackCurrentTime)}</span>
                <span>{formatTime(playbackTotalDuration || 180)}</span>
              </div>
            </div>
          </div>

          {/* Related Topics Section */}
          <div>
            <h3 className="font-semibold text-[14px] font-semibold text-[#121212] mb-2.5">
              Related Topics
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {[
                "UI Design",
                "Notepad Apps",
                "Dark Mode",
                "Design Trends",
                "User Experience",
                "Apple Notes",
                "Minimalism",
                "ATS Scoring",
                "Full Stack",
              ].map((topic) => (
                <span
                  key={topic}
                  className="bg-[#f2f2f2] text-[#121212] text-[10px] font-medium px-2.5 py-1 rounded-[13px] hover:bg-black/10 cursor-default transition"
                >
                  {topic}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Status bar */}
        {statusMessage && (
          <div className="pt-4 border-t border-black/5 text-[11px] text-center font-medium text-black/60 truncate">
            {statusMessage}
          </div>
        )}
      </aside>
    </div>
  );
}
