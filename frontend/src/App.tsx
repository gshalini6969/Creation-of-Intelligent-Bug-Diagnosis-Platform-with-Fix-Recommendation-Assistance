import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout/Layout";
import HomePage from "./pages/HomePage/HomePage";
import SubmitBugPage from "./pages/SubmitBugPage/SubmitBugPage";
import AnalyzeBugPage from "./pages/AnalyzeBugPage/AnalyzeBugPage";
import KnowledgeBasePage from "./pages/KnowledgeBasePage/KnowledgeBasePage";
import DashboardPage from "./pages/DashboardPage/DashboardPage";

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/submit-bug" element={<SubmitBugPage />} />
          <Route path="/analyze-bug" element={<AnalyzeBugPage />} />
          <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
