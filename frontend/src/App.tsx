import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import LoginPage from "./features/auth/LoginPage"
import DashboardPage from "./pages/DashboardPage"
import ProtectedRoute from "./components/ProtectedRoute"
import { useAuth } from "./context/AuthContext"

function AppRoutes() {

  const {isAuthenticated} = useAuth()

  return (
     <Routes>
        <Route path="/login" element={isAuthenticated ? <Navigate to="/dashboard" replace/> : <LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<DashboardPage />} />
        </Route>

        <Route path="/" element={
          <Navigate to={isAuthenticated ? "/dashboard" : "/login"}/>
        }/>

         <Route path="*" element={<Navigate to="/login" replace />} />

     </Routes>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}

export default App