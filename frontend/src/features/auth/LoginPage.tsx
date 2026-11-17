import { useState } from "react";
import { LockKeyhole, User, Eye, EyeOff } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { useNavigate } from "react-router-dom";

const LoginPage = () => {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState("")
    const {login} = useAuth();
    
    const navigate = useNavigate();

    const handleLogin = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();

        setLoading(true)
        setError("")

        try{
            await login({
                username,
                password
            })

            navigate("/dashboard", {replace: true})
        } catch (err){
            console.error(err);
            setError("Login error");
            setError("Invalid username or password.")
        } finally {
            setLoading(false);
        }
    }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
        <div className="w-full max-w-md rounded-2xl border border-slate-800 bd-slate-900 p-8 shadow-2xl ">
            <div className="mb-8 text-center">
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-600">
                    <LockKeyhole className="h-7 w-7 text-white"/>
                </div>
                <h1 className="text-2xl font-bold text-white">
                    Welcome back
                </h1>
                <p className="mt-2 text-sm text-slate-400">
                    Sign in to your real-time chat account
                </p>

            </div>
            <form onSubmit={handleLogin} className="space-y-5">
                <div>
                    <label className="mb-2 block text-sm font-medium text-slate-300">Username</label>

                    <div className="relative">
                        <User className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500"/>
                        <input 
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            placeholder="Enter your username"
                            required
                            className="w-full rounded-lg border border-slate-700 bg-slate-800 py-3 pl-11 pr-4 text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                        />
                    </div>
                </div>

                <div>
                    <label className="mb-2 block text-sm font-medium text-slate-300">
                        Password
                    </label>
                    <div className="relative">
                        <User className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500"/>
                        <input 
                            type="text"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="Enter your password"
                            required
                            className="w-full rounded-lg border border-slate-700 bg-slate-800 py-3 pl-11 pr-4 text-white outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                        />

                        <button 
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white"
                        >
                            {showPassword ? (<EyeOff className="h-5 w-5"/>) : (<Eye className="h-5 w-5"/>)}
                        </button>
                    </div>

                </div>

                {error && (
                    <p className="rounded-lg bg-red-500/10 p-3 text-sm text-red-400">{error}</p>
                )}

                <button
                type="submit"
                disabled={loading}
                className="w-full rounded-lg bg-blue-600 py-3 font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {loading ? "Signing in..." : "Sign in"}
                </button>
            </form>

        </div>

    </main>
  )
}

export default LoginPage