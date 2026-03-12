import { Switch, Route } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import Layout from "@/components/layout";
import RunsList from "@/pages/runs-list";
import InvestigationDetail from "@/pages/investigation-detail";
import MLOverview from "@/pages/ml-overview";
import MLDetail from "@/pages/ml-detail";
import KnowledgeBrowser from "@/pages/knowledge-browser";
import NotFound from "@/pages/not-found";

function Router() {
  return (
    <Layout>
      <Switch>
        <Route path="/" component={RunsList} />
        <Route path="/investigations/:runId" component={InvestigationDetail} />
        <Route path="/ml" component={MLOverview} />
        <Route path="/ml/:runId" component={MLDetail} />
        <Route path="/knowledge" component={KnowledgeBrowser} />
        <Route component={NotFound} />
      </Switch>
    </Layout>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <Toaster />
        <Router />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
