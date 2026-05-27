import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ChatPage } from "./pages/ChatPage";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatPage />} />
        {/* Cognito redirects back to /auth?code=...; the backend handles OAuth exchange. */}
        <Route path="/auth" element={<Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
