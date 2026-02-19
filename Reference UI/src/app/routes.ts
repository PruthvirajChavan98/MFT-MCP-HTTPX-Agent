import { createBrowserRouter } from "react-router";
import { LandingPage } from "./components/landing/LandingPage";
import { AdminLayout } from "./components/admin/AdminLayout";
import { Dashboard } from "./components/admin/Dashboard";
import { KnowledgeBase } from "./components/admin/KnowledgeBase";
import { SessionCosts } from "./components/admin/SessionCosts";
import { ChatTraces } from "./components/admin/ChatTraces";
import { QuestionCategories } from "./components/admin/QuestionCategories";
import { FeedbackPage } from "./components/admin/FeedbackPage";
import { GuardrailsPage } from "./components/admin/GuardrailsPage";
import { RateLimiting } from "./components/admin/RateLimiting";
import { ModelsPage } from "./components/admin/ModelsPage";
import { SystemHealth } from "./components/admin/SystemHealth";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: LandingPage,
  },
  {
    path: "/admin",
    Component: AdminLayout,
    children: [
      { index: true, Component: Dashboard },
      { path: "knowledge-base", Component: KnowledgeBase },
      { path: "session-costs", Component: SessionCosts },
      { path: "traces", Component: ChatTraces },
      { path: "categories", Component: QuestionCategories },
      { path: "feedback", Component: FeedbackPage },
      { path: "guardrails", Component: GuardrailsPage },
      { path: "rate-limiting", Component: RateLimiting },
      { path: "models", Component: ModelsPage },
      { path: "health", Component: SystemHealth },
    ],
  },
]);
