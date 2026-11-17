import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import LoginPage from "./features/auth/LoginPage"

const App = () => {
  return (
    <BrowserRouter>
     <Routes>
        <Route path="/" element={<Navigate to="/login" replace/>} />
        <Route path="/login" element={<LoginPage />} />

         <Route path="*" element={<Navigate to="/login" replace />} />

     </Routes>
    </BrowserRouter>
  )
}

export default App