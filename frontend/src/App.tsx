import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { EmployeeDashboard } from "./pages/EmployeeDashboard";
import { LoginPage } from "./pages/LoginPage";
import { ManagerQueuePage } from "./pages/ManagerQueuePage";
import { NewRequestPage } from "./pages/NewRequestPage";
import { RequestDetailPage } from "./pages/RequestDetailPage";
import { ReviewQueuePage } from "./pages/ReviewQueuePage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<EmployeeDashboard />} />
          <Route path="requests/new" element={<NewRequestPage />} />
          <Route path="requests/:id" element={<RequestDetailPage />} />
          <Route path="review" element={<ReviewQueuePage />} />
          <Route path="manager" element={<ManagerQueuePage />} />
        </Route>
      </Route>
      <Route path="/" element={<Navigate to="/app" replace />} />
      <Route path="*" element={<Navigate to="/app" replace />} />
    </Routes>
  );
}
