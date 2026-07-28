// src/App.tsx
// Asistan — Ana uygulama bileşeni

import { useEffect } from "react";
import { Route, Switch } from "wouter";
import { Toaster } from "sonner";
import { useChatStore } from "./store/chatStore";
import { useWebSocket } from "./hooks/useWebSocket";
import { ApprovalModal } from "./components/ApprovalModal";

import { DashboardLayout } from "./layouts/DashboardLayout";
import { Home } from "./pages/Home";
import { Chat } from "./pages/Chat";
import { Projects, Data } from "./pages/Placeholders";
import { VoicePage } from "./pages/Voice";
import { Settings } from "./pages/Settings";
import { Logs } from "./pages/Logs";
import { Permissions } from "./pages/Permissions";
import { Models } from "./pages/Models";
import { Tools } from "./pages/Tools";

export default function App() {
  const { loadSettings, pendingApproval } = useChatStore();
  const { sendMessage } = useWebSocket(); // Initialize websocket connection globally

  useEffect(() => {
    loadSettings();
  }, []);

  return (
    <>
      <DashboardLayout>
        <Switch>
          <Route path="/" component={Home} />
          <Route path="/chat" component={Chat} />
          <Route path="/voice" component={VoicePage} />
          <Route path="/projects" component={Projects} />
          <Route path="/models" component={Models} />
          <Route path="/tools" component={Tools} />
          <Route path="/data" component={Data} />
          <Route path="/permissions" component={Permissions} />
          <Route path="/logs" component={Logs} />
          <Route path="/settings" component={Settings} />
          <Route>
            <div className="p-8 text-center text-brand-gray">404 - Sayfa Bulunamadı</div>
          </Route>
        </Switch>
      </DashboardLayout>

      {/* Global Modals */}
      {pendingApproval && <ApprovalModal sendMessage={sendMessage} />}
      <Toaster position="bottom-right" />
    </>
  );
}
