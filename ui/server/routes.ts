import type { Express } from "express";
import { createServer, type Server } from "http";
import {
  mockDomains,
  mockMeta,
  mockRuns,
  mockInvestigations,
  mockMLSummaries,
  mockAnomalies,
  mockTrends,
  mockAggregations,
  mockCompleteness,
  mockKnowledgeStats,
  mockKnowledgeEntries,
  mockReports,
} from "./storage";

export async function registerRoutes(
  httpServer: Server,
  app: Express
): Promise<Server> {
  app.get("/api/domains", (_req, res) => {
    res.json(mockDomains);
  });

  app.get("/api/meta", (_req, res) => {
    res.json(mockMeta);
  });

  app.get("/api/runs", (req, res) => {
    let runs = [...mockRuns.runs];
    const { domain, command, status, source_file, search, limit, offset } = req.query;

    if (domain) runs = runs.filter((r) => r.domain === domain);
    if (command) runs = runs.filter((r) => r.command === command);
    if (status) {
      if (status === "dry_run") {
        runs = runs.filter((r) => "is_dry_run" in r && r.is_dry_run === true);
      } else {
        runs = runs.filter((r) => "status" in r && r.status === status);
      }
    }
    if (source_file) {
      const sf = String(source_file).toLowerCase();
      runs = runs.filter((r) => r.source_files.some((f: string) => f.toLowerCase().includes(sf)));
    }
    if (search) {
      const s = String(search).toLowerCase();
      runs = runs.filter((r) =>
        r.run_id.toLowerCase().includes(s) ||
        ("label" in r && typeof r.label === "string" && r.label.toLowerCase().includes(s))
      );
    }

    const total = runs.length;
    const o = parseInt(String(offset || "0"), 10);
    const l = Math.min(parseInt(String(limit || "50"), 10), 500);
    runs = runs.slice(o, o + l);

    res.json({ total, runs });
  });

  app.get("/api/investigations/:runId", (req, res) => {
    const data = mockInvestigations[req.params.runId];
    if (!data) return res.status(404).json({ message: "Investigation not found" });
    res.json(data);
  });

  app.get("/api/investigations/:runId/report", (req, res) => {
    const data = mockReports[req.params.runId];
    if (!data) return res.status(404).json({ message: "Report not found" });
    const format = req.query.format || "json";
    if (format === "markdown") {
      res.json({ run_id: data.run_id, markdown: data.markdown });
    } else {
      res.json({ run_id: data.run_id, report: data });
    }
  });

  app.get("/api/ml", (_req, res) => {
    const summaries = Object.values(mockMLSummaries);
    summaries.sort((a: any, b: any) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime());
    const allAnomalies: any[] = [];
    for (const s of summaries) {
      const anomalies = mockAnomalies[s.run_id] || [];
      for (const a of anomalies) {
        allAnomalies.push({ ...a, run_id: s.run_id, started_at: s.started_at });
      }
    }
    const allTrends: any[] = [];
    for (const s of summaries) {
      const trends = mockTrends[s.run_id] || [];
      for (const t of trends) {
        allTrends.push({ ...t, run_id: s.run_id, started_at: s.started_at });
      }
    }
    res.json({ summaries, anomalies: allAnomalies, trends: allTrends });
  });

  app.get("/api/ml/:runId", (req, res) => {
    const data = mockMLSummaries[req.params.runId];
    if (!data) return res.status(404).json({ message: "ML run not found" });
    res.json(data);
  });

  app.get("/api/ml/:runId/aggregations", (req, res) => {
    let data = mockAggregations[req.params.runId] || [];
    const { dimension, dimension_value, limit, offset } = req.query;

    if (dimension) data = data.filter((a: any) => a.dimension === dimension);
    if (dimension_value) data = data.filter((a: any) => a.dimension_value === dimension_value);

    const total = data.length;
    const o = parseInt(String(offset || "0"), 10);
    const l = Math.min(parseInt(String(limit || "100"), 10), 1000);
    data = data.slice(o, o + l);

    res.json({ total, aggregations: data });
  });

  app.get("/api/ml/:runId/anomalies", (req, res) => {
    const data = mockAnomalies[req.params.runId] || [];
    res.json(data);
  });

  app.get("/api/ml/:runId/trends", (req, res) => {
    const data = mockTrends[req.params.runId] || [];
    res.json(data);
  });

  app.get("/api/ml/:runId/completeness", (req, res) => {
    let data = mockCompleteness[req.params.runId] || [];
    const { dimension, field_name, limit, offset } = req.query;

    if (dimension) data = data.filter((c: any) => c.dimension === dimension);
    if (field_name) data = data.filter((c: any) => c.field_name === field_name);

    const total = data.length;
    const o = parseInt(String(offset || "0"), 10);
    const l = Math.min(parseInt(String(limit || "100"), 10), 1000);
    data = data.slice(o, o + l);

    res.json({ total, completeness: data });
  });

  app.get("/api/knowledge/stats", (_req, res) => {
    res.json(mockKnowledgeStats);
  });

  app.get("/api/knowledge/search", (req, res) => {
    const q = req.query.q ? String(req.query.q).toLowerCase() : "";
    const tier = req.query.tier ? String(req.query.tier) : null;
    const o = parseInt(String(req.query.offset || "0"), 10);
    const l = Math.min(parseInt(String(req.query.limit || "20"), 10), 100);

    let results = [...mockKnowledgeEntries];
    if (tier) results = results.filter((e) => e.tier === tier);
    if (q) {
      const words = q.split(/\s+/).filter(Boolean);
      results = results.filter((e) =>
        words.some(
          (w) =>
            e.statement.toLowerCase().includes(w) ||
            e.topic.toLowerCase().includes(w) ||
            (e.dimension_value && e.dimension_value.toLowerCase().includes(w))
        )
      );
    }
    const total = results.length;
    results = results.slice(o, o + l);

    res.json({ total, results });
  });

  return httpServer;
}
