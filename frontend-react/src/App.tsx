import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { ChatPage } from "./pages/ChatPage";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatPage />} />
        {/* Cognito redirects back to /auth?code=...; the backend handles OAuth exchange. */}
        <Route path="/auth" element={<RedirectHome />} />
        <Route path="/index.html" element={<RedirectHome />} />
        <Route path="*" element={<RedirectHome />} />
      </Routes>
    </BrowserRouter>
  );
}

function RedirectHome() {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const freshLogin = params.get("fresh_login");
  const search = freshLogin === "1" ? "?fresh_login=1" : "";

  return <Navigate to={{ pathname: "/", search }} replace />;
}
