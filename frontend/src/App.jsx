import React, { useEffect, useMemo, useState } from 'react';
import { T } from './tokens.js';
import {
  clearFinishedJobs,
  createBatch,
  createJob,
  createRetryJobsFromScan,
  deleteJob,
  fileUrl,
  createRetryJob,
  getHealth,
  getJob,
  getJobQuality,
  getJobPreview,
  listJobs,
  listPlugins,
  listResultFiles,
  scanQuality,
  previewPlan,
  previewSafety,
  uploadInputFile,
} from './api.js';
import { Dot, Ico, Kbd, Num, Pill, btnIcon, btnPrimary } from './ui.jsx';

const defaultWork = {
  input: '',
  description: '抓取这张表前50条笔记，补充标题、封面、文案、话题、互动数据、评论和粉丝量。',
  limit: 50,
  cdp_url: 'http://127.0.0.1:9222',
  crawl_delay: 8,
  download_covers: true,
  embed_covers: true,
  crawl_pgy: false,
  pgy_delay: 12,
  pgy_safe_mode: true,
  pgy_max_retries: 2,
  use_llm: false,
  llm_base_url: 'https://api.deepseek.com/v1',
  llm_model: 'deepseek-v4-flash',
  no_crawl: false,
  execution_mode: 'graph_legacy',
};

const outputColumns = [
  '标题',
  '达人昵称',
  '粉丝量',
  '点赞数',
  '收藏数',
  '评论数',
  '分享数',
  '蒲公英图文报价',
  '蒲公英视频报价',
  '图文CPE',
  '视频CPE',
  '采集状态',
];

function statusTone(status) {
  if (status === 'succeeded') return { color: T.ok, bg: 'rgba(34,197,94,0.08)', br: 'rgba(34,197,94,0.2)' };
  if (status === 'running') return { color: T.red, bg: T.redDim, br: 'rgba(255,36,66,0.2)' };
  if (status === 'queued') return { color: T.warn, bg: 'rgba(234,179,8,0.08)', br: 'rgba(234,179,8,0.2)' };
  if (status === 'failed') return { color: '#dc2626', bg: 'rgba(220,38,38,0.08)', br: 'rgba(220,38,38,0.2)' };
  return { color: T.fg3, bg: T.bg3, br: T.br1 };
}

function prettyTime(value) {
  if (!value) return '--';
  try {
    return new Date(value).toLocaleString('zh-CN', { hour12: false });
  } catch {
    return value;
  }
}

function normalizeError(error) {
  if (!error) return '未知错误';
  if (typeof error === 'string') return error;
  if (error instanceof Error) return error.message;
  return String(error);
}

function buildPayload(work) {
  const outputName = `frontend_${Date.now()}.xlsx`;
  return {
    input: work.input,
    output: `D:/xhs/outputs/${outputName}`,
    description: work.description,
    limit: Number(work.limit || 0),
    cdp_url: work.cdp_url || null,
    crawl_delay: Number(work.crawl_delay || 0),
    download_covers: work.download_covers,
    embed_covers: work.embed_covers,
    crawl_pgy: work.crawl_pgy,
    pgy_delay: Number(work.pgy_delay || 0),
    pgy_safe_mode: work.pgy_safe_mode,
    pgy_max_retries: Number(work.pgy_max_retries || 1),
    use_llm: work.use_llm,
    llm_base_url: work.llm_base_url || null,
    llm_model: work.llm_model || null,
    no_crawl: work.no_crawl,
    execution_mode: work.execution_mode,
  };
}

export default function App() {
  const [work, setWork] = useState(defaultWork);
  const [jobs, setJobs] = useState([]);
  const [activeJobId, setActiveJobId] = useState('');
  const [activeJob, setActiveJob] = useState(null);
  const [preview, setPreview] = useState({ columns: [], rows: [] });
  const [quality, setQuality] = useState(null);
  const [files, setFiles] = useState([]);
  const [qualityScan, setQualityScan] = useState({ files: [], count: 0, total_retry_needed: 0 });
  const [plugins, setPlugins] = useState([]);
  const [health, setHealth] = useState({ status: 'checking' });
  const [activeTab, setActiveTab] = useState('preview');
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [planPreview, setPlanPreview] = useState(null);
  const [safetyPreview, setSafetyPreview] = useState(null);
  const [retryPrep, setRetryPrep] = useState(null);

  useEffect(() => {
    let alive = true;

    async function refreshShell() {
      try {
        const [healthData, jobData, fileData, pluginData, qualityScanData] = await Promise.all([
          getHealth(),
          listJobs(),
          listResultFiles(),
          listPlugins(),
          scanQuality(),
        ]);
        if (!alive) return;
        setHealth(healthData);
        setJobs(jobData);
        setFiles(fileData);
        setPlugins(pluginData);
        setQualityScan(qualityScanData);
        if (jobData.length === 0) {
          setActiveJobId('');
        } else if (!activeJobId || !jobData.some((job) => job.job_id === activeJobId)) {
          setActiveJobId(jobData[0].job_id);
        }
      } catch (err) {
        if (!alive) return;
        setHealth({ status: 'offline' });
        setError(normalizeError(err));
      }
    }

    refreshShell();
    const timer = setInterval(refreshShell, 5000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [activeJobId]);

  useEffect(() => {
    if (!activeJobId) {
      setActiveJob(null);
      setPreview({ columns: [], rows: [] });
      setQuality(null);
      setRetryPrep(null);
      return undefined;
    }

    let alive = true;

    async function refreshJob() {
      try {
        const job = await getJob(activeJobId);
        if (!alive) return;
        setActiveJob(job);
        if (job.csv_output) {
          const [data, qualityData] = await Promise.all([
            getJobPreview(activeJobId, 50),
            getJobQuality(activeJobId, 50),
          ]);
          if (alive) {
            setPreview(data);
            setQuality(qualityData);
          }
        }
      } catch (err) {
        if (!alive) return;
        if (normalizeError(err).includes('job not found')) {
          setActiveJobId('');
          return;
        }
        setError(normalizeError(err));
      }
    }

    refreshJob();
    const timer = setInterval(refreshJob, 3000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [activeJobId]);

  const summaryCards = useMemo(() => {
    const s = activeJob?.summary || {};
    return [
      { label: '总行数', value: s.rows ?? '--' },
      { label: '源表笔记', value: activeJob?.source_rows || '--' },
      { label: '本次处理', value: activeJob?.selected_rows || '--' },
      { label: '成功', value: s.status_ok ?? '--' },
      { label: 'Missing', value: s.status_missing ?? '--' },
      { label: 'LLM', value: s.llm_ok ?? '--' },
      { label: '文案', value: s.has_copywriting ?? '--' },
      { label: '评论', value: s.has_top_comments ?? '--' },
      { label: '图文价', value: s.has_pgy_image_price ?? '--' },
      { label: '视频价', value: s.has_pgy_video_price ?? '--' },
    ];
  }, [activeJob]);

  async function handleUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      const uploaded = await uploadInputFile(file);
      setWork((current) => ({
        ...current,
        input: uploaded.path,
      }));
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  }

  async function submitJob(event) {
    event.preventDefault();
    if (!work.input) {
      setError('请先上传或填写一个 Excel 文件。');
      return;
    }
    if (work.use_llm && health.llm_configured === false) {
      setError('后端没有配置 LLM_API_KEY / OPENAI_API_KEY。请先关闭“启用 LLM”，或者配置 API Key 后重启后端。');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const created = await createJob(buildPayload(work));
      setActiveJobId(created.job_id);
      setActiveTab('preview');
      setJobs(await listJobs());
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitBatch() {
    if (!work.input) {
      setError('请先上传或填写一个 Excel 文件。');
      return;
    }
    if (work.use_llm && health.llm_configured === false) {
      setError('后端没有配置 LLM_API_KEY / OPENAI_API_KEY。请先关闭“启用 LLM”，或者配置 API Key 后重启后端。');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const first = buildPayload(work);
      const second = { ...buildPayload(work), output: `D:/xhs/outputs/frontend_${Date.now()}_pgy.xlsx`, crawl_pgy: true, pgy_safe_mode: true };
      const created = await createBatch([first, second]);
      setActiveJobId(created.job_ids[0]);
      setJobs(await listJobs());
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function handlePreviewPlan() {
    if (!work.input) {
      setError('请先上传或填写一个 Excel 文件。');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const plan = await previewPlan(buildPayload(work));
      setPlanPreview(plan);
      setSafetyPreview(plan.safety || await previewSafety(buildPayload(work)));
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function handlePrepareRetry(jobId = activeJob?.job_id) {
    if (!jobId) {
      setError('当前没有可补抓的任务。');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const result = await createRetryJob(jobId);
      setRetryPrep(result.prep || null);
      if (result.job_id) {
        setActiveJobId(result.job_id);
        setActiveTab('quality');
        setJobs(await listJobs());
      }
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleRetryScan() {
    setBusy(true);
    setError('');
    try {
      const result = await createRetryJobsFromScan();
      setRetryPrep(result);
      setJobs(await listJobs());
      setQualityScan(await scanQuality());
      if (result.created?.[0]?.retry_job_id) {
        setActiveJobId(result.created[0].retry_job_id);
        setActiveTab('quality');
      }
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteJob(jobId) {
    const job = jobs.find((item) => item.job_id === jobId);
    if (job?.status === 'queued' || job?.status === 'running') {
      setError('运行中或排队中的任务不能删除，请等任务结束后再删。');
      return;
    }
    if (!window.confirm('删除这条任务记录？输出文件会保留。')) return;
    setError('');
    try {
      await deleteJob(jobId);
      const nextJobs = await listJobs();
      setJobs(nextJobs);
      if (activeJobId === jobId) {
        setActiveJobId(nextJobs[0]?.job_id || '');
        setActiveJob(null);
        setPreview({ columns: [], rows: [] });
        setQuality(null);
      }
    } catch (err) {
      setError(normalizeError(err));
    }
  }

  async function handleClearHistory() {
    if (!window.confirm('清理所有已完成/失败的任务记录？运行中的任务和输出文件会保留。')) return;
    setError('');
    try {
      await clearFinishedJobs();
      const nextJobs = await listJobs();
      setJobs(nextJobs);
      if (!nextJobs.some((job) => job.job_id === activeJobId)) {
        setActiveJobId(nextJobs[0]?.job_id || '');
        setActiveJob(null);
        setPreview({ columns: [], rows: [] });
        setQuality(null);
      }
    } catch (err) {
      setError(normalizeError(err));
    }
  }

  function update(key, value) {
    setWork((current) => ({ ...current, [key]: value }));
  }

  const tone = statusTone(activeJob?.status);

  return (
    <div style={appShellStyle}>
      <aside style={sideStyle}>
        <div style={sideHeaderStyle}>
          <div>
            <div style={labelStyle}>xhs agent</div>
            <div style={titleStyle}>任务队列</div>
          </div>
          <div style={{ display: 'flex', gap: 4 }}>
            <button type="button" style={btnIcon} title="清理已完成/失败任务" onClick={handleClearHistory}>
              <Ico.trash />
            </button>
            <button type="button" style={btnIcon} title="刷新" onClick={() => window.location.reload()}>
              <Ico.search />
            </button>
          </div>
        </div>

        <div style={{ padding: 14, borderBottom: `1px solid ${T.br0}` }}>
          <Pill color={health.status === 'ok' ? T.ok : T.fg3} bg={health.status === 'ok' ? 'rgba(34,197,94,0.08)' : T.bg3} br={health.status === 'ok' ? 'rgba(34,197,94,0.2)' : T.br1}>
            <Dot color={health.status === 'ok' ? T.ok : T.fg3} />
            {health.status === 'ok' ? '后端在线' : '后端离线'}
          </Pill>
          <div style={{ marginTop: 8, fontSize: 11, color: T.fg4, fontFamily: T.mono }}>
            队列 {health.queue_size ?? 0} · {health.graph_enabled ? 'LangGraph' : 'Legacy'} · 插件 {health.plugins ?? plugins.length} · {prettyTime(health.time)}
          </div>
        </div>

        <div style={jobListStyle}>
          {jobs.length === 0 && <EmptySmall>还没有任务，先从中间工作台提交一次。</EmptySmall>}
          {jobs.map((job) => (
            <JobItem
              key={job.job_id}
              job={job}
              active={job.job_id === activeJobId}
              onClick={() => setActiveJobId(job.job_id)}
              onDelete={() => handleDeleteJob(job.job_id)}
            />
          ))}
        </div>

        <div style={{ padding: 14, borderTop: `1px solid ${T.br0}` }}>
          <div style={labelStyle}>能力插件</div>
          <div style={{ marginTop: 8, maxHeight: 118, overflow: 'auto' }}>
            {plugins.slice(0, 8).map((plugin) => (
              <div key={plugin.plugin_id} style={pluginLineStyle}>
                <span>{plugin.name}</span>
                <span style={{ color: plugin.risk_level === 'high' ? T.red : T.fg4 }}>{plugin.kind}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ padding: 14, borderTop: `1px solid ${T.br0}` }}>
          <div style={labelStyle}>结果文件</div>
          <div style={{ marginTop: 8, maxHeight: 130, overflow: 'auto' }}>
            {files.slice(0, 8).map((file) => (
              <a key={file.path} href={fileUrl(file.path)} style={fileLinkStyle}>
                <span>{file.name}</span>
                <span style={{ color: T.fg4 }}>{file.type}</span>
              </a>
            ))}
          </div>
        </div>
      </aside>

      <main style={workbenchStyle}>
        <header style={mainHeaderStyle}>
          <div>
            <div style={labelStyle}>workspace</div>
            <div style={titleStyle}>上传文件并描述任务</div>
          </div>
          <Kbd>队列执行</Kbd>
        </header>

        <form onSubmit={submitJob} style={formStyle}>
          <section style={panelStyle}>
            <div style={sectionHeaderStyle}>
              <div>
                <div style={sectionTitleStyle}>输入文件</div>
                <div style={mutedStyle}>支持 .xlsx / .xls / .csv，会保存到后端 uploads 目录。</div>
              </div>
              <label style={uploadButtonStyle}>
                <Ico.upload />
                {uploading ? '上传中' : '上传'}
                <input type="file" accept=".xlsx,.xls,.csv" onChange={handleUpload} style={{ display: 'none' }} />
              </label>
            </div>
            <input value={work.input} onChange={(e) => update('input', e.target.value)} placeholder="也可以直接粘贴服务器上的文件路径" style={inputStyle} />
          </section>

          <section style={panelStyle}>
            <div style={sectionTitleStyle}>自然语言描述</div>
            <textarea
              value={work.description}
              onChange={(e) => update('description', e.target.value)}
              style={textareaStyle}
              placeholder="例如：只抓前50条，慢速跑，补评论和粉丝量。"
            />
          </section>

          <section style={panelStyle}>
            <div style={sectionHeaderStyle}>
              <div>
                <div style={sectionTitleStyle}>运行设置</div>
                <div style={mutedStyle}>自然语言先作为任务说明保存，下面的开关决定实际执行参数。</div>
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <Field label="前 N 条">
                <input type="number" min="0" value={work.limit} onChange={(e) => update('limit', e.target.value)} style={inputStyle} />
              </Field>
              <Field label="Chrome CDP">
                <input value={work.cdp_url} onChange={(e) => update('cdp_url', e.target.value)} style={inputStyle} />
              </Field>
              <Field label="笔记间隔">
                <input type="number" min="0" step="0.5" value={work.crawl_delay} onChange={(e) => update('crawl_delay', e.target.value)} style={inputStyle} />
              </Field>
              <Field label="蒲公英间隔">
                <input type="number" min="0" step="0.5" value={work.pgy_delay} onChange={(e) => update('pgy_delay', e.target.value)} style={inputStyle} />
              </Field>
            </div>
          </section>

          <section style={panelStyle}>
            <div style={toggleGridStyle}>
              <Toggle label="仅离线分析" checked={work.no_crawl} onChange={(v) => update('no_crawl', v)} />
              <Toggle label="下载封面" checked={work.download_covers} onChange={(v) => update('download_covers', v)} />
              <Toggle label="嵌入封面" checked={work.embed_covers} onChange={(v) => update('embed_covers', v)} />
              <Toggle label="抓蒲公英" checked={work.crawl_pgy} onChange={(v) => update('crawl_pgy', v)} />
              <Toggle label="蒲公英安全模式" checked={work.pgy_safe_mode} onChange={(v) => update('pgy_safe_mode', v)} />
              <Toggle
                label={health.llm_configured === false ? '启用 LLM（未配置）' : '启用 LLM'}
                checked={work.use_llm}
                onChange={(v) => {
                  if (v && health.llm_configured === false) {
                    setError('后端没有配置 LLM_API_KEY / OPENAI_API_KEY。配置后重启后端，或保持 LLM 关闭。');
                    return;
                  }
                  update('use_llm', v);
                }}
              />
            </div>
          </section>

          <section style={panelStyle}>
            <div style={sectionHeaderStyle}>
              <div>
                <div style={sectionTitleStyle}>执行模式</div>
                <div style={mutedStyle}>默认用 LangGraph 编排，核心抓取仍走已验证的 XHS/蒲公英链路；需要排障时可一键回退。</div>
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
              <button type="button" onClick={() => update('execution_mode', 'graph_legacy')} style={modeButtonStyle(work.execution_mode === 'graph_legacy')}>
                LangGraph 编排
              </button>
              <button type="button" onClick={() => update('execution_mode', 'graph_split')} style={modeButtonStyle(work.execution_mode === 'graph_split')}>
                分节点实验
              </button>
              <button type="button" onClick={() => update('execution_mode', 'legacy')} style={modeButtonStyle(work.execution_mode === 'legacy')}>
                Legacy 直跑
              </button>
            </div>
            {planPreview && (
              <div style={{ marginTop: 10 }}>
                <div style={labelStyle}>计划预览</div>
                <PlanLine plan={planPreview.plan || []} />
              </div>
            )}
            {safetyPreview && (
              <div style={{ marginTop: 10 }}>
                <div style={labelStyle}>安全预览</div>
                <SafetyBox safety={safetyPreview} />
              </div>
            )}
          </section>

          <section style={panelStyle}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <Field label="LLM Base URL">
                <input value={work.llm_base_url} onChange={(e) => update('llm_base_url', e.target.value)} style={inputStyle} />
              </Field>
              <Field label="LLM 模型">
                <input value={work.llm_model} onChange={(e) => update('llm_model', e.target.value)} style={inputStyle} />
              </Field>
            </div>
          </section>

          {error && <div style={errorStyle}>{error}</div>}

          <div style={{ marginTop: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
            <button type="submit" disabled={busy} style={{ ...btnPrimary, opacity: busy ? 0.65 : 1 }}>
              <Ico.send /> {busy ? '提交中' : '提交任务'}
            </button>
            <button type="button" disabled={busy} onClick={submitBatch} style={secondaryButtonStyle}>
              批量队列测试
            </button>
            <button type="button" disabled={busy} onClick={handlePreviewPlan} style={secondaryButtonStyle}>
              预览计划
            </button>
            <span style={{ marginLeft: 'auto', color: T.fg4, fontSize: 11 }}>
              日志和任务状态会持久化保存。
            </span>
          </div>
        </form>
      </main>

      <section style={resultStyle}>
        <header style={mainHeaderStyle}>
          <div>
            <div style={labelStyle}>result</div>
            <div style={titleStyle}>{activeJob ? `任务 ${activeJob.job_id.slice(0, 8)}` : '结果预览'}</div>
            {activeJob?.current_step && <div style={{ marginTop: 5, color: T.fg4, fontSize: 11, fontFamily: T.mono }}>step: {activeJob.current_step}</div>}
          </div>
          {activeJob && <Pill color={tone.color} bg={tone.bg} br={tone.br}><Dot color={tone.color} />{activeJob.status}</Pill>}
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
            {activeJob?.output && <a href={fileUrl(activeJob.output)} style={linkButtonStyle}><Ico.download /> Excel</a>}
            {activeJob?.csv_output && <a href={fileUrl(activeJob.csv_output)} style={linkButtonStyle}><Ico.download /> CSV</a>}
            {activeJob?.csv_output && activeJob?.request?.input && <button type="button" onClick={handlePrepareRetry} style={linkButtonPlainStyle}><Ico.upload /> 开始补抓</button>}
          </div>
        </header>

        <div style={tabBarStyle}>
          {[
            ['scan', '总览', <Ico.chart />],
            ['preview', '表格预览', <Ico.table />],
            ['summary', '摘要', <Ico.chart />],
            ['quality', '质量', <Ico.search />],
            ['logs', '日志', <Ico.doc />],
            ['request', '参数', <Ico.json />],
          ].map(([key, label, icon]) => (
            <button key={key} onClick={() => setActiveTab(key)} style={tabStyle(activeTab === key)}>
              {icon}{label}
            </button>
          ))}
          {activeJob && <span style={{ marginLeft: 'auto', color: T.fg4, fontSize: 11, fontFamily: T.mono }}>{prettyTime(activeJob.updated_at)}</span>}
        </div>

        <div style={resultBodyStyle}>
          {!activeJob && <EmptyState />}
          {activeTab === 'scan' && <QualityScanView scan={qualityScan} onOpenJob={setActiveJobId} onRetry={handlePrepareRetry} onRetryAll={handleRetryScan} busy={busy} retryPrep={retryPrep} />}
          {activeJob && activeTab === 'preview' && <PreviewTable preview={preview} />}
          {activeJob && activeTab === 'summary' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {activeJob.plan?.length > 0 && (
                <div style={metricStyle}>
                  <div style={labelStyle}>执行计划</div>
                  <PlanLine plan={activeJob.plan} />
                </div>
              )}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(120px, 1fr))', gap: 10 }}>
                {summaryCards.map((item) => <MetricCard key={item.label} {...item} />)}
              </div>
            </div>
          )}
          {activeJob && activeTab === 'quality' && <QualityView quality={quality} retryPrep={retryPrep} />}
          {activeJob && activeTab === 'logs' && <LogView logs={activeJob.logs} error={activeJob.error} />}
          {activeJob && activeTab === 'request' && <pre style={codeStyle}>{JSON.stringify(activeJob.request, null, 2)}</pre>}
        </div>
      </section>
    </div>
  );
}

function JobItem({ job, active, onClick, onDelete }) {
  const tone = statusTone(job.status);
  const canDelete = job.status !== 'queued' && job.status !== 'running';
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') onClick();
      }}
      style={{ ...jobItemStyle, background: active ? T.bg3 : 'transparent' }}
    >
      <div style={jobItemHeaderStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
          <strong style={{ fontSize: 12 }}>{job.job_id.slice(0, 8)}</strong>
          <Pill color={tone.color} bg={tone.bg} br={tone.br}>{job.status}</Pill>
        </div>
        {canDelete && (
          <button
            type="button"
            title="删除任务记录"
            onClick={(event) => {
              event.stopPropagation();
              onDelete();
            }}
            style={deleteButtonStyle}
          >
            <Ico.trash />
          </button>
        )}
      </div>
      <div style={jobDescriptionStyle}>{job.request?.description || job.request?.input || '--'}</div>
      <div style={{ marginTop: 5, color: T.fg4, fontSize: 10.5, fontFamily: T.mono }}>{prettyTime(job.created_at)}</div>
    </div>
  );
}

function PreviewTable({ preview }) {
  const columns = outputColumns.filter((col) => preview.columns?.includes(col));
  const visibleColumns = columns.length ? columns : (preview.columns || []).slice(0, 10);
  if (!preview.rows?.length) {
    return <EmptySmall>任务完成后，这里会显示 CSV 前 50 行。</EmptySmall>;
  }
  return (
    <div style={{ overflow: 'auto', border: `1px solid ${T.br0}`, borderRadius: 8, background: T.bg2 }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr>
            {visibleColumns.map((col) => <th key={col} style={thStyle}>{col}</th>)}
          </tr>
        </thead>
        <tbody>
          {preview.rows.map((row, idx) => (
            <tr key={idx} style={{ borderTop: `1px solid ${T.br0}` }}>
              {visibleColumns.map((col) => <td key={col} style={tdStyle}>{row[col] || ''}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LogView({ logs = [], error }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {error && <div style={errorStyle}>{error}</div>}
      {logs.length === 0 && <EmptySmall>暂无日志。</EmptySmall>}
      {logs.map((line, index) => (
        <div key={`${line}-${index}`} style={logLineStyle}>{line}</div>
      ))}
    </div>
  );
}

function Field({ label, children }) {
  return <label><div style={labelStyle}>{label}</div>{children}</label>;
}

function Toggle({ label, checked, onChange }) {
  return (
    <button type="button" onClick={() => onChange(!checked)} style={{ ...toggleStyle, background: checked ? T.bg3 : T.bg2, borderColor: checked ? T.br2 : T.br0 }}>
      <span>{label}</span>
      <span style={{ ...switchStyle, background: checked ? T.red : T.bg4 }}>
        <span style={{ ...knobStyle, left: checked ? 13 : 2 }} />
      </span>
    </button>
  );
}

function PlanLine({ plan = [] }) {
  if (!plan.length) return <EmptySmall>暂无计划。</EmptySmall>;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
      {plan.map((step, index) => (
        <Pill key={`${step}-${index}`} color={T.fg1} bg={T.bg3} br={T.br1}>
          <Num>{index + 1}</Num> · {step}
        </Pill>
      ))}
    </div>
  );
}

function SafetyBox({ safety }) {
  const tone = safety?.risk_level === 'high'
    ? { color: T.red, bg: T.redDim, br: 'rgba(255,36,66,0.2)' }
    : safety?.risk_level === 'medium'
      ? { color: T.warn, bg: 'rgba(234,179,8,0.08)', br: 'rgba(234,179,8,0.2)' }
      : { color: T.ok, bg: 'rgba(34,197,94,0.08)', br: 'rgba(34,197,94,0.2)' };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <Pill color={tone.color} bg={tone.bg} br={tone.br}>
        <Dot color={tone.color} /> {safety?.risk_level || 'low'} · {safety?.allowed === false ? 'blocked' : 'allowed'}
      </Pill>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        <Pill color={T.fg1} bg={T.bg3} br={T.br1}>XHS {safety?.uses_xhs ? 'on' : 'off'}</Pill>
        <Pill color={T.fg1} bg={T.bg3} br={T.br1}>PGY {safety?.uses_pgy ? 'on' : 'off'}</Pill>
        <Pill color={T.fg1} bg={T.bg3} br={T.br1}>LLM {safety?.uses_llm ? 'on' : 'off'}</Pill>
        <Pill color={T.fg1} bg={T.bg3} br={T.br1}>rows <Num>{safety?.estimated_crawl_rows ?? 0}</Num></Pill>
      </div>
      {safety?.usage && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          <Pill color={T.fg1} bg={T.bg3} br={T.br1}>today XHS <Num>{safety.usage?.totals?.xhs_rows ?? 0}</Num></Pill>
          <Pill color={T.fg1} bg={T.bg3} br={T.br1}>today PGY <Num>{safety.usage?.totals?.pgy_rows ?? 0}</Num></Pill>
          <Pill color={T.fg1} bg={T.bg3} br={T.br1}>hour XHS <Num>{safety.usage?.current_hour?.xhs_rows ?? 0}</Num></Pill>
          <Pill color={T.fg1} bg={T.bg3} br={T.br1}>hour PGY <Num>{safety.usage?.current_hour?.pgy_rows ?? 0}</Num></Pill>
        </div>
      )}
      {[...(safety?.adjustments || []), ...(safety?.warnings || []), ...(safety?.errors || [])].map((line, index) => (
        <div key={`${line}-${index}`} style={miniNoticeStyle}>{line}</div>
      ))}
    </div>
  );
}

function MetricCard({ label, value }) {
  return (
    <div style={metricStyle}>
      <div style={labelStyle}>{label}</div>
      <div style={{ marginTop: 14, fontSize: 26, fontWeight: 650 }}><Num>{value}</Num></div>
    </div>
  );
}

function QualityView({ quality, retryPrep }) {
  if (!quality) {
    return <EmptySmall>暂无质量报告。</EmptySmall>;
  }
  const missingEntries = Object.entries(quality.missing || {});
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(120px, 1fr))', gap: 10 }}>
        <MetricCard label="完整度" value={`${quality.score ?? 0}%`} />
        <MetricCard label="完整行" value={quality.complete_rows ?? '--'} />
        <MetricCard label="待补抓" value={quality.retry_needed ?? '--'} />
        <MetricCard label="总行数" value={quality.rows ?? '--'} />
      </div>
      <div style={metricStyle}>
        <div style={labelStyle}>缺失字段</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(160px, 1fr))', gap: 8, marginTop: 10 }}>
          {missingEntries.map(([key, value]) => (
            <div key={key} style={miniNoticeStyle}>{key}: <Num>{value}</Num></div>
          ))}
        </div>
      </div>
      <div style={metricStyle}>
        <div style={labelStyle}>待补抓清单（前 50 条）</div>
        {quality.retry_rows?.length ? (
          <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {quality.retry_rows.map((row) => (
              <div key={`${row.index}-${row.url}`} style={retryRowStyle}>
                <div style={{ fontSize: 12.5, color: T.fg0 }}>{row.title || row.url || `row ${row.index}`}</div>
                <div style={{ marginTop: 4, color: T.fg3, fontSize: 11 }}>
                  #{row.row_number || row.index} · {row.status} · {(row.missing_columns || []).join(' / ') || 'status failed'}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptySmall>当前结果没有待补抓记录。</EmptySmall>
        )}
      </div>
      {retryPrep && (
        <div style={metricStyle}>
          <div style={labelStyle}>补抓预演</div>
          <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={miniNoticeStyle}>待补抓记录: <Num>{retryPrep.retry_candidates ?? 0}</Num></div>
            <div style={miniNoticeStyle}>补抓输入行数: <Num>{retryPrep.retry_input_rows ?? 0}</Num></div>
            {retryPrep.retry_input && (
              <a href={fileUrl(retryPrep.retry_input)} style={linkButtonStyle}>
                <Ico.download /> 下载补抓输入表
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function QualityScanView({ scan, onOpenJob, onRetry, onRetryAll, busy, retryPrep }) {
  const files = scan?.files || [];
  if (!files.length) {
    return <EmptySmall>还没有可扫描的结果 CSV。</EmptySmall>;
  }
  const lowestScore = files.reduce((min, item) => Math.min(min, Number(item?.quality?.score ?? 100)), 100);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button type="button" onClick={onRetryAll} disabled={busy} style={secondaryButtonStyle}>
          <Ico.upload /> {busy ? '排队中' : '批量补抓'}
        </button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(140px, 1fr))', gap: 10 }}>
        <MetricCard label="扫描文件" value={scan?.count ?? 0} />
        <MetricCard label="待补抓总数" value={scan?.total_retry_needed ?? 0} />
        <MetricCard label="最低完整度" value={`${lowestScore}%`} />
      </div>
      {retryPrep?.created && (
        <div style={metricStyle}>
          <div style={labelStyle}>批量补抓结果</div>
          <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            <div style={miniNoticeStyle}>新建任务: <Num>{retryPrep.created.length}</Num></div>
            <div style={miniNoticeStyle}>跳过: <Num>{retryPrep.skipped?.length ?? 0}</Num></div>
            <div style={miniNoticeStyle}>待补抓总数: <Num>{retryPrep.retry_needed_total ?? 0}</Num></div>
          </div>
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {files.map((item) => {
          const score = Number(item?.quality?.score ?? 0);
          const retryNeeded = Number(item?.quality?.retry_needed ?? 0);
          const missingSummary = Object.entries(item?.quality?.missing || {})
            .filter(([, value]) => Number(value) > 0)
            .slice(0, 4)
            .map(([key, value]) => `${key}: ${value}`)
            .join('  ·  ');
          const scoreTone = score >= 95 ? T.ok : score >= 80 ? T.warn : T.red;
          return (
            <div key={item.path} style={scanCardStyle}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 650, color: T.fg0, wordBreak: 'break-all' }}>{item.name}</div>
                  <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    <Pill color={scoreTone} bg={T.bg3} br={T.br1}>score <Num>{score}%</Num></Pill>
                    <Pill color={T.fg1} bg={T.bg3} br={T.br1}>rows <Num>{item?.quality?.rows ?? 0}</Num></Pill>
                    <Pill color={retryNeeded ? T.warn : T.ok} bg={T.bg3} br={T.br1}>retry <Num>{retryNeeded}</Num></Pill>
                    {item.job_id && <Pill color={T.fg1} bg={T.bg3} br={T.br1}>job {item.job_id.slice(0, 8)}</Pill>}
                  </div>
                  <div style={{ marginTop: 8, color: T.fg3, fontSize: 11.5, lineHeight: 1.6 }}>
                    {missingSummary || '当前文件没有缺失字段'}
                  </div>
                  <div style={{ marginTop: 6, color: T.fg4, fontSize: 10.5, fontFamily: T.mono }}>
                    {prettyTime(item.modified_at)}
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 112 }}>
                  <a href={fileUrl(item.path)} style={linkButtonStyle}>
                    <Ico.download /> CSV
                  </a>
                  {item.job_id && (
                    <button type="button" onClick={() => onOpenJob(item.job_id)} style={linkButtonPlainStyle}>
                      <Ico.search /> 打开任务
                    </button>
                  )}
                  {item.can_retry && item.job_id && (
                    <button type="button" onClick={() => onRetry(item.job_id)} style={linkButtonPlainStyle}>
                      <Ico.upload /> 补抓
                    </button>
                  )}
                </div>
              </div>
              {item?.quality?.retry_rows?.length > 0 && (
                <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {item.quality.retry_rows.slice(0, 3).map((row) => (
                    <div key={`${item.path}-${row.index}`} style={miniNoticeStyle}>
                      #{row.row_number || row.index} · {row.title || row.url || 'untitled'} · {(row.missing_columns || []).join(' / ') || row.status}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div style={{ height: '100%', display: 'grid', placeItems: 'center' }}>
      <div style={{ maxWidth: 420, textAlign: 'center', color: T.fg2, lineHeight: 1.7 }}>
        <div style={{ fontSize: 18, color: T.fg0, fontWeight: 650, marginBottom: 8 }}>等待任务</div>
        上传文件并提交后，右侧会显示摘要、日志和结果表预览。
      </div>
    </div>
  );
}

function EmptySmall({ children }) {
  return <div style={{ padding: 14, color: T.fg3, fontSize: 12, lineHeight: 1.6 }}>{children}</div>;
}

const appShellStyle = { display: 'grid', gridTemplateColumns: '250px 440px minmax(0, 1fr)', height: '100vh', overflow: 'hidden', background: T.bg0, color: T.fg0 };
const sideStyle = { height: '100vh', overflow: 'hidden', background: T.bg1, borderRight: `1px solid ${T.br0}`, display: 'flex', flexDirection: 'column', minWidth: 0, minHeight: 0 };
const workbenchStyle = { height: '100vh', overflow: 'hidden', background: T.bg0, borderRight: `1px solid ${T.br0}`, display: 'flex', flexDirection: 'column', minWidth: 0, minHeight: 0 };
const resultStyle = { height: '100vh', overflow: 'hidden', background: T.bg0, display: 'flex', flexDirection: 'column', minWidth: 0, minHeight: 0 };
const sideHeaderStyle = { padding: '14px 16px', borderBottom: `1px solid ${T.br0}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' };
const mainHeaderStyle = { padding: '14px 16px', borderBottom: `1px solid ${T.br0}`, display: 'flex', alignItems: 'center', gap: 10 };
const labelStyle = { fontSize: 11, color: T.fg3, fontFamily: T.mono, textTransform: 'uppercase', marginBottom: 7 };
const titleStyle = { fontSize: 16, fontWeight: 650 };
const formStyle = { flex: 1, minHeight: 0, overflow: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 12 };
const panelStyle = { background: T.bg2, border: `1px solid ${T.br0}`, borderRadius: 8, padding: 14 };
const sectionHeaderStyle = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 10 };
const sectionTitleStyle = { fontSize: 13, fontWeight: 650, color: T.fg0 };
const mutedStyle = { marginTop: 4, fontSize: 11, color: T.fg3, lineHeight: 1.5 };
const inputStyle = { width: '100%', padding: '9px 10px', borderRadius: 6, border: `1px solid ${T.br1}`, background: T.bg2, color: T.fg0, outline: 'none', fontSize: 12 };
const textareaStyle = { ...inputStyle, minHeight: 120, resize: 'vertical', lineHeight: 1.6 };
const uploadButtonStyle = { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 11px', background: T.bg3, border: `1px solid ${T.br1}`, borderRadius: 8, color: T.fg1, fontSize: 12, cursor: 'pointer' };
const toggleGridStyle = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 };
const toggleStyle = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '9px 10px', borderRadius: 6, border: '1px solid', color: T.fg1, cursor: 'pointer', fontSize: 12 };
const switchStyle = { width: 29, height: 17, borderRadius: 999, position: 'relative', flexShrink: 0 };
const knobStyle = { position: 'absolute', top: 2, width: 13, height: 13, borderRadius: '50%', background: '#fff', transition: 'left 160ms ease' };
const secondaryButtonStyle = { display: 'inline-flex', alignItems: 'center', padding: '7px 12px', background: T.bg2, border: `1px solid ${T.br1}`, borderRadius: 8, color: T.fg1, fontSize: 12, cursor: 'pointer' };
const modeButtonStyle = (active) => ({ padding: '9px 10px', background: active ? T.bg3 : T.bg2, border: `1px solid ${active ? T.br2 : T.br0}`, borderRadius: 7, color: active ? T.fg0 : T.fg2, cursor: 'pointer', fontSize: 12, textAlign: 'left' });
const errorStyle = { padding: '10px 12px', borderRadius: 8, background: 'rgba(220,38,38,0.06)', border: '1px solid rgba(220,38,38,0.16)', color: '#b91c1c', fontSize: 12, lineHeight: 1.5, whiteSpace: 'pre-wrap' };
const miniNoticeStyle = { padding: '7px 9px', borderRadius: 7, background: T.bg3, border: `1px solid ${T.br0}`, color: T.fg2, fontSize: 11.5, lineHeight: 1.45 };
const fileLinkStyle = { display: 'flex', justifyContent: 'space-between', gap: 8, padding: '5px 0', color: T.fg2, textDecoration: 'none', fontSize: 11, borderTop: `1px solid ${T.br0}` };
const pluginLineStyle = { display: 'flex', justifyContent: 'space-between', gap: 8, padding: '5px 0', color: T.fg2, fontSize: 11, borderTop: `1px solid ${T.br0}` };
const retryRowStyle = { padding: '9px 10px', borderRadius: 7, background: T.bg3, border: `1px solid ${T.br0}` };
const scanCardStyle = { background: T.bg2, border: `1px solid ${T.br0}`, borderRadius: 8, padding: 14 };
const jobListStyle = { flex: 1, minHeight: 0, overflow: 'auto', padding: '10px 8px' };
const jobItemStyle = { width: '100%', display: 'block', textAlign: 'left', padding: '10px 12px', border: 'none', borderRadius: 7, cursor: 'pointer', marginBottom: 6, color: T.fg1, outline: 'none' };
const jobItemHeaderStyle = { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 };
const jobDescriptionStyle = { marginTop: 6, color: T.fg3, fontSize: 11, lineHeight: 1.45, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', wordBreak: 'break-word' };
const deleteButtonStyle = { ...btnIcon, width: 24, height: 24, color: T.fg4, flexShrink: 0 };
const tabBarStyle = { padding: '9px 16px', borderBottom: `1px solid ${T.br0}`, display: 'flex', gap: 8, alignItems: 'center' };
const tabStyle = (active) => ({ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 999, border: `1px solid ${active ? T.br2 : T.br0}`, background: active ? T.bg3 : 'transparent', color: active ? T.fg0 : T.fg3, cursor: 'pointer', fontSize: 11.5 });
const linkButtonStyle = { display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 9px', background: T.bg2, border: `1px solid ${T.br1}`, borderRadius: 7, color: T.fg2, textDecoration: 'none', fontSize: 11.5 };
const linkButtonPlainStyle = { display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 9px', background: T.bg2, border: `1px solid ${T.br1}`, borderRadius: 7, color: T.fg2, textDecoration: 'none', fontSize: 11.5, cursor: 'pointer' };
const metricStyle = { background: T.bg2, border: `1px solid ${T.br0}`, borderRadius: 8, padding: 14, minHeight: 90 };
const codeStyle = { margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 11.5, lineHeight: 1.7, color: T.fg1, fontFamily: T.mono, background: T.bg2, border: `1px solid ${T.br0}`, borderRadius: 8, padding: 14 };
const logLineStyle = { padding: '8px 10px', borderRadius: 7, background: T.bg2, border: `1px solid ${T.br0}`, fontFamily: T.mono, fontSize: 11.5, color: T.fg1 };
const resultBodyStyle = { flex: 1, minHeight: 0, overflow: 'auto', padding: 16 };
const thStyle = { position: 'sticky', top: 0, zIndex: 1, background: T.bg2, color: T.fg3, textAlign: 'left', padding: '9px 10px', fontSize: 11, fontFamily: T.mono, whiteSpace: 'nowrap' };
const tdStyle = { padding: '9px 10px', color: T.fg1, maxWidth: 280, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', verticalAlign: 'top' };
