import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Header } from "./components/layout/Header";
import { ChatPage } from "./pages/ChatPage";
import { useAuth } from "./hooks/useAuth";

export function App() {
  const { whoAmI, cognitoConfig, loggedIn, login, logout } = useAuth();

  return (
    <BrowserRouter>
      <Header
        whoAmI={whoAmI}
        cognitoConfig={cognitoConfig}
        loggedIn={loggedIn}
        onLogin={login}
        onLogout={logout}
      />
      <Routes>
        <Route path="/" element={<ChatPage />} />
        {/* Cognito redirects back to /auth?code=... — the backend handles the
            OAuth code exchange and sets a session cookie, then redirects to /.
            React Router must not intercept this path. */}
        <Route path="/auth" element={<Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
