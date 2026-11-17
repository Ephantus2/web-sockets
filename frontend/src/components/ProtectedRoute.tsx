import {Navigate, Outlet} from "react-router-dom"

import {useAuth} from "../context/AuthContext";

function ProtectedRoute() {
    const {isAuthenticated, loading} = useAuth();

    if (loading) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-slate-950 text-white">
                Checking authentication...
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace/>
    }

    return <Outlet />
}

export default ProtectedRoute