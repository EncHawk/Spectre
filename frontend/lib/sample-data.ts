export type SessionStatus = "running" | "needs-approval" | "healthy" | "investigating";

export type Session = {
  id: string;
  agent: string;
  repository: string;
  branch: string;
  status: SessionStatus;
  started: string;
  runs: number;
  failures: number;
  fix: string;
  progress: number;
};

export const sessions: Session[] = [
  {
    id: "ses_08f1a",
    agent: "checkout_agent",
    repository: "northstar/checkout-agent",
    branch: "release/v2.8",
    status: "needs-approval",
    started: "12 min ago",
    runs: 64,
    failures: 3,
    fix: "PR ready",
    progress: 100,
  },
  {
    id: "ses_91b2c",
    agent: "research_agent",
    repository: "northstar/research-agent",
    branch: "main",
    status: "running",
    started: "28 min ago",
    runs: 41,
    failures: 1,
    fix: "Testing fix",
    progress: 76,
  },
  {
    id: "ses_73ad9",
    agent: "support_triage",
    repository: "Repository not connected",
    branch: "—",
    status: "investigating",
    started: "1 hr ago",
    runs: 29,
    failures: 4,
    fix: "Suggestion ready",
    progress: 58,
  },
  {
    id: "ses_56c8e",
    agent: "catalog_agent",
    repository: "northstar/catalog-agent",
    branch: "main",
    status: "healthy",
    started: "Yesterday",
    runs: 52,
    failures: 0,
    fix: "No action",
    progress: 100,
  },
];

export const statusLabel: Record<SessionStatus, string> = {
  running: "Running",
  "needs-approval": "Needs approval",
  healthy: "Healthy",
  investigating: "Investigating",
};
