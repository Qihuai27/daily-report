import React, { useState, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { 
  Search, 
  BookOpen, 
  Settings, 
  Plus, 
  Play, 
  CheckCircle, 
  Archive, 
  ChevronRight, 
  ExternalLink,
  Loader2,
  Calendar,
  Layers,
  FileText,
  Trash2,
  MoveUp,
  MoveDown,
  Cpu,
  Sparkles,
  RefreshCw,
  Github
} from 'lucide-react';

// --- API Helper ---
const api = axios.create({
  baseURL: 'http://localhost:8000/api'
});

// --- Types ---
interface Brief {
  id: string;
  name: string;
  date: string;
  size: number;
}

interface Paper {
  id: string;
  title_cn: string;
  title_en: string;
  url: string;
  checked: boolean;
  score: number;
  tags: string[];
  analysis: Record<string, string>; // Dynamic analysis content
}

interface Status {
  status: 'idle' | 'busy' | 'error';
  task: string | null;
  message: string;
  logs: string[];
  progress_current?: number;
  progress_total?: number;
  progress_stage?: string | null;
}

interface Config {
  llm_provider: 'openai' | 'anthropic' | 'gemini' | 'ollama';
  
  openai_model: string;
  openai_base_url: string;
  has_openai_key: boolean;
  
  anthropic_model: string;
  anthropic_base_url: string;
  has_anthropic_key: boolean;
  
  gemini_model: string;
  gemini_base_url: string;
  has_gemini_key: boolean;

  ollama_base_url: string;
  ollama_model: string;
  
  zotero_user_id: string;
  has_zotero_key: boolean;
  zotero_collection: string;
  search_queries: string[];
  use_pdf_fulltext: boolean;
  pdf_body_max_pages: number;
  pdf_body_max_tokens: number;
  pdf_cache_ttl_days?: number;
  use_arxiv_source: boolean;
  arxiv_source_min_chars?: number;
  arxiv_source_max_mb?: number;
  arxiv_source_ttl_days?: number;
  arxiv_source_keep_archive?: boolean;
}

interface ScheduleConfig {
  enabled: boolean;
  hour: number;
  minute: number;
  queries: string[];
  max_results: number;
  use_llm: boolean;
}

interface TemplateItem {
  key: string;
  label: string;
  prompt: string;
}

// --- Components ---

export default function App() {
  const [activeTab, setActiveTab] = useState<'fetch' | 'briefs' | 'settings'>('fetch');
  const [status, setStatus] = useState<Status>({ status: 'idle', task: null, message: '', logs: [] });
  const [config, setConfig] = useState<Config | null>(null);
  const [schedule, setSchedule] = useState<ScheduleConfig | null>(null);
  const [template, setTemplate] = useState<TemplateItem[]>([]);

  // Poll status
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await api.get('/status');
        setStatus(res.data);
      } catch (e) {
        console.error("Status check failed", e);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // Fetch initial config
  useEffect(() => {
    api.get('/config').then(res => setConfig(res.data));
    api.get('/schedule').then(res => setSchedule(res.data));
    api.get('/template').then(res => setTemplate(res.data.template));
  }, []);

  const progressPercent = status.progress_total
    ? Math.min(100, Math.round((status.progress_current || 0) / status.progress_total * 100))
    : 0;

  return (
    <div className="min-h-screen bg-zinc-50 text-zinc-900 font-sans selection:bg-indigo-100 selection:text-indigo-900">
      {/* Sidebar */}
      <div className="fixed left-0 top-0 h-full w-72 bg-white/80 backdrop-blur-xl border-r border-zinc-200/60 p-6 flex flex-col shadow-[4px_0_24px_-12px_rgba(0,0,0,0.05)] z-50">
        <div className="flex items-center gap-3 mb-12 px-2">
          <div className="bg-gradient-to-br from-indigo-600 to-violet-600 p-2 rounded-xl text-white shadow-lg shadow-indigo-200">
            <Sparkles size={20} fill="currentColor" className="text-white/90" />
          </div>
          <div>
            <h1 className="font-bold text-lg tracking-tight text-zinc-900">Academic Flow</h1>
            <p className="text-[10px] text-zinc-400 font-medium tracking-wide uppercase">Research Assistant</p>
          </div>
        </div>

        <nav className="flex-1 space-y-2">
          <NavItem 
            active={activeTab === 'fetch'} 
            onClick={() => setActiveTab('fetch')}
            icon={<Search size={18} />}
            label="情报抓取"
            desc="Fetch & Analyze"
          />
          <NavItem 
            active={activeTab === 'briefs'} 
            onClick={() => setActiveTab('briefs')}
            icon={<BookOpen size={18} />}
            label="简报阅读室"
            desc="Library & Archive"
          />
          <NavItem 
            active={activeTab === 'settings'} 
            onClick={() => setActiveTab('settings')}
            icon={<Settings size={18} />}
            label="偏好设置"
            desc="Configuration"
          />
        </nav>

        {/* Status indicator at bottom */}
        <div className="mt-auto">
          <div className={`p-4 rounded-2xl border transition-all duration-300 ${
            status.status === 'busy' 
              ? 'bg-indigo-50/50 border-indigo-100 shadow-sm' 
              : 'bg-zinc-50 border-zinc-100'
          }`}>
            <div className="flex items-center gap-3 mb-2">
              <div className={`relative flex h-3 w-3`}>
                {status.status === 'busy' && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>}
                <span className={`relative inline-flex rounded-full h-3 w-3 ${
                  status.status === 'busy' ? 'bg-indigo-500' : 
                  status.status === 'error' ? 'bg-red-500' : 'bg-emerald-500'
                }`}></span>
              </div>
              <span className={`text-xs font-bold uppercase tracking-wider ${
                status.status === 'busy' ? 'text-indigo-600' : 
                status.status === 'error' ? 'text-red-600' : 'text-emerald-600'
              }`}>{status.status === 'idle' ? 'System Ready' : status.status}</span>
            </div>
            
            <p className="text-xs text-zinc-500 line-clamp-2 h-8 leading-4">{status.message || "Waiting for command..."}</p>
            
            {status.status === 'busy' && (
              <div className="mt-3 space-y-1.5">
                <div className="flex justify-between text-[10px] text-indigo-400 font-medium">
                  <span className="uppercase">{status.progress_stage || "Processing"}</span>
                  <span>{progressPercent}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-indigo-100 overflow-hidden">
                  <div className="h-full bg-indigo-500 transition-all duration-300 ease-out" style={{ width: `${progressPercent}%` }} />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="ml-72 p-8 lg:p-12 max-w-7xl mx-auto min-h-screen">
        {activeTab === 'fetch' && <FetchView config={config} status={status} />}
        {activeTab === 'briefs' && <BriefsView template={template} config={config} />}
        {activeTab === 'settings' && (
          <SettingsView
            initialConfig={config}
            initialSchedule={schedule}
            initialTemplate={template}
            onSave={() => api.get('/config').then(res => setConfig(res.data))}
            onScheduleSave={() => api.get('/schedule').then(res => setSchedule(res.data))}
            onTemplateSave={() => api.get('/template').then(res => setTemplate(res.data.template))}
          />
        )}
      </main>
    </div>
  );
}

function NavItem({ active, onClick, icon, label, desc }: { active: boolean, onClick: () => void, icon: React.ReactNode, label: string, desc: string }) {
  return (
    <button 
      onClick={onClick}
      className={`group w-full flex items-center gap-4 px-4 py-3.5 rounded-xl text-left transition-all duration-200 ${
        active 
          ? 'bg-zinc-900 text-white shadow-lg shadow-zinc-200' 
          : 'text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900'
      }`}
    >
      <div className={`${active ? 'text-indigo-300' : 'text-zinc-400 group-hover:text-zinc-600'}`}>
        {icon}
      </div>
      <div>
        <div className={`text-sm font-semibold ${active ? 'text-white' : 'text-zinc-700 group-hover:text-zinc-900'}`}>{label}</div>
        <div className={`text-[10px] font-medium tracking-wide ${active ? 'text-zinc-400' : 'text-zinc-400 group-hover:text-zinc-500'}`}>{desc}</div>
      </div>
      {active && <ChevronRight size={14} className="ml-auto text-zinc-500" />}
    </button>
  );
}

// --- View: Fetch ---
function FetchView({ config, status }: { config: Config | null, status: Status }) {
  const [queries, setQueries] = useState<string[]>(["LLM", "RAG"]);
  const [newQuery, setNewQuery] = useState("");
  const [maxResults, setMaxResults] = useState(10);
  const [useLlm, setUseLlm] = useState(true);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  useEffect(() => {
    if (config?.search_queries?.length) {
      setQueries(config.search_queries);
    }
  }, [config]);

  const addQuery = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) return;
    if (queries.includes(trimmed)) {
      setNewQuery("");
      return;
    }
    setQueries([...queries, trimmed]);
    setNewQuery("");
  };

  const handleStart = async () => {
    try {
      await api.post('/fetch', {
        queries,
        max_results: maxResults,
        use_llm: useLlm,
        date_from: dateFrom || null,
        date_to: dateTo || null
      });
    } catch (e) {
      alert("启动任务失败，请检查后端服务是否运行");
    }
  };

  return (
    <div className="space-y-10 animate-slide-up">
      <header className="max-w-2xl">
        <h2 className="text-3xl font-bold tracking-tight text-zinc-900 mb-3">情报抓取中心</h2>
        <p className="text-zinc-500 text-lg leading-relaxed">
          配置自定义搜索关键词，从 ArXiv 实时抓取并深度分析最新科研动态。
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Configuration */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Query Card */}
          <div className="bg-white rounded-3xl p-8 border border-zinc-100 shadow-sm hover:shadow-md transition-shadow">
            <div className="flex items-center gap-3 mb-6">
              <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
                <Layers size={20} />
              </div>
              <h3 className="font-bold text-lg text-zinc-800">搜索关键词</h3>
            </div>
            
            <div className="flex flex-wrap gap-2.5 mb-6 min-h-[80px] content-start bg-zinc-50/50 p-4 rounded-xl border border-zinc-100/50">
              {queries.map((q, i) => (
                <span key={i} className="pl-3 pr-2 py-1.5 bg-white border border-zinc-200 text-zinc-700 rounded-lg text-sm font-medium flex items-center gap-2 shadow-sm group">
                  {q}
                  <button onClick={() => setQueries(queries.filter((_, idx) => idx !== i))} className="text-zinc-300 hover:text-red-500 hover:bg-red-50 rounded p-0.5 transition-colors">
                    <Trash2 size={12} />
                  </button>
                </span>
              ))}
              <div className="flex items-center group relative">
                <Plus size={16} className="absolute left-3 text-zinc-400 group-focus-within:text-indigo-500" />
                <input 
                  value={newQuery}
                  onChange={e => setNewQuery(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && addQuery(newQuery)}
                  placeholder="输入关键词并回车..."
                  className="pl-9 pr-3 py-1.5 bg-transparent border-b-2 border-zinc-200 focus:border-indigo-500 outline-none text-sm w-40 focus:w-64 transition-all text-zinc-700 placeholder:text-zinc-400"
                />
              </div>
            </div>
          </div>

          {/* Settings Card */}
          <div className="bg-white rounded-3xl p-8 border border-zinc-100 shadow-sm hover:shadow-md transition-shadow">
             <div className="flex items-center gap-3 mb-6">
              <div className="p-2 bg-violet-50 text-violet-600 rounded-lg">
                <Settings size={20} />
              </div>
              <h3 className="font-bold text-lg text-zinc-800">抓取参数</h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
               {/* Date Range */}
               <div className="space-y-4">
                <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                  <Calendar size={14} /> 时间范围
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <span className="text-[10px] text-zinc-400 font-medium ml-1">START DATE</span>
                    <input
                      type="date"
                      value={dateFrom}
                      onChange={e => setDateFrom(e.target.value)}
                      className="w-full bg-zinc-50 hover:bg-zinc-100 border border-zinc-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 ring-indigo-500/20 focus:border-indigo-500 transition-all text-zinc-600"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <span className="text-[10px] text-zinc-400 font-medium ml-1">END DATE</span>
                    <input
                      type="date"
                      value={dateTo}
                      onChange={e => setDateTo(e.target.value)}
                      className="w-full bg-zinc-50 hover:bg-zinc-100 border border-zinc-200 rounded-xl px-3 py-2 text-sm outline-none focus:ring-2 ring-indigo-500/20 focus:border-indigo-500 transition-all text-zinc-600"
                    />
                  </div>
                </div>
              </div>

               {/* Limits & AI */}
               <div className="space-y-6">
                 <div className="space-y-3">
                   <div className="flex justify-between items-center">
                     <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">论文数量上限</label>
                     <span className="text-xs font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-md">{maxResults} 篇</span>
                   </div>
                   <input 
                      type="range" min="1" max="100" value={maxResults} 
                      onChange={e => setMaxResults(parseInt(e.target.value))}
                      className="w-full h-2 bg-zinc-100 rounded-lg appearance-none cursor-pointer accent-indigo-600"
                    />
                 </div>

                 <div className="flex items-center justify-between p-3 border border-zinc-100 rounded-xl bg-zinc-50/50">
                    <div>
                      <label className="text-sm font-bold text-zinc-700">启用 LLM 深度分析</label>
                      <p className="text-xs text-zinc-400 mt-0.5">自动生成中文摘要、评分及结构化笔记</p>
                    </div>
                    <div className="relative inline-block w-11 h-6 align-middle select-none transition duration-200 ease-in">
                        <input 
                          type="checkbox" 
                          name="toggle" 
                          id="toggle" 
                          checked={useLlm}
                          onChange={e => setUseLlm(e.target.checked)}
                          className="toggle-checkbox absolute block w-5 h-5 rounded-full bg-white border-4 appearance-none cursor-pointer transition-transform duration-200 ease-in-out checked:translate-x-full checked:border-indigo-600"
                        />
                        <label htmlFor="toggle" className={`toggle-label block overflow-hidden h-6 rounded-full cursor-pointer transition-colors duration-200 ${useLlm ? 'bg-indigo-600' : 'bg-zinc-300'}`}></label>
                    </div>
                 </div>
               </div>
            </div>
          </div>
        </div>

        {/* Right Column: Action */}
        <div className="lg:col-span-1">
          <div className="sticky top-8">
            <div className="bg-gradient-to-br from-zinc-900 to-zinc-800 rounded-3xl p-8 text-white shadow-xl shadow-zinc-200 flex flex-col items-center text-center h-full border border-zinc-700/50">
              <div className="mb-6 p-4 bg-white/10 rounded-full backdrop-blur-sm">
                <Play size={32} fill="currentColor" className="text-white" />
              </div>
              <h3 className="text-2xl font-bold mb-2">准备就绪</h3>
              <p className="text-zinc-400 text-sm mb-8 leading-relaxed">
                将根据配置抓取 {queries.length} 个关键词下的最新论文，预计处理上限为 {maxResults} 篇。
              </p>
              
              <button 
                onClick={handleStart}
                disabled={status.status === 'busy'}
                className="w-full py-4 bg-white text-zinc-900 rounded-xl font-bold hover:bg-indigo-50 hover:text-indigo-700 transition-all active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-black/20 flex items-center justify-center gap-2"
              >
                 {status.status === 'busy' ? (
                   <>
                    <Loader2 className="animate-spin" /> 正在运行...
                   </>
                 ) : (
                   <>开始抓取任务</>
                 )}
              </button>
            </div>
            
            <div className="mt-6 bg-white/50 border border-zinc-200 rounded-2xl p-6 backdrop-blur-sm">
               <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider mb-4">使用提示</h4>
               <ul className="text-sm text-zinc-600 space-y-2 list-disc pl-4">
                 <li>首次运行会自动下载相关模型配置。</li>
                 <li>抓取完成后，请前往「简报阅读室」查看。</li>
                 <li>支持配置 Zotero 自动同步。</li>
               </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- View: Briefs ---
function BriefsView({ template, config }: { template: TemplateItem[]; config: Config | null }) {
  const [briefs, setBriefs] = useState<Brief[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [detail, setDetail] = useState<{header: string, papers: Paper[]} | null>(null);
  const [loading, setLoading] = useState(false);
  const [collection, setCollection] = useState<string>('');

  useEffect(() => {
    api.get('/briefs').then(res => setBriefs(res.data));
  }, []);

  useEffect(() => {
    if (config?.zotero_collection) {
      setCollection(config.zotero_collection);
    }
  }, [config?.zotero_collection]);

  const loadDetail = async (filename: string) => {
    setLoading(true);
    setSelectedFile(filename);
    try {
      const res = await api.get(`/briefs/${filename}`);
      setDetail(res.data);
    } finally {
      setLoading(false);
    }
  };

  const togglePaper = async (paperId: string, current: boolean) => {
    await api.post(`/briefs/${selectedFile}/check`, null, { params: { paper_id: paperId, checked: !current } });
    setDetail(prev => {
      if(!prev) return prev;
      return {
        ...prev,
        papers: prev.papers.map(p => p.id === paperId ? { ...p, checked: !current } : p)
      };
    });
  };

  const startArchive = async () => {
    if(!selectedFile) return;
    await api.post('/archive', { filename: selectedFile, collection: collection || undefined });
    alert("归档任务已提交！请关注左下角任务状态。");
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100vh-6rem)] animate-fade-in">
      {/* Sidebar List */}
      <div className="lg:col-span-3 flex flex-col h-full">
         <div className="flex items-center gap-2 mb-4 px-1">
            <BookOpen size={20} className="text-zinc-400" />
            <h2 className="text-xl font-bold text-zinc-800">历史简报</h2>
         </div>
         <div className="flex-1 overflow-y-auto pr-2 space-y-3 custom-scrollbar">
          {briefs.map(b => (
            <button 
              key={b.id}
              onClick={() => loadDetail(b.id)}
              className={`w-full text-left p-4 rounded-2xl border transition-all duration-200 group relative overflow-hidden ${
                selectedFile === b.id 
                  ? 'border-indigo-600 bg-indigo-600 text-white shadow-lg shadow-indigo-200' 
                  : 'border-white bg-white hover:border-zinc-200 text-zinc-600 shadow-sm'
              }`}
            >
              <div className="relative z-10">
                <div className={`text-sm font-bold mb-1 ${selectedFile === b.id ? 'text-white' : 'text-zinc-800'}`}>{b.name}</div>
                <div className={`text-[10px] flex justify-between uppercase tracking-wider font-medium ${selectedFile === b.id ? 'text-indigo-200' : 'text-zinc-400'}`}>
                  <span className="flex items-center gap-1"><Calendar size={10} /> {b.date}</span>
                  <span>{(b.size / 1024).toFixed(1)} KB</span>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Main Detail Area */}
      <div className="lg:col-span-9 flex flex-col h-full bg-white rounded-3xl border border-zinc-200/60 shadow-xl shadow-zinc-100 overflow-hidden relative">
        {selectedFile ? (
          <>
            {/* Header */}
            <div className="px-8 py-5 border-b border-zinc-100 flex justify-between items-center bg-white/80 backdrop-blur-md sticky top-0 z-20">
              <div>
                <h3 className="font-bold text-zinc-900 text-lg flex items-center gap-2">
                  {selectedFile}
                  <span className="px-2 py-0.5 rounded-full bg-zinc-100 text-zinc-500 text-xs font-medium">{detail?.papers.length || 0} items</span>
                </h3>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 bg-zinc-50 border border-zinc-200 rounded-lg px-3 py-1.5">
                  <span className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Collection</span>
                  <input
                    value={collection}
                    onChange={e => setCollection(e.target.value)}
                    placeholder="ArXiv Daily"
                    className="w-32 bg-transparent text-xs font-medium text-zinc-700 outline-none placeholder:text-zinc-300"
                  />
                </div>
                <button 
                  onClick={startArchive}
                  className="bg-zinc-900 hover:bg-zinc-800 text-white px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wide flex items-center gap-2 transition-all shadow-md active:scale-95"
                >
                  <Archive size={14} /> Sync to Zotero
                </button>
              </div>
            </div>
            
            {/* Content List */}
            <div className="flex-1 overflow-y-auto p-8 space-y-8 bg-zinc-50/30 scroll-smooth">
              {loading ? (
                <div className="flex flex-col items-center justify-center h-full text-zinc-400 gap-4">
                  <Loader2 className="animate-spin text-indigo-500" size={32} />
                  <span className="text-sm font-medium animate-pulse">Analysing content...</span>
                </div>
              ) : (
                detail?.papers.map((p, idx) => (
                  <div key={p.id} className={`group relative p-6 rounded-2xl border transition-all duration-300 ${
                    p.checked 
                      ? 'border-indigo-200 bg-indigo-50/30 shadow-sm' 
                      : 'border-zinc-200 bg-white hover:shadow-md hover:border-zinc-300'
                  }`}>
                    {/* Floating Index */}
                    <div className="absolute -left-3 -top-3 w-8 h-8 rounded-full bg-white border border-zinc-200 flex items-center justify-center text-xs font-bold text-zinc-400 shadow-sm">
                      {idx + 1}
                    </div>

                    <div className="flex justify-between items-start gap-6 mb-5 pl-2">
                      <div className="flex-1">
                        <div className="flex flex-wrap items-center gap-3 mb-2">
                           <span className={`px-2 py-1 rounded-md text-xs font-bold flex items-center gap-1 ${
                             p.score >= 8 ? 'bg-emerald-100 text-emerald-700' : 
                             p.score >= 5 ? 'bg-amber-100 text-amber-700' : 'bg-zinc-100 text-zinc-500'
                           }`}>
                             <Sparkles size={10} fill="currentColor" /> {p.score} / 10
                           </span>
                           <h4 className="text-lg font-bold text-zinc-900 leading-tight">{p.title_cn}</h4>
                        </div>
                        <div className="text-sm text-zinc-500 font-medium font-serif leading-relaxed pl-1 border-l-2 border-zinc-200 ml-1">
                          {p.title_en}
                        </div>
                      </div>
                      
                      <button 
                        onClick={() => togglePaper(p.id, p.checked)}
                        className={`flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center transition-all ${
                          p.checked 
                            ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-200 scale-105' 
                            : 'bg-zinc-100 text-zinc-300 hover:bg-zinc-200 hover:text-zinc-500'
                        }`}
                      >
                        <CheckCircle size={24} fill={p.checked ? "currentColor" : "none"} />
                      </button>
                    </div>

                    {/* Dynamic Analysis Content */}
                    <div className="space-y-6 pl-2">
                      {template.length > 0 ? (
                        template.map(item => (
                          <div key={item.key} className="bg-zinc-50/80 rounded-xl p-4 border border-zinc-100/50">
                            <h5 className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest mb-2 flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400"></span>
                              {item.label}
                            </h5>
                            <div className="text-sm text-zinc-700 leading-7 prose prose-zinc prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0">
                              <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                {p.analysis[item.key] || p.analysis[item.label] || "_No analysis content_"}
                              </ReactMarkdown>
                            </div>
                          </div>
                        ))
                      ) : (
                         Object.entries(p.analysis).map(([k, v]) => (
                          <div key={k} className="bg-zinc-50 rounded-xl p-4 border border-zinc-100">
                             <h5 className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest mb-2">{k}</h5>
                             <div className="text-sm text-zinc-700 leading-relaxed prose prose-zinc prose-sm max-w-none">
                                <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                                  {v}
                                </ReactMarkdown>
                             </div>
                          </div>
                        ))
                      )}
                    </div>
                    
                    <div className="flex items-center justify-between pt-4 mt-4 border-t border-dashed border-zinc-200 pl-2">
                      <div className="flex gap-2">
                        {p.tags.slice(0, 4).map(t => (
                          <span key={t} className="text-[10px] bg-white border border-zinc-200 text-zinc-500 px-2 py-1 rounded-md font-medium">#{t}</span>
                        ))}
                      </div>
                      <a href={p.url} target="_blank" className="flex items-center gap-1 text-xs font-bold text-indigo-600 hover:text-indigo-800 transition-colors bg-indigo-50 px-3 py-1.5 rounded-lg">
                        View Paper <ExternalLink size={12} />
                      </a>
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-zinc-300 gap-6">
            <div className="bg-zinc-50 p-6 rounded-full">
              <BookOpen size={48} strokeWidth={1} />
            </div>
            <p className="text-sm font-medium text-zinc-400">请从左侧列表选择一份简报以开始阅读</p>
          </div>
        )}
      </div>
    </div>
  );
}

// --- View: Settings ---
function SettingsView({
  initialConfig,
  initialSchedule,
  initialTemplate,
  onSave,
  onScheduleSave,
  onTemplateSave
}: {
  initialConfig: Config | null,
  initialSchedule: ScheduleConfig | null,
  initialTemplate: TemplateItem[],
  onSave: () => void,
  onScheduleSave: () => void,
  onTemplateSave: () => void
}) {
  const [form, setForm] = useState<Partial<Config>>({});
  
  // Initialize form with API data
  useEffect(() => {
    if (!initialConfig) return;
    setForm({
      llm_provider: initialConfig.llm_provider,
      openai_api_key: '', 
      openai_base_url: initialConfig.openai_base_url,
      openai_model: initialConfig.openai_model,
      
      anthropic_api_key: '',
      anthropic_base_url: initialConfig.anthropic_base_url,
      anthropic_model: initialConfig.anthropic_model,
      
      gemini_api_key: '',
      gemini_base_url: initialConfig.gemini_base_url,
      gemini_model: initialConfig.gemini_model,

      ollama_base_url: initialConfig.ollama_base_url,
      ollama_model: initialConfig.ollama_model,
      
      zotero_user_id: initialConfig.zotero_user_id,
      zotero_api_key: '',
      use_pdf_fulltext: initialConfig.use_pdf_fulltext,
      pdf_body_max_pages: initialConfig.pdf_body_max_pages,
      pdf_body_max_tokens: initialConfig.pdf_body_max_tokens,
      pdf_cache_ttl_days: initialConfig.pdf_cache_ttl_days,
      use_arxiv_source: initialConfig.use_arxiv_source,
      arxiv_source_ttl_days: initialConfig.arxiv_source_ttl_days,
    });
  }, [initialConfig]);

  // Schedule state
  const [scheduleForm, setScheduleForm] = useState({
    enabled: initialSchedule?.enabled ?? true,
    hour: initialSchedule?.hour ?? 8,
    minute: initialSchedule?.minute ?? 0,
    queries: (initialSchedule?.queries || []).join(", "),
    max_results: initialSchedule?.max_results ?? 30,
    use_llm: initialSchedule?.use_llm ?? true,
  });
  
  // Template state
  const [templateForm, setTemplateForm] = useState<TemplateItem[]>(initialTemplate);

  useEffect(() => {
    if (!initialSchedule) return;
    setScheduleForm({
      enabled: initialSchedule.enabled,
      hour: initialSchedule.hour,
      minute: initialSchedule.minute,
      queries: (initialSchedule.queries || []).join(", "),
      max_results: initialSchedule.max_results,
      use_llm: initialSchedule.use_llm,
    });
  }, [initialSchedule]);
  
  useEffect(() => {
     setTemplateForm(initialTemplate);
  }, [initialTemplate]);

  const handleSave = async () => {
    await api.post('/config', form);
    onSave();
    alert("系统配置已保存");
  };

  const handlePdfSave = async () => {
    await api.post('/config', {
      use_pdf_fulltext: form.use_pdf_fulltext,
      pdf_body_max_pages: form.pdf_body_max_pages,
      pdf_body_max_tokens: form.pdf_body_max_tokens,
      pdf_cache_ttl_days: form.pdf_cache_ttl_days,
      use_arxiv_source: form.use_arxiv_source,
      arxiv_source_ttl_days: form.arxiv_source_ttl_days,
    });
    onSave();
    alert("PDF 处理策略已更新");
  };

  const handleScheduleSave = async () => {
    const queries = scheduleForm.queries.split(",").map(q => q.trim()).filter(Boolean);
    await api.post('/schedule', { ...scheduleForm, queries });
    onScheduleSave();
    alert("自动调度任务已更新");
  };
  
  const handleTemplateSave = async () => {
      await api.post('/template', { template: templateForm });
      onTemplateSave();
      alert("分析模板已更新");
  };

  // Template helpers
  const addTemplateItem = () => setTemplateForm([...templateForm, { key: `field_${Date.now()}`, label: "新分析点", prompt: "" }]);
  const removeTemplateItem = (index: number) => {
      const next = [...templateForm]; next.splice(index, 1); setTemplateForm(next);
  };
  const updateTemplateItem = (index: number, field: keyof TemplateItem, value: string) => {
      const next = [...templateForm]; next[index] = { ...next[index], [field]: value }; setTemplateForm(next);
  };
  const moveItem = (index: number, direction: -1 | 1) => {
      if (index + direction < 0 || index + direction >= templateForm.length) return;
      const next = [...templateForm]; 
      [next[index], next[index + direction]] = [next[index + direction], next[index]];
      setTemplateForm(next);
  };

  const SectionTitle = ({ icon, title, desc }: { icon: React.ReactNode, title: string, desc?: string }) => (
    <div className="mb-6">
      <h3 className="font-bold text-lg text-zinc-900 flex items-center gap-2">
        <div className="p-1.5 bg-zinc-100 rounded-lg text-zinc-500">{icon}</div>
        {title}
      </h3>
      {desc && <p className="text-sm text-zinc-500 ml-9 mt-1">{desc}</p>}
    </div>
  );

  return (
    <div className="max-w-4xl mx-auto space-y-10 pb-20 animate-slide-up">
      <header>
        <h2 className="text-3xl font-bold tracking-tight text-zinc-900 mb-2">系统设置</h2>
        <p className="text-zinc-500 text-lg">管理 API 密钥、自动化规则及内容生成模板。</p>
      </header>

      {/* LLM Config */}
      <section className="bg-white rounded-3xl p-8 border border-zinc-200 shadow-sm relative overflow-hidden">
        <div className="absolute top-0 right-0 p-32 bg-indigo-50/50 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none"></div>
        <SectionTitle icon={<Cpu size={18} />} title="模型服务 (LLM Provider)" desc="选择并配置用于论文分析的大语言模型。" />
        
        <div className="space-y-6 relative z-10">
          <div className="flex flex-col gap-2">
            <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">选择服务商</label>
            <div className="flex gap-4">
              {['openai', 'anthropic', 'gemini', 'ollama'].map(p => (
                <label key={p} className={`flex-1 cursor-pointer border rounded-xl p-4 flex flex-col items-center gap-2 transition-all ${
                  form.llm_provider === p 
                    ? 'border-indigo-600 bg-indigo-50 text-indigo-700 ring-1 ring-indigo-600' 
                    : 'border-zinc-200 hover:border-zinc-300 hover:bg-zinc-50'
                }`}>
                  <input 
                    type="radio" 
                    name="provider" 
                    value={p} 
                    checked={form.llm_provider === p} 
                    onChange={e => setForm({...form, llm_provider: e.target.value as any})}
                    className="hidden" 
                  />
                  <span className="capitalize font-bold">{p}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-6 bg-zinc-50/50 rounded-2xl border border-zinc-100">
             {form.llm_provider === 'openai' && (
                <>
                    <div className="col-span-2 space-y-1">
                        <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">API Key</label>
                        <input 
                            type="password"
                            placeholder={initialConfig?.has_openai_key ? "••••••••••••••••" : "sk-..."}
                            value={form.openai_api_key || ''}
                            onChange={e => setForm({...form, openai_api_key: e.target.value})}
                            className="w-full bg-white border border-zinc-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 ring-indigo-500/10 transition-all"
                        />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Base URL</label>
                        <input 
                            value={form.openai_base_url || ''}
                            onChange={e => setForm({...form, openai_base_url: e.target.value})}
                            className="w-full bg-white border border-zinc-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 ring-indigo-500/10 transition-all"
                        />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Model</label>
                        <input 
                            value={form.openai_model || ''}
                            onChange={e => setForm({...form, openai_model: e.target.value})}
                            className="w-full bg-white border border-zinc-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 ring-indigo-500/10 transition-all"
                        />
                    </div>
                </>
            )}
             {/* ... (Repeat similar styling for other providers) ... */}
             {form.llm_provider === 'anthropic' && (
                <>
                    <div className="col-span-2 space-y-1">
                        <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">API Key</label>
                        <input 
                            type="password"
                            placeholder={initialConfig?.has_anthropic_key ? "••••••••••••••••" : "sk-ant-..."}
                            value={form.anthropic_api_key || ''}
                            onChange={e => setForm({...form, anthropic_api_key: e.target.value})}
                            className="w-full bg-white border border-zinc-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 ring-indigo-500/10 transition-all"
                        />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Base URL</label>
                        <input 
                            value={form.anthropic_base_url || ''}
                            onChange={e => setForm({...form, anthropic_base_url: e.target.value})}
                            className="w-full bg-white border border-zinc-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 ring-indigo-500/10 transition-all"
                        />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Model</label>
                        <input 
                            value={form.anthropic_model || ''}
                            onChange={e => setForm({...form, anthropic_model: e.target.value})}
                            className="w-full bg-white border border-zinc-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 ring-indigo-500/10 transition-all"
                        />
                    </div>
                </>
            )}

            {form.llm_provider === 'gemini' && (
                <>
                    <div className="col-span-2 space-y-1">
                        <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">API Key</label>
                        <input 
                            type="password"
                            placeholder={initialConfig?.has_gemini_key ? "••••••••••••••••" : "AIza..."}
                            value={form.gemini_api_key || ''}
                            onChange={e => setForm({...form, gemini_api_key: e.target.value})}
                            className="w-full bg-white border border-zinc-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 ring-indigo-500/10 transition-all"
                        />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Base URL</label>
                        <input 
                            value={form.gemini_base_url || ''}
                            onChange={e => setForm({...form, gemini_base_url: e.target.value})}
                            className="w-full bg-white border border-zinc-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 ring-indigo-500/10 transition-all"
                        />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Model</label>
                        <input 
                            value={form.gemini_model || ''}
                            onChange={e => setForm({...form, gemini_model: e.target.value})}
                            className="w-full bg-white border border-zinc-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 ring-indigo-500/10 transition-all"
                        />
                    </div>
                </>
            )}
             {form.llm_provider === 'ollama' && (
                <>
                    <div className="space-y-1">
                        <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Base URL</label>
                        <input 
                            value={form.ollama_base_url || ''}
                            onChange={e => setForm({...form, ollama_base_url: e.target.value})}
                             placeholder="http://localhost:11434"
                            className="w-full bg-white border border-zinc-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 ring-indigo-500/10 transition-all"
                        />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">Model</label>
                        <input 
                            value={form.ollama_model || ''}
                            onChange={e => setForm({...form, ollama_model: e.target.value})}
                             placeholder="llama3"
                            className="w-full bg-white border border-zinc-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 ring-indigo-500/10 transition-all"
                        />
                    </div>
                </>
            )}
          </div>
          
          <div className="flex justify-end pt-2">
            <button 
                onClick={handleSave}
                className="bg-zinc-900 text-white px-6 py-2.5 rounded-xl font-bold hover:bg-zinc-800 transition-all active:scale-[0.98] text-sm shadow-lg shadow-zinc-200"
            >
                保存 LLM 配置
            </button>
          </div>
        </div>
      </section>

      {/* PDF & Source Config */}
      <section className="bg-white rounded-3xl p-8 border border-zinc-200 shadow-sm">
        <SectionTitle icon={<FileText size={18} />} title="内容解析策略" desc="设置 PDF 下载与全文解析的规则。" />
        
        <div className="space-y-6">
           <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
             <div className="p-4 rounded-xl border border-zinc-200 hover:border-indigo-300 transition-colors bg-zinc-50/50">
               <div className="flex items-center gap-3 mb-2">
                 <input
                    type="checkbox"
                    checked={Boolean(form.use_pdf_fulltext)}
                    onChange={e => setForm({ ...form, use_pdf_fulltext: e.target.checked })}
                    className="w-5 h-5 rounded border-zinc-300 accent-indigo-600"
                  />
                  <label className="font-bold text-zinc-800">解析 PDF 全文</label>
               </div>
               <p className="text-xs text-zinc-500 pl-8">下载 PDF 文件并提取文本内容供 AI 分析，能获得更精准的细节。</p>
             </div>

             <div className="p-4 rounded-xl border border-zinc-200 hover:border-indigo-300 transition-colors bg-zinc-50/50">
               <div className="flex items-center gap-3 mb-2">
                 <input
                    type="checkbox"
                    checked={Boolean(form.use_arxiv_source)}
                    onChange={e => setForm({ ...form, use_arxiv_source: e.target.checked })}
                    className="w-5 h-5 rounded border-zinc-300 accent-indigo-600"
                  />
                  <label className="font-bold text-zinc-800">尝试源码解析</label>
               </div>
               <p className="text-xs text-zinc-500 pl-8">若 PDF 解析失败或内容不足，尝试下载 LaTeX 源码提取内容。</p>
             </div>
           </div>

           <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
             {[
               { label: "PDF 缓存天数", val: form.pdf_cache_ttl_days, key: 'pdf_cache_ttl_days' },
               { label: "源码缓存天数", val: form.arxiv_source_ttl_days, key: 'arxiv_source_ttl_days' },
               { label: "最大页数", val: form.pdf_body_max_pages, key: 'pdf_body_max_pages' },
               { label: "Token 预算", val: form.pdf_body_max_tokens, key: 'pdf_body_max_tokens', step: 500 }
             ].map((field: any) => (
                <div key={field.key} className="space-y-1">
                  <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">{field.label}</label>
                  <input
                    type="number"
                    min={0}
                    step={field.step || 1}
                    value={field.val ?? 0}
                    onChange={e => setForm({ ...form, [field.key]: parseInt(e.target.value) || 0 })}
                    className="w-full bg-zinc-50 border border-zinc-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-500 focus:ring-1 ring-indigo-500/20"
                  />
                </div>
             ))}
           </div>

           <div className="flex justify-end pt-2">
            <button
              onClick={handlePdfSave}
              className="bg-zinc-900 text-white px-6 py-2.5 rounded-xl font-bold hover:bg-zinc-800 transition-all active:scale-[0.98] text-sm shadow-lg shadow-zinc-200"
            >
              更新策略
            </button>
          </div>
        </div>
      </section>

      {/* Analysis Template */}
      <section className="bg-white rounded-3xl p-8 border border-zinc-200 shadow-sm">
         <div className="flex justify-between items-start mb-6">
            <SectionTitle icon={<Sparkles size={18} />} title="AI 分析模板" desc="自定义简报中 AI 输出的结构与 Prompt。" />
            <button onClick={addTemplateItem} className="text-xs flex items-center gap-1 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 px-4 py-2 rounded-lg transition-colors font-bold">
                <Plus size={14} /> 添加新字段
            </button>
         </div>

         <div className="space-y-4">
            {templateForm.map((item, idx) => (
                <div key={idx} className="flex gap-4 items-start bg-zinc-50/50 p-5 rounded-2xl border border-zinc-200 group hover:border-indigo-200 transition-colors">
                    <div className="flex flex-col gap-1 pt-2">
                        <button onClick={() => moveItem(idx, -1)} disabled={idx===0} className="w-6 h-6 flex items-center justify-center rounded bg-white border border-zinc-200 text-zinc-400 hover:text-indigo-600 hover:border-indigo-300 disabled:opacity-30 transition-all"><MoveUp size={12} /></button>
                        <button onClick={() => moveItem(idx, 1)} disabled={idx===templateForm.length-1} className="w-6 h-6 flex items-center justify-center rounded bg-white border border-zinc-200 text-zinc-400 hover:text-indigo-600 hover:border-indigo-300 disabled:opacity-30 transition-all"><MoveDown size={12} /></button>
                    </div>
                    <div className="flex-1 grid grid-cols-1 md:grid-cols-12 gap-4">
                        <div className="md:col-span-3 space-y-1">
                            <label className="text-[10px] font-bold text-zinc-400 uppercase">显示标题</label>
                            <input 
                                value={item.label}
                                onChange={e => updateTemplateItem(idx, 'label', e.target.value)}
                                className="w-full bg-white border border-zinc-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-500 font-medium"
                                placeholder="例如：核心创新点"
                            />
                        </div>
                        <div className="md:col-span-3 space-y-1">
                            <label className="text-[10px] font-bold text-zinc-400 uppercase">JSON Key</label>
                            <input 
                                value={item.key}
                                onChange={e => updateTemplateItem(idx, 'key', e.target.value)}
                                className="w-full bg-zinc-100 border border-transparent rounded-lg px-3 py-2 text-xs outline-none focus:bg-white focus:border-indigo-500 font-mono text-zinc-600"
                                placeholder="key_name"
                            />
                        </div>
                        <div className="md:col-span-6 space-y-1">
                            <label className="text-[10px] font-bold text-zinc-400 uppercase">Prompt 指令</label>
                            <textarea 
                                value={item.prompt}
                                onChange={e => updateTemplateItem(idx, 'prompt', e.target.value)}
                                rows={2}
                                className="w-full bg-white border border-zinc-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-500 resize-none"
                                placeholder="告诉 AI 该提取或分析什么..."
                            />
                        </div>
                    </div>
                    <button onClick={() => removeTemplateItem(idx)} className="self-center p-2 rounded-lg text-zinc-300 hover:text-red-500 hover:bg-red-50 transition-colors">
                        <Trash2 size={18} />
                    </button>
                </div>
            ))}
         </div>
         <div className="flex justify-end pt-6">
            <button 
                onClick={handleTemplateSave}
                className="bg-zinc-900 text-white px-6 py-2.5 rounded-xl font-bold hover:bg-zinc-800 transition-all active:scale-[0.98] text-sm shadow-lg shadow-zinc-200"
            >
                保存模板设置
            </button>
        </div>
      </section>

      {/* Schedule & Zotero */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <section className="bg-white rounded-3xl p-8 border border-zinc-200 shadow-sm">
             <SectionTitle icon={<Archive size={18} />} title="Zotero 同步" />
             <div className="space-y-4">
                <div className="space-y-1">
                  <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">User ID</label>
                  <input 
                    value={form.zotero_user_id || ''}
                    onChange={e => setForm({...form, zotero_user_id: e.target.value})}
                    className="w-full bg-zinc-50 border border-zinc-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">API Key</label>
                  <input 
                    type="password"
                    placeholder={initialConfig?.has_zotero_key ? "configured" : "API Key..."}
                    value={form.zotero_api_key || ''}
                    onChange={e => setForm({...form, zotero_api_key: e.target.value})}
                    className="w-full bg-zinc-50 border border-zinc-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-indigo-500"
                  />
                </div>
                <div className="pt-4">
                    <button 
                        onClick={handleSave}
                        className="w-full bg-white border border-zinc-300 text-zinc-700 px-6 py-2.5 rounded-xl font-bold hover:bg-zinc-50 transition-all active:scale-[0.98] text-sm"
                    >
                        保存 Zotero 配置
                    </button>
                </div>
             </div>
          </section>

          <section className="bg-white rounded-3xl p-8 border border-zinc-200 shadow-sm">
              <SectionTitle icon={<Calendar size={18} />} title="每日定时任务" />
              <div className="space-y-5">
                   <div className="flex items-center gap-3 p-3 bg-zinc-50 rounded-xl border border-zinc-100">
                      <input
                        type="checkbox"
                        checked={scheduleForm.enabled}
                        onChange={e => setScheduleForm({ ...scheduleForm, enabled: e.target.checked })}
                        className="w-5 h-5 rounded border-zinc-300 accent-indigo-600"
                      />
                      <div>
                        <label className="text-sm font-bold text-zinc-800">启用自动抓取</label>
                        <p className="text-xs text-zinc-500">每天在指定时间自动运行</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1">
                            <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">运行时间</label>
                            <div className="flex items-center gap-2">
                                <input
                                  type="number" min={0} max={23}
                                  value={scheduleForm.hour}
                                  onChange={e => setScheduleForm({ ...scheduleForm, hour: parseInt(e.target.value) || 0 })}
                                  className="w-full bg-zinc-50 border border-zinc-200 rounded-lg px-3 py-2 text-center font-mono font-bold"
                                />
                                <span className="font-bold text-zinc-300">:</span>
                                <input
                                  type="number" min={0} max={59}
                                  value={scheduleForm.minute}
                                  onChange={e => setScheduleForm({ ...scheduleForm, minute: parseInt(e.target.value) || 0 })}
                                  className="w-full bg-zinc-50 border border-zinc-200 rounded-lg px-3 py-2 text-center font-mono font-bold"
                                />
                            </div>
                        </div>
                        <div className="space-y-1">
                             <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">限制</label>
                             <input
                                type="number" min={1} max={50}
                                value={scheduleForm.max_results}
                                onChange={e => setScheduleForm({ ...scheduleForm, max_results: parseInt(e.target.value) || 1 })}
                                className="w-full bg-zinc-50 border border-zinc-200 rounded-lg px-3 py-2 text-sm text-center"
                              />
                        </div>
                    </div>
                    <div className="space-y-1">
                      <label className="text-xs font-bold text-zinc-500 uppercase tracking-wider">自动关键词</label>
                      <input
                        value={scheduleForm.queries}
                        onChange={e => setScheduleForm({ ...scheduleForm, queries: e.target.value })}
                        className="w-full bg-zinc-50 border border-zinc-200 rounded-lg px-3 py-2 text-sm outline-none focus:border-indigo-500"
                        placeholder="keyword1, keyword2..."
                      />
                    </div>
                    <div className="pt-1">
                        <button
                          onClick={handleScheduleSave}
                          className="w-full bg-white border border-zinc-300 text-zinc-700 px-6 py-2.5 rounded-xl font-bold hover:bg-zinc-50 transition-all active:scale-[0.98] text-sm"
                        >
                          保存定时任务
                        </button>
                    </div>
              </div>
          </section>
      </div>

    </div>
  );
}