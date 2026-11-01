import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AdminDepartmentsPage } from "./pages/AdminDepartmentsPage";
import { DepartmentDashboard } from "./pages/DepartmentDashboard";
import { EmployeeDashboard } from "./pages/EmployeeDashboard";
import { HRDashboard } from "./pages/HRDashboard";
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
          <Route path="department" element={<DepartmentDashboard />} />
          <Route path="manager" element={<ManagerQueuePage />} />
          <Route path="review" element={<ReviewQueuePage />} />
          <Route path="hr" element={<HRDashboard />} />
          <Route path="admin/departments" element={<AdminDepartmentsPage />} />
        </Route>
      </Route>
      <Route path="/" element={<Navigate to="/app" replace />} />
      <Route path="*" element={<Navigate to="/app" replace />} />
    </Routes>
  );
}
