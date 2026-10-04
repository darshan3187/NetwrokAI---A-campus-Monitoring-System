import React, { useState } from 'react';
import {
  ExternalLink,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Layers,
  GraduationCap,
} from 'lucide-react';

export const DocumentationTab: React.FC = () => {
  const [activeFaq, setActiveFaq] = useState<number | null>(null);

  const toggleFaq = (index: number) => {
    setActiveFaq(activeFaq === index ? null : index);
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-8 text-text-primary">
      {/* Page Header */}
      <div className="border-b border-border-subtle pb-4">
        <h1 className="text-lg font-bold text-text-primary tracking-tight">
          Research &amp; About
        </h1>
        <p className="text-xs text-text-secondary mt-0.5">
          Reference paper citation, project methodology, NetFlow features, and viva defense notes.
        </p>
      </div>

      {/* 1. Concise Reference to Selected Research Paper */}
      <div className="p-5 rounded-[8px] bg-card-surface border border-border-subtle space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-[11px] font-mono font-semibold text-[#0070f3] uppercase tracking-wider">
            Reference Research Paper
          </span>
          <a
            href="https://arxiv.org/abs/2509.01375"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-xs text-[#0070f3] font-semibold hover:underline"
          >
            <span>arXiv:2509.01375 [cs.CR]</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>

        <h2 className="text-base font-bold text-text-primary leading-snug">
          Anomaly Detection in Network Flows Using Unsupervised Online Machine Learning
        </h2>

        <div className="text-xs text-text-secondary space-y-1 pt-1 border-t border-border-subtle">
          <div>
            <strong>Authors:</strong> Alberto Miguel-Diez, Adrián Campazas-Vega, Ángel Manuel Guerrero-Higueras, Claudia Álvarez-Aparicio, Vicente Matellán-Olivera.
          </div>
          <div>
            <strong>Institution:</strong> Universidad de León, Spain (Published September 2025).
          </div>
          <p className="text-text-muted pt-1">
            <strong>Summary:</strong> This paper introduces an unsupervised online streaming anomaly detection pipeline using River's One-Class SVM with an incremental MaxAbsScaler and QuantileFilter dynamic thresholding. The model updates model weights exclusively on benign flows to prevent adversarial model poisoning, processing network flows at sub-millisecond speeds without requiring pre-labeled training data.
          </p>
        </div>
      </div>

      {/* 2. B.Tech Student Project Scope & Contribution */}
      <div className="p-5 rounded-[8px] bg-card-surface border border-border-subtle space-y-3">
        <div className="flex items-center gap-2">
          <GraduationCap className="w-4 h-4 text-[#0070f3]" />
          <h2 className="text-xs font-semibold text-text-primary uppercase tracking-wider font-mono">
            B.Tech Project Scope &amp; Contribution
          </h2>
        </div>

        <p className="text-xs text-text-secondary leading-relaxed">
          This college project implements and evaluates unsupervised online anomaly detection for network flows as part of Computer Network practical coursework:
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs pt-1">
          <div className="p-3 rounded-[6px] bg-elevated-surface/50 border border-border-subtle space-y-1">
            <strong className="text-text-primary block font-medium">1. Online ML Implementation</strong>
            <p className="text-text-secondary text-[11px]">
              Reproduces the reference paper's streaming River One-Class SVM with incremental MaxAbsScaler and QuantileFilter thresholding.
            </p>
          </div>

          <div className="p-3 rounded-[6px] bg-elevated-surface/50 border border-border-subtle space-y-1">
            <strong className="text-text-primary block font-medium">2. Baseline Comparison</strong>
            <p className="text-text-secondary text-[11px]">
              Compares streaming online performance against Scikit-Learn's Isolation Forest baseline on identical 8-feature NetFlow splits.
            </p>
          </div>

          <div className="p-3 rounded-[6px] bg-elevated-surface/50 border border-border-subtle space-y-1">
            <strong className="text-text-primary block font-medium">3. Telemetry Integration</strong>
            <p className="text-text-secondary text-[11px]">
              Provides a real-time host monitor to inspect local network interface throughput and packet activity via Python <code className="font-mono text-text-primary">psutil</code>.
            </p>
          </div>
        </div>
      </div>

      {/* 3. 8 NetFlow Feature Specifications */}
      <div className="p-5 rounded-[8px] bg-card-surface border border-border-subtle space-y-3">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-[#0070f3]" />
          <h2 className="text-xs font-semibold text-text-primary uppercase tracking-wider font-mono">
            8 NetFlow Features Used by the Model
          </h2>
        </div>

        <div className="border border-border-subtle rounded-[6px] overflow-hidden">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-elevated-surface border-b border-border-subtle text-[11px] font-mono text-text-muted uppercase">
                <th className="p-2.5">Feature Name</th>
                <th className="p-2.5">Data Type</th>
                <th className="p-2.5">Preprocessing</th>
                <th className="p-2.5">Role in Traffic Analysis</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle text-text-secondary font-mono text-[11px]">
              <tr>
                <td className="p-2.5 font-semibold text-[#0070f3]">IPV4_SRC_ADDR</td>
                <td className="p-2.5 text-text-muted">IPv4 Address</td>
                <td className="p-2.5">Converted to 32-bit unsigned int</td>
                <td className="p-2.5 font-sans">Source host IP address</td>
              </tr>
              <tr>
                <td className="p-2.5 font-semibold text-[#0070f3]">IPV4_DST_ADDR</td>
                <td className="p-2.5 text-text-muted">IPv4 Address</td>
                <td className="p-2.5">Converted to 32-bit unsigned int</td>
                <td className="p-2.5 font-sans">Destination server or service IP</td>
              </tr>
              <tr>
                <td className="p-2.5 font-semibold text-text-primary">L4_SRC_PORT</td>
                <td className="p-2.5 text-text-muted">Integer (0-65535)</td>
                <td className="p-2.5">Standard integer bounds</td>
                <td className="p-2.5 font-sans">Client ephemeral port</td>
              </tr>
              <tr>
                <td className="p-2.5 font-semibold text-text-primary">L4_DST_PORT</td>
                <td className="p-2.5 text-text-muted">Integer (0-65535)</td>
                <td className="p-2.5">Standard integer bounds</td>
                <td className="p-2.5 font-sans">Destination service port (80, 443, etc.)</td>
              </tr>
              <tr>
                <td className="p-2.5 font-semibold text-text-primary">PROTOCOL</td>
                <td className="p-2.5 text-text-muted">Integer (1-255)</td>
                <td className="p-2.5">IANA Protocol Number</td>
                <td className="p-2.5 font-sans">6 for TCP, 17 for UDP, 1 for ICMP</td>
              </tr>
              <tr>
                <td className="p-2.5 font-semibold text-text-primary">IN_BYTES</td>
                <td className="p-2.5 text-text-muted">Integer</td>
                <td className="p-2.5">Scaled via MaxAbsScaler</td>
                <td className="p-2.5 font-sans">Inbound byte volume transferred</td>
              </tr>
              <tr>
                <td className="p-2.5 font-semibold text-text-primary">OUT_BYTES</td>
                <td className="p-2.5 text-text-muted">Integer</td>
                <td className="p-2.5">Scaled via MaxAbsScaler</td>
                <td className="p-2.5 font-sans">Outbound byte volume transferred</td>
              </tr>
              <tr>
                <td className="p-2.5 font-semibold text-text-primary">FLOW_DURATION_MILLISECONDS</td>
                <td className="p-2.5 text-text-muted">Float</td>
                <td className="p-2.5">Scaled via MaxAbsScaler</td>
                <td className="p-2.5 font-sans">Duration of the flow in milliseconds</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* 4. Viva / Presentation Q&A Guide */}
      <div className="p-5 rounded-[8px] bg-card-surface border border-border-subtle space-y-3">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-[#0070f3]" />
          <h2 className="text-xs font-semibold text-text-primary uppercase tracking-wider font-mono">
            Viva / Presentation Q&amp;A Defense Guide
          </h2>
        </div>

        <div className="space-y-2">
          {[
            {
              q: 'Why use unsupervised online machine learning rather than supervised deep learning in high-speed networks?',
              a: 'Supervised deep learning models require human-labeled training data that cannot be generated in real-time at high network speeds, and they fail to detect zero-day attacks that have no existing labels. In contrast, River Online One-Class SVM operates in an unsupervised manner: it learns what normal network traffic looks like and flags any deviations as anomalies without needing attack labels during training.',
            },
            {
              q: 'How does conditional updating prevent adversarial poisoning of the model?',
              a: 'If an online model updated its weights on every incoming network packet, an attacker could slowly send malicious packets to gradually poison the model\'s baseline. Miguel-Diez et al. use conditional updating: incoming flows that are scored as anomalies are quarantined and never used to update model weights. Only benign flows update the model.',
            },
            {
              q: 'Why convert IPv4 addresses into 32-bit unsigned integers?',
              a: 'Categorical one-hot encoding of IP addresses would create millions of sparse columns, causing massive memory usage and slow latency. Converting standard dotted-quad IPv4 strings (e.g. 192.168.1.1) into 32-bit unsigned integers allows the incremental MaxAbsScaler to normalize the address space into continuous numerical features with zero dimensionality explosion.',
            },
            {
              q: 'What is the purpose of comparing River Online OCSVM with Isolation Forest?',
              a: 'Isolation Forest is one of the most widely used unsupervised anomaly detection algorithms. Comparing River Online OCSVM against Isolation Forest on the same NetFlow data provides an empirical benchmark to evaluate whether online streaming SGD offers competitive accuracy while maintaining single-instance streaming latency.',
            },
          ].map((item, idx) => (
            <div
              key={idx}
              className="border border-border-subtle rounded-[6px] overflow-hidden bg-card-surface"
            >
              <button
                onClick={() => toggleFaq(idx)}
                className="w-full p-3.5 text-left text-xs font-semibold text-text-primary flex items-center justify-between hover:bg-elevated-surface/50 transition-colors cursor-pointer"
              >
                <span>Q{idx + 1}: {item.q}</span>
                {activeFaq === idx ? (
                  <ChevronUp className="w-4 h-4 text-text-muted shrink-0" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-text-muted shrink-0" />
                )}
              </button>
              {activeFaq === idx && (
                <div className="p-3.5 pt-0 text-xs text-text-secondary border-t border-border-subtle/50 bg-elevated-surface/20 leading-relaxed">
                  <strong className="text-text-primary block mb-1">Answer:</strong>
                  {item.a}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
