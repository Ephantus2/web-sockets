import { useAuth } from "../context/AuthContext";

function DashboardPage() {
    const {logout} = useAuth();

    return (
        <main className="flex min-h-screen items-center bg-slate-950">
            <div className="text-center">
                <h1 className="text-3xl font-bold text-white">Chat Dashboard</h1>
                <p className="mt-3 text-slate-400">Authentication successful. Welcome to your chat plartform</p>

                <button 
                onClick={logout}
                className="mt-6 rounded-lg bg-red-600 px-6 font-semibold text-white hover:bg-red-500">
                    Logout
                </button>
            </div>
            
        </main>
    )
}

export default DashboardPage;