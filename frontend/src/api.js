const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

async function request(path, options = {}) {
  const headers = options.body instanceof FormData
    ? { ...(options.headers || {}) }
    : {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      };
  const response = await fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }

  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }
  return response.text();
}

export function getHealth() {
  return request('/health');
}

export function listJobs() {
  return request('/api/v1/jobs');
}

export function getJob(jobId) {
  return request(`/api/v1/jobs/${jobId}`);
}

export function createJob(payload) {
  return request('/api/v1/jobs', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function previewPlan(payload) {
  return request('/api/v1/plan', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function previewSafety(payload) {
  return request('/api/v1/safety/preview', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function createBatch(jobs) {
  return request('/api/v1/jobs/batch', {
    method: 'POST',
    body: JSON.stringify({ jobs }),
  });
}

export function uploadInputFile(file) {
  const form = new FormData();
  form.append('file', file);
  return request('/api/v1/uploads', {
    method: 'POST',
    body: form,
  });
}

export function getJobPreview(jobId, limit = 50) {
  return request(`/api/v1/jobs/${jobId}/preview?limit=${limit}`);
}

export function getJobArtifacts(jobId) {
  return request(`/api/v1/jobs/${jobId}/artifacts`);
}

export function getJobQuality(jobId, limit = 50) {
  return request(`/api/v1/jobs/${jobId}/quality?limit=${limit}`);
}

export function listResultFiles() {
  return request('/api/v1/result-files');
}

export function scanQuality(limitFiles = 50, previewLimit = 10) {
  return request(`/api/v1/quality-scan?limit_files=${limitFiles}&preview_limit=${previewLimit}`);
}

export function listPlugins() {
  return request('/api/v1/plugins');
}

export function previewCsv(path, limit = 50) {
  return request(`/api/v1/csv-preview?path=${encodeURIComponent(path)}&limit=${limit}`);
}

export function inspectQuality(path, limit = 50) {
  return request(`/api/v1/quality?path=${encodeURIComponent(path)}&limit=${limit}`);
}

export function prepareRetry(path, source, limit = 50) {
  return request(`/api/v1/retry-prep?path=${encodeURIComponent(path)}&source=${encodeURIComponent(source)}&limit=${limit}`);
}

export function createRetryJob(jobId) {
  return request(`/api/v1/jobs/${jobId}/retry`, {
    method: 'POST',
  });
}

export function createRetryJobsFromScan(limitFiles = 50, maxJobs = 20, previewLimit = 10) {
  return request(`/api/v1/retry-scan?limit_files=${limitFiles}&max_jobs=${maxJobs}&preview_limit=${previewLimit}`, {
    method: 'POST',
  });
}

export function runSync(payload) {
  return request('/api/v1/run-sync', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fileUrl(path) {
  return `${API_BASE}/api/v1/files?path=${encodeURIComponent(path)}`;
}
