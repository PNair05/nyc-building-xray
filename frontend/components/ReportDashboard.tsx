"use client";

import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Evidence, Explanation, Report } from "@/lib/types";
import { BuildingModel3D } from "./BuildingModel3D";
import { TrendChart } from "./TrendChart";

const CLASS_LABELS: Record<string, string> = { A: "Non-hazardous", B: "Hazardous", C: "Immediately hazardous", I: "Information order" };

function count(value: number | null) {
  return value === null ? "Unavailable" : value.toLocaleString();
}

function StatusPill({ value }: { value: string }) {
  return <span className={`pill pill-${value.toLowerCase().replaceAll("_", "-")}`}>{value.replaceAll("_", " ")}</span>;
}

export function ReportDashboard({ report, onReset }: { report: Report; onReset: () => void }) {
  const [category, setCategory] = useState("All categories");
  const [source, setSource] = useState("All sources");
  const [query, setQuery] = useState("");
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [selected, setSelected] = useState<Evidence | null>(null);
  const categories = Object.keys(report.category_totals);
  const records = useMemo(() => report.records.filter((record) => {
    const sourceMatch = source === "All sources" || record.source === source;
    const text = `${record.description} ${record.original_category} ${record.id}`.toLowerCase();
    return sourceMatch && text.includes(query.toLowerCase());
  }), [report.records, source, query]);

  async function explain() {
    setExplaining(true);
    try { setExplanation(await api.explain(report.building.id)); }
    finally { setExplaining(false); }
  }

  function jumpToEvidence(ids: string[]) {
    const first = report.records.find((record) => ids.includes(record.id));
    if (first) setSelected(first);
  }

  return (
    <main>
      {report.mode === "demo" && <div className="demo-banner">Demo data — fictional example <span>Fixed reference date: {report.reference_date}</span></div>}
      <header className="nav compact">
        <button className="brand brand-button" onClick={onReset} aria-label="Start a new search"><span className="brand-mark">XR</span><span>NYC Building X-Ray</span></button>
        <button className="text-button" onClick={onReset}>New search</button>
      </header>

      <section className="report-shell">
        <div className="building-head">
          <div className="building-info-column">
            <div className="building-copy">
              <div className="eyebrow">Building report · {report.mode === "demo" ? "Fictional fixture" : "Live public records"}</div>
              <h1>{report.building.address}</h1>
              <p>{report.building.borough} · {report.period.label} ending {report.period.end_exclusive}</p>
              {report.building.ambiguity && <div className="notice">{report.building.ambiguity}</div>}
            </div>

            <section className="coverage-strip" aria-label="Data coverage">
              {report.coverage.map((item) => <div key={item.key} className="coverage-item">
                <div><span className={`status-dot ${item.status}`} /> <strong>{item.key}</strong></div>
                <StatusPill value={item.status} />
                <small>{item.record_count === null ? "No count" : `${item.record_count} source records`} · {item.cached ? "cached" : "retrieved"} {new Date(item.retrieved_at).toLocaleString()}</small>
                {item.warnings.map((warning) => <small className="warning" key={warning}>{warning}</small>)}
              </div>)}
            </section>

            <section className="metric-grid" aria-label="Summary metrics">
              <article className="metric-card"><span>311 requests</span><strong>{count(report.summary.complaints_311)}</strong><small>{report.period.label} · NYC 311</small></article>
              <article className="metric-card"><span>Open HPD violations</span><strong>{count(report.summary.open_hpd_violations)}</strong><small>Latest status snapshot · HPD</small></article>
              <article className="metric-card"><span>HPD by class</span><strong className="class-counts">{report.summary.hpd_by_class ? Object.entries(report.summary.hpd_by_class).map(([key, value]) => <span title={CLASS_LABELS[key]} key={key}>{key} {value}</span>) : "Unavailable"}</strong><small>Open only · documented classification</small></article>
              <article className="metric-card"><span>DOB complaints</span><strong>{count(report.summary.dob_complaints)}</strong><small>{report.period.label} · reports, not violations</small></article>
            </section>
          </div>
          <BuildingModel3D building={report.building} records={report.records} onSelect={setSelected} />
        </div>
        <details className="identity-card">
          <summary>Building match details</summary>
          <dl><dt>BIN</dt><dd>{report.building.bin || "Unavailable"}</dd><dt>BBL</dt><dd>{report.building.bbl || "Unavailable"}</dd><dt>Method</dt><dd>{report.building.match_method}</dd></dl>
        </details>

        <div className="dashboard-grid">
          <section className="panel findings-panel">
            <div className="section-heading"><div><div className="eyebrow">Start here</div><h2>Worth investigating</h2></div></div>
            {report.findings.length ? report.findings.map((finding, index) => <article className="finding" key={finding.id}>
              <div className="finding-number">0{index + 1}</div><div><h3>{finding.title}</h3><p>{finding.detail}</p><button onClick={() => jumpToEvidence(finding.evidence_ids)}>View {finding.evidence_ids.length} supporting record{finding.evidence_ids.length === 1 ? "" : "s"} →</button></div>
            </article>) : <div className="empty-state"><strong>No heuristic findings in this view</strong><p>The query succeeded, but no category met the recurrence rule and no open HPD violations were found.</p></div>}
          </section>

          <section className="panel chart-panel">
            <div className="section-heading"><div><div className="eyebrow">311 reports</div><h2>Monthly pattern</h2></div>
              <label className="select-label"><span className="sr-only">Chart category</span><select value={category} onChange={(event) => setCategory(event.target.value)}><option>All categories</option>{categories.map((item) => <option key={item}>{item}</option>)}</select></label>
            </div>
            {report.coverage.find((item) => item.key === "311")?.status === "unavailable" ? <div className="empty-state"><strong>311 data unavailable</strong><p>This source failed, so the chart is intentionally not shown as zero.</p></div> : <TrendChart monthly={report.monthly} category={category} />}
            <p className="fine-print">Current incomplete month excluded. Counts represent building-matched reports, not confirmed conditions.</p>
          </section>

          <section className="panel categories-panel">
            <div className="section-heading"><div><div className="eyebrow">Normalized categories</div><h2>What people reported</h2></div></div>
            <div className="category-list">{categories.map((item) => {
              const total = report.category_totals[item];
              const max = Math.max(1, ...Object.values(report.category_totals));
              return <div className="category-row" key={item}><div><span>{item}</span><strong>{total}</strong></div><div className="bar"><span style={{ width: `${(total / max) * 100}%` }} /></div></div>;
            })}</div>
          </section>

          <section className="panel explain-panel">
            <div className="section-heading"><div><div className="eyebrow">Plain language</div><h2>Turn records into questions</h2></div></div>
            {!explanation ? <div className="explain-intro"><p>Generate a short, evidence-linked overview and practical questions for a landlord. The report works without an AI key.</p><button className="primary-button" onClick={explain} disabled={explaining}>{explaining ? "Preparing…" : "Explain this building"}</button></div> : <div className="explanation">
              <span className="explanation-label">{explanation.label}</span><p>{explanation.overview}</p>
              {explanation.findings.map((finding) => <button className="linked-finding" key={finding.text} onClick={() => jumpToEvidence(finding.evidence_ids)}>{finding.text} <span>Evidence →</span></button>)}
              <h3>Questions to ask</h3><ol>{explanation.landlord_questions.map((question) => <li key={question}>{question}</li>)}</ol>
            </div>}
          </section>
        </div>

        <section className="panel evidence-panel">
          <div className="section-heading"><div><div className="eyebrow">Trace every claim</div><h2>Evidence table</h2></div><div className="table-tools"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search records" aria-label="Search evidence records"/><select value={source} onChange={(event) => setSource(event.target.value)} aria-label="Filter by source"><option>All sources</option><option>311</option><option>HPD</option><option>DOB</option></select></div></div>
          <div className="table-wrap"><table><thead><tr><th>Date</th><th>Source</th><th>Category</th><th>Description</th><th>Status</th><th /></tr></thead><tbody>{records.map((record) => <tr key={record.id}><td>{record.occurred_at.slice(0, 10)}</td><td><span className="source-chip">{record.source}</span></td><td>{record.category}</td><td className="description-cell">{record.description}</td><td><StatusPill value={record.status_group === "not_applicable" ? record.status : record.status_group} /></td><td><button className="row-button" onClick={() => setSelected(record)}>Open</button></td></tr>)}</tbody></table>{!records.length && <div className="empty-state">No records match these filters.</div>}</div>
        </section>

        <section className="limitations"><h2>Read this report carefully</h2><ul>{report.limitations.map((item) => <li key={item}>{item}</li>)}</ul></section>
      </section>

      {selected && <div className="modal-backdrop" role="presentation" onMouseDown={() => setSelected(null)}><article className="modal" role="dialog" aria-modal="true" aria-labelledby="evidence-title" onMouseDown={(event) => event.stopPropagation()}>
        <button className="modal-close" onClick={() => setSelected(null)} aria-label="Close evidence">×</button><div className="eyebrow">{selected.source} · {selected.id}</div><h2 id="evidence-title">{selected.category}</h2><p>{selected.description}</p><dl><dt>Source category</dt><dd>{selected.original_category}</dd><dt>Date</dt><dd>{selected.occurred_at.slice(0, 10)}</dd><dt>Raw status</dt><dd>{selected.status}</dd>{selected.location_detail && <><dt>Documented location</dt><dd>{selected.location_detail}</dd></>}{selected.classification && <><dt>HPD class</dt><dd>{selected.classification} — {CLASS_LABELS[selected.classification] || "Unmapped"}</dd></>}</dl><a className="primary-button inline-button" href={selected.source_url} target="_blank" rel="noreferrer">Open source dataset ↗</a><p className="fine-print">Source text is presented as evidence, not as a legal or safety conclusion.</p>
      </article></div>}
    </main>
  );
}
