import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import SessionDetailPage from './pages/SessionDetailPage'
import SessionHistory from './pages/SessionHistory'

function Nav() {
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `text-sm px-3 py-1.5 rounded-full ${isActive ? 'bg-[#1d9e75] text-white' : 'text-[#5f5e5a]'}`
  return (
    <nav className="sticky top-0 z-10 bg-[#f3f1ea]/90 backdrop-blur border-b border-black/5">
      <div className="max-w-[1100px] mx-auto px-4 py-2 flex items-center gap-2">
        <span className="text-sm font-bold mr-2">With-Stride</span>
        <NavLink to="/" end className={linkClass}>
          실시간 대시보드
        </NavLink>
        <NavLink to="/sessions" className={linkClass}>
          세션 이력
        </NavLink>
      </div>
    </nav>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Nav />
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/sessions" element={<SessionHistory />} />
        <Route path="/sessions/:id" element={<SessionDetailPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
