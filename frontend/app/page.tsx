"use client";

import { FormEvent, useState } from "react";
import { ReportDashboard } from "@/components/ReportDashboard";
import { api } from "@/lib/api";
import type { Building, Report } from "@/lib/types";

export default function Home() {
  const [query, setQuery] = useState("");
  const [borough, setBorough] = useState("");
  const [candidates, setCandidates] = useState<Building[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function search(event?: FormEvent, demo = false) {
    event?.preventDefault(); setLoading(true); setError(""); setCandidates([]);
    try {
      const results = await api.search(demo ? "demo" : query, borough || undefined);
      setCandidates(results);
      if (!results.length) setError("No NYC building matches were returned. Try including the house number and borough.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Search failed."); }
    finally { setLoading(false); }
  }

  async function select(building: Building) {
    setLoading(true); setError("");
    try { setReport(await api.report(building.id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Report failed."); }
    finally { setLoading(false); }
  }

  if (report) return <ReportDashboard report={report} onReset={() => { setReport(null); setCandidates([]); }} />;

  return <main className="landing">
    <header className="nav"><div className="brand"><span className="brand-mark">XR</span><span>NYC Building X-Ray</span></div><a href="#sources">How it works</a></header>
    <section className="hero">
      <div className="hero-copy"><div className="eyebrow">Public records, made legible</div><h1>Know the building<br />before you sign.</h1><p>Explore public complaints, housing violations, and recurring issues at an NYC address.</p></div>
      <div className="search-card">
        <form onSubmit={search}><label htmlFor="address">NYC building address</label><div className="search-row"><input id="address" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="e.g. 350 5th Avenue" minLength={2} required autoComplete="street-address"/><select value={borough} onChange={(event) => setBorough(event.target.value)} aria-label="Borough"><option value="">Any borough</option><option>Manhattan</option><option>Bronx</option><option>Brooklyn</option><option>Queens</option><option>Staten Island</option></select><button className="primary-button" disabled={loading}>{loading ? "Searching…" : "Search"}</button></div></form>
        <div className="or"><span>or</span></div><button className="demo-button" onClick={() => search(undefined, true)} disabled={loading}><span>Try a demo building</span><small>No API keys or live data needed</small><b>→</b></button>
        {error && <div className="error" role="alert">{error}</div>}
      </div>
    </section>
    {loading && <section className="candidate-shell"><div className="skeleton wide"/><div className="skeleton"/><div className="skeleton"/></section>}
    {!!candidates.length && <section className="candidate-shell"><div className="eyebrow">Confirm the building</div><h2>{candidates[0].demo ? "Choose a fictional demo" : "Which building did you mean?"}</h2><div className="candidate-grid">{candidates.map((building) => <button className="candidate" onClick={() => select(building)} key={building.id}><div><strong>{building.address}</strong><span>{building.borough}</span></div><p>{building.demo ? "Fictional records · fixed date" : `${Math.round(building.confidence * 100)}% address match`}</p><small>{building.ambiguity || building.match_method}</small><b>View report →</b></button>)}</div></section>}
    <section className="source-intro" id="sources"><div><div className="eyebrow">One address, three lenses</div><h2>Follow the evidence,<br />not a score.</h2></div><div className="source-cards"><article><span>01</span><h3>311 requests</h3><p>Resident reports reveal repeated patterns over time. A report is not a verified violation.</p></article><article><span>02</span><h3>HPD violations</h3><p>Housing-code violations retain documented classes and their latest recorded status.</p></article><article><span>03</span><h3>DOB complaints</h3><p>Building-related complaints remain separate from verified violations and permit records.</p></article></div></section>
    <footer><strong>NYC Building X-Ray</strong><p>An investigation aid, not a safety determination or rental recommendation.</p></footer>
  </main>;
}
