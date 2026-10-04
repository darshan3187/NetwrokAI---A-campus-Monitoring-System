import React, { useState, useEffect, useCallback } from 'react';
import {
  Database,
  UploadCloud,
  CheckCircle2,
  XCircle,
  FileText,
  Trash2,
  AlertTriangle,
  Sparkles,
  Eye,
  Info,
} from 'lucide-react';
import { researchApi } from '../../services/researchApi';
import type {
  ResearchDataset,
  ResearchDatasetDetail,
} from '../../types/research';
import { Spinner } from '../common/Spinner';

export const DatasetTab: React.FC = () => {
  const [datasets, setDatasets] = useState<ResearchDataset[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [datasetDetail, setDatasetDetail] = useState<ResearchDatasetDetail | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isDetailLoading, setIsDetailLoading] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Upload Form State
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [datasetName, setDatasetName] = useState<string>('');
  const [datasetVersion, setDatasetVersion] = useState<string>('NF-UNSW-NB15');
  const [datasetDesc, setDatasetDesc] = useState<string>('');

  const fetchDatasets = useCallback(async () => {
    try {
      const res = await researchApi.getDatasets();
      setDatasets(res.datasets);
      if (res.datasets.length > 0 && !selectedDatasetId) {
        setSelectedDatasetId(res.datasets[0].id);
      }
    } catch (err: any) {
      setErrorMsg(`Failed to load datasets: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  }, [selectedDatasetId]);

  const loadDetail = useCallback(async (id: string) => {
    setIsDetailLoading(true);
    try {
      const detail = await researchApi.getDatasetDetail(id);
      setDatasetDetail(detail);
    } catch (err: any) {
      setErrorMsg(`Failed to load dataset details: ${err.message}`);
    } finally {
      setIsDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  useEffect(() => {
    if (selectedDatasetId) {
      loadDetail(selectedDatasetId);
    }
  }, [selectedDatasetId, loadDetail]);

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) {
      setErrorMsg('Please select a CSV dataset file to upload.');
      return;
    }

    setIsUploading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    const formData = new FormData();
    formData.append('file', uploadFile);
    if (datasetName.trim()) formData.append('name', datasetName.trim());
    formData.append('version', datasetVersion);
    if (datasetDesc.trim()) formData.append('description', datasetDesc.trim());

    try {
      const created = await researchApi.uploadDataset(formData);
      setSuccessMsg(`Dataset '${created.name}' uploaded and registered successfully.`);
      setUploadFile(null);
      setDatasetName('');
      setDatasetDesc('');
      await fetchDatasets();
      setSelectedDatasetId(created.id);
    } catch (err: any) {
      setErrorMsg(err.message || 'Dataset upload failed.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleLoadSample = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const sample = await researchApi.loadSampleDataset();
      setSuccessMsg(`Bundled sample dataset '${sample.name}' loaded.`);
      await fetchDatasets();
      setSelectedDatasetId(sample.id);
    } catch (err: any) {
      setErrorMsg(`Failed to load sample dataset: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!window.confirm(`Are you sure you want to delete dataset '${name}'?`)) {
      return;
    }
    try {
      await researchApi.deleteDataset(id);
      setSuccessMsg(`Dataset '${name}' removed.`);
      if (selectedDatasetId === id) {
        setSelectedDatasetId(null);
        setDatasetDetail(null);
      }
      await fetchDatasets();
    } catch (err: any) {
      setErrorMsg(`Failed to delete dataset: ${err.message}`);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[360px] gap-3">
        <Spinner size="lg" />
        <span className="text-xs text-text-muted font-mono">Loading dataset manager...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border-subtle pb-4">
        <div>
          <h1 className="text-lg font-bold text-text-primary tracking-tight">
            Dataset Management
          </h1>
          <p className="text-xs text-text-secondary mt-0.5">
            Manage, upload, and validate NetFlow CSV datasets for model training and evaluation.
          </p>
        </div>

        <button
          onClick={handleLoadSample}
          className="px-3.5 py-1.5 rounded-[6px] bg-elevated-surface text-text-primary border border-border-subtle text-xs font-semibold hover:bg-elevated-surface/80 transition-colors flex items-center gap-1.5 cursor-pointer self-start md:self-auto"
        >
          <Sparkles className="w-3.5 h-3.5 text-[#0070f3]" />
          <span>Load Bundled Benchmark Sample</span>
        </button>
      </div>

      {/* Notifications */}
      {errorMsg && (
        <div className="p-3.5 rounded-[6px] bg-red-500/10 border border-red-500/25 flex items-center justify-between text-xs text-red-500">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
          <button onClick={() => setErrorMsg(null)} className="underline cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {successMsg && (
        <div className="p-3.5 rounded-[6px] bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-between text-xs text-emerald-500">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="underline cursor-pointer">
            Dismiss
          </button>
        </div>
      )}

      {/* Main Grid: Upload & Dataset List (5 cols) | Inspector & Sample Preview (7 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Registered Datasets & Upload Form */}
        <div className="lg:col-span-5 space-y-5">
          {/* Datasets List */}
          <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-text-primary uppercase tracking-wider font-mono flex items-center gap-2">
                <Database className="w-3.5 h-3.5 text-[#0070f3]" />
                <span>Registered Datasets</span>
              </span>
              <span className="text-[11px] font-mono text-text-muted">{datasets.length} available</span>
            </div>

            {datasets.length === 0 ? (
              <div className="p-4 rounded-[6px] bg-elevated-surface text-center text-xs text-text-muted">
                No datasets registered. Click "Load Bundled Benchmark Sample" or upload a CSV below.
              </div>
            ) : (
              <div className="space-y-2">
                {datasets.map((d) => {
                  const isSelected = selectedDatasetId === d.id;
                  return (
                    <div
                      key={d.id}
                      onClick={() => setSelectedDatasetId(d.id)}
                      className={`p-3 rounded-[6px] border cursor-pointer transition-all flex items-start justify-between gap-3 ${
                        isSelected
                          ? 'bg-[#0070f3]/10 border-[#0070f3] text-text-primary'
                          : 'bg-elevated-surface/50 border-border-subtle text-text-secondary hover:text-text-primary hover:bg-elevated-surface'
                      }`}
                    >
                      <div className="space-y-1 min-w-0">
                        <div className="font-semibold text-xs text-text-primary flex items-center gap-1.5 flex-wrap">
                          <span className="truncate">{d.name}</span>
                          {d.is_sample && (
                            <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-[#0070f3]/20 text-[#0070f3] shrink-0 font-medium">
                              SAMPLE
                            </span>
                          )}
                          {d.is_adapted ? (
                            <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-500 shrink-0 font-medium">
                              ADAPTED
                            </span>
                          ) : (
                            <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-500 shrink-0 font-medium">
                              NETFLOW
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-text-muted font-mono flex items-center gap-2">
                          <span>{d.total_flows.toLocaleString()} flows</span>
                          <span>•</span>
                          <span className="text-emerald-500">{d.benign_flows.toLocaleString()} benign</span>
                          <span>•</span>
                          <span className="text-amber-500">{d.attack_flows.toLocaleString()} attack</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0 pt-0.5">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(d.id, d.name);
                          }}
                          className="p-1 rounded text-text-muted hover:text-red-500 hover:bg-red-500/10 transition-colors cursor-pointer"
                          title="Delete Dataset"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Upload Form Card */}
          <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle space-y-4">
            <span className="text-xs font-semibold text-text-primary uppercase tracking-wider font-mono flex items-center gap-2">
              <UploadCloud className="w-3.5 h-3.5 text-[#0070f3]" />
              <span>Import Dataset</span>
            </span>

            <form onSubmit={handleUploadSubmit} className="space-y-3 text-xs">
              <div className="space-y-1">
                <span className="text-[11px] text-text-muted">CSV Dataset File</span>
                <input
                  type="file"
                  accept=".csv,.txt"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  disabled={isUploading}
                  className="w-full text-xs text-text-secondary file:mr-2.5 file:py-1.5 file:px-3 file:rounded-[4px] file:border file:border-border-subtle file:text-xs file:bg-elevated-surface file:text-text-primary hover:file:bg-elevated-surface/80 file:cursor-pointer"
                />
                <p className="text-[10px] text-text-muted">
                  Accepts native 8-feature NetFlow (NF-UNSW-NB15) or official UNSW-NB15 test set (sbytes, dbytes, dur, proto, label).
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <span className="text-[11px] text-text-muted">Dataset Name (Optional)</span>
                  <input
                    type="text"
                    placeholder="e.g. UNSW-NB15-Test"
                    value={datasetName}
                    onChange={(e) => setDatasetName(e.target.value)}
                    disabled={isUploading}
                    className="w-full px-2.5 py-1.5 rounded-[4px] bg-elevated-surface text-text-primary border border-border-subtle text-xs"
                  />
                </div>

                <div className="space-y-1">
                  <span className="text-[11px] text-text-muted">Format Version</span>
                  <select
                    value={datasetVersion}
                    onChange={(e) => setDatasetVersion(e.target.value)}
                    disabled={isUploading}
                    className="w-full px-2.5 py-1.5 rounded-[4px] bg-elevated-surface text-text-primary border border-border-subtle text-xs"
                  >
                    <option value="NF-UNSW-NB15">NF-UNSW-NB15 (NetFlow v9)</option>
                    <option value="NF-UNSW-NB15-v2">NF-UNSW-NB15-v2</option>
                    <option value="UNSW-NB15-Testing-Set">UNSW-NB15 Testing Set (Adapter)</option>
                    <option value="Custom NetFlow">Custom NetFlow</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-[11px] text-text-muted">Description (Optional)</span>
                <input
                  type="text"
                  placeholder="Notes on source capture or flow subset..."
                  value={datasetDesc}
                  onChange={(e) => setDatasetDesc(e.target.value)}
                  disabled={isUploading}
                  className="w-full px-2.5 py-1.5 rounded-[4px] bg-elevated-surface text-text-primary border border-border-subtle text-xs"
                />
              </div>

              <button
                type="submit"
                disabled={isUploading || !uploadFile}
                className="w-full py-2 rounded-[6px] bg-[#0070f3] hover:bg-[#0070f3]/90 text-white font-semibold text-xs transition-colors flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                {isUploading ? (
                  <>
                    <Spinner size="sm" />
                    <span>Parsing & Validating...</span>
                  </>
                ) : (
                  <>
                    <UploadCloud className="w-3.5 h-3.5" />
                    <span>Upload & Register Dataset</span>
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Schema Inspector & Preview */}
        <div className="lg:col-span-7 space-y-5">
          {isDetailLoading ? (
            <div className="p-8 rounded-[8px] bg-card-surface border border-border-subtle flex flex-col items-center justify-center min-h-[300px] gap-2">
              <Spinner size="md" />
              <span className="text-xs text-text-muted font-mono">Analyzing schema...</span>
            </div>
          ) : datasetDetail ? (
            <div className="space-y-5">
              {/* Adaptation Notice Banner if dataset was adapted */}
              {(datasetDetail.dataset.is_adapted || datasetDetail.validation.is_adapted) && (
                <div className="p-4 rounded-[8px] bg-amber-500/10 border border-amber-500/25 space-y-2.5 text-xs">
                  <div className="flex items-center gap-2 font-semibold text-amber-600 dark:text-amber-400">
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                    <span>UNSW-NB15 Experimental Adapter Applied</span>
                  </div>
                  <p className="text-text-secondary text-[11px] leading-relaxed">
                    {datasetDetail.validation.adaptation_notes || datasetDetail.dataset.adaptation_notes}
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 font-mono text-[10px]">
                    <div className="bg-elevated-surface/80 p-2 rounded border border-border-subtle">
                      <span className="text-text-primary font-semibold">Byte Direction:</span> sbytes &rarr; IN_BYTES, dbytes &rarr; OUT_BYTES
                    </div>
                    <div className="bg-elevated-surface/80 p-2 rounded border border-border-subtle">
                      <span className="text-text-primary font-semibold">Duration:</span> Converted seconds &times; 1000 to milliseconds
                    </div>
                    <div className="bg-elevated-surface/80 p-2 rounded border border-border-subtle">
                      <span className="text-text-primary font-semibold">Protocol:</span> IANA name-to-integer mapping applied
                    </div>
                    <div className="bg-elevated-surface/80 p-2 rounded border border-border-subtle">
                      <span className="text-text-primary font-semibold">IP & Ports:</span> Surrogate zero tokens (not in official test CSV)
                    </div>
                  </div>
                </div>
              )}

              {/* Feature Compatibility Card */}
              <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-text-primary uppercase tracking-wider font-mono flex items-center gap-2">
                    <FileText className="w-3.5 h-3.5 text-[#0070f3]" />
                    <span>Feature Schema & Validation Status</span>
                  </span>

                  <span
                    className={`text-[11px] font-mono px-2 py-0.5 rounded font-medium self-start sm:self-auto ${
                      datasetDetail.validation.is_paper_compliant
                        ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/25'
                        : datasetDetail.validation.is_adapted
                        ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/25'
                        : 'bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/25'
                    }`}
                  >
                    {datasetDetail.validation.validation_status ||
                      (datasetDetail.validation.is_paper_compliant
                        ? 'Valid Native NetFlow (8/8)'
                        : 'Adapted UNSW-NB15')}
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono text-text-secondary">
                  <div className="p-2 rounded bg-elevated-surface border border-border-subtle">
                    <span className="text-[10px] text-text-muted block uppercase">Schema Type</span>
                    <span className="text-text-primary font-semibold">{datasetDetail.dataset.schema_type || 'native_netflow'}</span>
                  </div>
                  <div className="p-2 rounded bg-elevated-surface border border-border-subtle">
                    <span className="text-[10px] text-text-muted block uppercase">Duration Unit</span>
                    <span className="text-text-primary font-semibold">{datasetDetail.validation.duration_unit || 'milliseconds'}</span>
                  </div>
                  <div className="p-2 rounded bg-elevated-surface border border-border-subtle">
                    <span className="text-[10px] text-text-muted block uppercase">Total Flows</span>
                    <span className="text-text-primary font-semibold">{datasetDetail.dataset.total_flows.toLocaleString()}</span>
                  </div>
                  <div className="p-2 rounded bg-elevated-surface border border-border-subtle">
                    <span className="text-[10px] text-text-muted block uppercase">Class Ratio</span>
                    <span className="text-text-primary font-semibold">
                      {Math.round((datasetDetail.dataset.benign_flows / Math.max(1, datasetDetail.dataset.total_flows)) * 100)}% Benign
                    </span>
                  </div>
                </div>

                <p className="text-xs text-text-secondary">
                  The model evaluates 8 standard NetFlow features. Ground-truth labels are strictly reserved for evaluation metrics and never exposed during model training.
                </p>

                {/* Feature Checklist */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  {datasetDetail.validation.expected_paper_features.map((feat) => {
                    const isPresent = datasetDetail.validation.detected_features.includes(feat);
                    const isSurrogate = datasetDetail.validation.is_adapted && ['IPV4_SRC_ADDR', 'IPV4_DST_ADDR', 'L4_SRC_PORT', 'L4_DST_PORT'].includes(feat);
                    return (
                      <div
                        key={feat}
                        className={`p-2 rounded-[4px] border flex items-center gap-1.5 font-mono text-[11px] ${
                          isPresent
                            ? 'bg-emerald-500/5 border-emerald-500/20 text-text-primary'
                            : isSurrogate
                            ? 'bg-amber-500/5 border-amber-500/20 text-amber-500'
                            : 'bg-red-500/5 border-red-500/20 text-red-500'
                        }`}
                      >
                        {isPresent ? (
                          <CheckCircle2 className="w-3 h-3 text-emerald-500 shrink-0" />
                        ) : isSurrogate ? (
                          <AlertTriangle className="w-3 h-3 text-amber-500 shrink-0" />
                        ) : (
                          <XCircle className="w-3 h-3 text-red-500 shrink-0" />
                        )}
                        <span className="truncate">{feat}</span>
                        {isSurrogate && <span className="text-[9px] text-amber-500 shrink-0">(surrogate)</span>}
                      </div>
                    );
                  })}
                </div>

                <div className="p-2.5 rounded-[6px] bg-elevated-surface/50 border border-border-subtle text-[11px] text-text-secondary flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <Info className="w-3.5 h-3.5 text-[#0070f3]" />
                    <span>Ground Truth Target Label:</span>
                  </span>
                  <span className="font-mono text-emerald-600 dark:text-emerald-400 font-medium">
                    {datasetDetail.validation.has_label_column ? 'Verified (Strictly Isolated)' : 'Missing'}
                  </span>
                </div>
              </div>

              {/* Sample Rows Preview */}
              <div className="p-4 rounded-[8px] bg-card-surface border border-border-subtle space-y-3">
                <span className="text-xs font-semibold text-text-primary uppercase tracking-wider font-mono flex items-center gap-2">
                  <Eye className="w-3.5 h-3.5 text-[#0070f3]" />
                  <span>Sample Records Preview (First 5 Rows)</span>
                </span>

                <div className="overflow-x-auto border border-border-subtle rounded-[6px]">
                  <table className="w-full text-[11px] text-left">
                    <thead className="bg-elevated-surface text-text-muted font-mono uppercase text-[10px] border-b border-border-subtle">
                      <tr>
                        <th className="px-3 py-2">SRC IP</th>
                        <th className="px-3 py-2">DST IP</th>
                        <th className="px-3 py-2">PORTS</th>
                        <th className="px-3 py-2">PROTO</th>
                        <th className="px-3 py-2">BYTES IN/OUT</th>
                        <th className="px-3 py-2">DUR (MS)</th>
                        <th className="px-3 py-2">LABEL</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-subtle font-mono text-text-secondary">
                      {datasetDetail.sample_rows.map((row, idx) => (
                        <tr key={idx} className="hover:bg-elevated-surface/50">
                          <td className="px-3 py-2 truncate max-w-[120px]">
                            {row.IPV4_SRC_ADDR || row.src_ip || (datasetDetail.validation.is_adapted ? '0.0 (surrogate)' : '---')}
                          </td>
                          <td className="px-3 py-2 truncate max-w-[120px]">
                            {row.IPV4_DST_ADDR || row.dst_ip || (datasetDetail.validation.is_adapted ? '0.0 (surrogate)' : '---')}
                          </td>
                          <td className="px-3 py-2 text-text-primary">
                            {row.L4_SRC_PORT || row.src_port || '0'} &rarr; {row.L4_DST_PORT || row.dst_port || '0'}
                          </td>
                          <td className="px-3 py-2">{row.PROTOCOL || row.protocol || row.proto || '6'}</td>
                          <td className="px-3 py-2">
                            {Number(row.IN_BYTES || row.in_bytes || row.sbytes || 0).toLocaleString()} / {Number(row.OUT_BYTES || row.out_bytes || row.dbytes || 0).toLocaleString()}
                          </td>
                          <td className="px-3 py-2">
                            {datasetDetail.validation.is_adapted
                              ? (Number(row.dur || row.duration || 0) * 1000).toFixed(2)
                              : (row.FLOW_DURATION_MILLISECONDS || row.duration || '0')}
                          </td>
                          <td className="px-3 py-2">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] ${
                                String(row.Label || row.label || row.attack || '0') === '1'
                                  ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400'
                                  : 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                              }`}
                            >
                              {String(row.Label || row.label || row.attack || '0') === '1' ? 'Attack' : 'Benign'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 rounded-[8px] bg-card-surface border border-border-subtle flex flex-col items-center justify-center min-h-[300px] text-xs text-text-muted">
              Select a dataset from the left list to inspect its schema and sample records.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
