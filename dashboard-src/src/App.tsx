import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import AppLayout from "@/components/AppLayout";
import Index from "./pages/Index";
import Visualization from "./pages/Visualization";
import LogPage from "./pages/LogPage";
import LogicPage from "./pages/LogicPage";
import SettingsPage from "./pages/SettingsPage";
import UpdatePage from "./pages/UpdatePage";
import NotFound from "./pages/NotFound";
import VisuPanel from "./pages/VisuPanel";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          {/* Standalone panel route – no sidebar/header */}
          <Route path="/panel" element={<VisuPanel />} />

          {/* Dashboard routes with full layout */}
          <Route path="*" element={
            <AppLayout>
              <Routes>
                <Route path="/" element={<Index />} />
                <Route path="/visu" element={<Visualization />} />
                <Route path="/logic" element={<LogicPage />} />
                <Route path="/log" element={<LogPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/update" element={<UpdatePage />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </AppLayout>
          } />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
